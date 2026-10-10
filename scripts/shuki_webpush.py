"""Single-user, tailnet-only Web Push; all credentials live outside the repo."""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import time
import urllib.parse
import uuid

import shuki_paths

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"
CSRF_TOKEN = secrets.token_urlsafe(32)
MAX_DEVICES = 8


def state_file(name):
    return shuki_paths.secret_file(name)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def state_guard(name="webpush-state.lock"):
    # Same nonblocking OS guard pattern as runner.py, without importing the job subsystem.
    path = state_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0"); handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BlockingIOError("Notification state is busy; try again shortly.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def config():
    return read_json(state_file("webpush.json"), {"channel": "ntfy"})


def subscriptions():
    return read_json(state_file("webpush-subscriptions.json"), {})


def initialize(origin):
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("Use the HTTPS dashboard origin without a trailing slash.")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    with state_guard():
        current = config()
        if current.get("origin") and current["origin"] != origin:
            raise ValueError("Changing the registered origin requires explicit migration.")
        path = state_file("webpush-private.pem")
        if not path.exists():
            key = ec.generate_private_key(ec.SECP256R1())
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
            with path.open("xb") as output:
                output.write(pem)
            os.chmod(path, 0o600)
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        raw = key.public_key().public_bytes(serialization.Encoding.X962,
                                             serialization.PublicFormat.UncompressedPoint)
        current.update(origin=origin, public_key=base64.urlsafe_b64encode(raw).decode().rstrip("="),
                       subject=origin)
        write_json(state_file("webpush.json"), current)
    return public_config()


def public_config():
    cfg = config()
    return {"configured": bool(cfg.get("public_key")), "origin": cfg.get("origin", ""),
            "public_key": cfg.get("public_key", ""), "channel": cfg.get("channel", "ntfy"),
            "csrf": CSRF_TOKEN}


def guard(client_ip, host, origin=None, token=None, mutation=False):
    """Tailscale ACLs authenticate access; exact host/origin plus token prevent CSRF."""
    try:
        ip = ipaddress.ip_address(client_ip.split("%", 1)[0])
        remote = urllib.parse.urlsplit(config().get("origin", ""))
        authority = urllib.parse.urlsplit("//" + host)
        local = (ip.is_loopback and authority.hostname in {"127.0.0.1", "localhost", "::1"}
                 and authority.port is not None and not authority.username and not authority.password
                 and not authority.path and not authority.query and not authority.fragment)
        on_tailnet = ip in ipaddress.ip_network("100.64.0.0/10") or ip in ipaddress.ip_network("fd7a:115c:a1e0::/48")
        expected = "http://" + host if local else remote.geturl()
        if not local and (not (ip.is_loopback or on_tailnet) or host != remote.netloc or not expected):
            return False
        if origin is not None and origin != expected:
            return False
        if mutation and (origin != expected or not hmac.compare_digest(token or "", CSRF_TOKEN)):
            return False
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def validate_subscription(value):
    from cryptography.hazmat.primitives.asymmetric import ec
    if not isinstance(value, dict):
        raise ValueError("Expected a browser subscription.")
    endpoint = value.get("endpoint", "")
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise ValueError("Invalid push endpoint.")
    url = urllib.parse.urlsplit(endpoint)
    if (url.scheme != "https" or url.hostname not in {"fcm.googleapis.com", "updates.push.services.mozilla.com"}
            or url.port not in (None, 443) or url.username or url.password or url.fragment or not url.path
            or "\\" in endpoint):
        raise ValueError("Use Chrome or Firefox with a supported HTTPS push provider.")
    keys = value.get("keys", {})
    decoded = {}
    for name, size in (("p256dh", 65), ("auth", 16)):
        raw = keys.get(name, "") if isinstance(keys, dict) else ""
        if not isinstance(raw, str) or len(raw) > 100:
            raise ValueError("Invalid subscription encryption keys.")
        try:
            decoded[name] = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
        except ValueError:
            raise ValueError("Invalid subscription encryption keys.") from None
        if len(decoded[name]) != size:
            raise ValueError("Invalid subscription encryption keys.")
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded["p256dh"])
    return {"endpoint": endpoint, "keys": {k: keys[k] for k in decoded}}


def subscribe(value):
    sub = validate_subscription(value)
    identity = hashlib.sha256(sub["endpoint"].encode()).hexdigest()
    with state_guard():
        items = subscriptions()
        if identity not in items and len(items) >= MAX_DEVICES:
            raise ValueError("Device limit reached; disable an old device first.")
        old = items.get(identity, {})
        # Preserve test evidence only when the encryption keys remain the same.
        if old.get("subscription") != sub:
            old = {}
        items[identity] = dict(old, subscription=sub, updated=time.time())
        write_json(state_file("webpush-subscriptions.json"), items)
    return {"ok": True, "id": identity, "tested": bool(old.get("tested_at"))}


def unsubscribe(identity):
    with state_guard():
        items = subscriptions()
        items.pop(identity, None)
        write_json(state_file("webpush-subscriptions.json"), items)
    return {"ok": True}


def select_channel(channel, identity=""):
    if channel not in {"ntfy", "webpush"}:
        raise ValueError("Unknown notification channel.")
    with state_guard():
        if channel == "webpush" and not subscriptions().get(identity, {}).get("tested_at"):
            raise ValueError("Enable this device and send a test first.")
        cfg = config()
        cfg["channel"] = channel
        write_json(state_file("webpush.json"), cfg)
    return {"ok": True, "channel": channel}


class SafePushSession:
    """Disable redirects and implicit proxy/.netrc credentials for push endpoints."""
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.trust_env = False

    def post(self, *args, **kwargs):
        return self.session.post(*args, allow_redirects=False, **kwargs)

    def close(self):
        self.session.close()


def send(notice, persist, target=""):
    """Checkpoint each device; retry only unaccepted devices, at most twice."""
    from pywebpush import webpush, WebPushException
    cfg = config()
    devices = subscriptions()
    if target:
        devices = {target: devices[target]} if target in devices else {}
    if not cfg.get("public_key") or not devices:
        raise RuntimeError("No active SHUKI push device; enable notifications in Settings.")
    receipts = notice.setdefault("push_receipts", {})
    targets = notice.setdefault("push_targets", list(devices))
    session_id = notice.get("session", "")
    url = notice.get("url") or ("/?resume=" + urllib.parse.quote(session_id, safe="") if session_id else "/notifications")
    choices = notice.get("choices", [])[:3] if session_id else []
    body = notice.get("summary", "")[:400]
    if choices:
        body += "\n" + " · ".join(f"{i + 1}: {c}" for i, c in enumerate(choices))
    payload = json.dumps({"title": notice.get("title", "SHUKI")[:100], "body": body[:700],
                          "url": url, "tag": notice.get("event", "shuki-notice"),
                          "choices": choices, "priority": notice.get("notification", "")}, ensure_ascii=False)
    persist()
    session = SafePushSession()
    try:
        for identity in targets:
            receipt = receipts.setdefault(identity, {"attempts": 0})
            if receipt.get("status") == "accepted" or receipt.get("attempts", 0) >= 2:
                continue
            if identity not in devices:
                receipt.update(status="expired", attempts=2)
                persist()
                continue
            receipt["attempts"] += 1
            # Save before sending: an interrupted attempt is bounded too.
            persist()
            try:
                sub = validate_subscription(devices[identity]["subscription"])
                response = webpush(sub, payload, vapid_private_key=str(state_file("webpush-private.pem")),
                                   vapid_claims={"sub": cfg["subject"]}, timeout=10, ttl=3600,
                                   headers={"Urgency": "high" if notice.get("notification") == "blocker" else "normal"},
                                   requests_session=session)
                if response.status_code not in (200, 201, 202):
                    raise WebPushException("Push service rejected the notification", response=response)
            except WebPushException as error:
                status = error.response.status_code if error.response is not None else None
                receipt.update(status="failed", http_status=status)
                if status in (404, 410):
                    receipt.update(status="expired", attempts=2)
                    with state_guard():
                        current = subscriptions()
                        if current.get(identity, {}).get("subscription") == devices[identity]["subscription"]:
                            current.pop(identity, None)
                            write_json(state_file("webpush-subscriptions.json"), current)
                # Auth, throttling and connectivity errors stop this batch; no immediate retries.
                persist()
                raise RuntimeError(f"Web Push stopped (HTTP {status or 'unknown'}); check delivery in Settings.") from None
            except Exception:
                receipt["status"] = "failed"
                persist()
                raise RuntimeError("Web Push stopped; check connectivity or registration in Settings.") from None
            receipt.update(status="accepted", accepted_at=time.time())
            persist()
    finally:
        session.close()
    if not all(receipts.get(identity, {}).get("status") == "accepted" for identity in targets):
        raise RuntimeError("Some push devices need re-registration; notice remains pending.")
    return {"ok": True, "status": "accepted", "devices": len(targets)}


def test_device(identity):
    notice = {"title": "SHUKI test notification", "summary": "Tap to open SHUKI Settings.",
              "event": "shuki-test-" + uuid.uuid4().hex, "url": "/settings"}
    result = send(notice, lambda: None, target=identity)
    with state_guard():
        items = subscriptions()
        if identity in items:
            items[identity]["tested_at"] = time.time()
            write_json(state_file("webpush-subscriptions.json"), items)
    return result


def settings_html():
    return '''<details class="card settings-group" id="push-settings">
  <summary>Phone notifications</summary><div class="settings-body">
  <p id="push-status" role="status" aria-live="polite">Checking notifications…</p>
  <p class="hint">Install SHUKI from its HTTPS address on your phone. After the test arrives, switch delivery to SHUKI.</p>
  <p><button type="button" class="hbtn" id="push-enable" disabled>Enable this device</button>
  <button type="button" class="hbtn" id="push-test" disabled>Send test</button></p>
  <p><button type="button" class="hbtn" id="push-switch" disabled>Use SHUKI notifications</button>
  <button type="button" class="hbtn" id="push-ntfy">Use ntfy</button>
  <button type="button" class="hbtn" id="push-disable" disabled>Disable this device</button></p>
  <p><button type="button" class="hbtn" id="push-retry">Retry pending notices</button></p>
  <p class="hint">Tap a notification to open its conversation and choose a reply. SHUKI must be reachable through Tailscale. Push service acceptance does not confirm phone receipt.</p>
  </div></details>'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", metavar="HTTPS_ORIGIN")
    parser.add_argument("--alert", metavar="MESSAGE")
    args = parser.parse_args()
    if args.initialize:
        initialize(args.initialize)
        print("Web Push initialized; ntfy remains selected. Private keys were not printed.")
    elif args.alert:
        from shuki_notifications import post_notice, deliver_pending
        path = post_notice("dashboard-start-failure:" + time.strftime("%Y-%m-%d"),
                           "SHUKI dashboard could not recover", args.alert, kind="blocker")
        deliver_pending(only=path)
