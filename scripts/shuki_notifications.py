"""Selective notices; the existing review inbox remains the durable inbox/outbox."""
import hashlib
import json
import time
import urllib.request
import uuid
from pathlib import Path

import shuki_paths
import shuki_webpush

NOTICE_TYPES = {"upgrade", "decision", "blocker", "important_result"}
PRODUCER_GUIDANCE = """
Notification policy: Routine edits, task status changes, and routine reviews belong in
activity history, not the user's notification inbox. Only for a decision, an actual
blocker requiring user action, or an important usable result, write one deduplicated
JSON notice to 99_System/review-inbox/ with source, title, summary, notification
(decision|blocker|important_result), and optional path/task_path. Use English.
Summary: outcome, why it matters, required action (or 'No action needed'), at most
400 characters; no execution log. Do not report routine job completion or duplicate
an existing notice/decision card. Existing notification delivery handles the inbox.
"""


# Ordered for display: what blocks you first, what you must decide next, then results/updates.
CATEGORIES = [
    ("blocker", "barrier", "Blocked"),
    ("decision", "scale", "Decide"),
    ("important_result", "check", "Result"),
    ("upgrade", "arrow-up", "Update"),
]


def category(item):
    """The bucket a surfaced notice belongs to; only called for items that qualify."""
    kind = item.get("notification")
    if kind in NOTICE_TYPES:
        return kind
    if item.get("fm_status") == "on-hold":
        return "decision"
    return "important_result"


def needs_attention(item):
    if item.get("notification") in NOTICE_TYPES:
        return True
    # A task being edited/completed alone is not an event the user must review.
    if item.get("source") in {"vault_task", "ai_done"}:
        return item.get("fm_status") == "on-hold" or (
            item.get("source") == "ai_done" and item.get("fm_priority") in {"高", "high"})
    return False


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def post_notice(event, title, summary, kind="upgrade", acknowledged=False, session="", choices=None):
    """Deduplicate across unread and acknowledged notices; never lose pending delivery.

    acknowledged=True writes straight to processed/: it is still pushed and still kept in
    history, but it never adds an unread card (used by the daily digest, which is a
    recap rather than something to act on).
    """
    inbox = shuki_paths.system_dir() / "review-inbox"
    filename = "notice-" + hashlib.sha256(event.encode()).hexdigest()[:20] + ".json"
    path = (inbox / "processed" / filename) if acknowledged else (inbox / filename)
    for existing in (inbox / filename, inbox / "processed" / filename):
        if existing.exists():
            return existing
    atomic_json(path, {"source": "system", "kind": "Notification", "notification": kind,
                       "title": title, "summary": summary[:400], "ts": time.time(),
                       "push_pending": True, "push_attempts": 0, "event": event,
                       "session": session, "choices": list(choices or [])[:4]})
    return path


def deliver_pending(only=None):
    """Persist delivery outcome. Two failed attempts require human intervention."""
    with shuki_webpush.state_guard("notification-delivery.lock"):
        return _deliver_pending(only)


def _deliver_pending(only=None):
    channel = shuki_webpush.config().get("channel", "ntfy")
    topic = shuki_paths.get_value("ntfy_topic")
    inbox = shuki_paths.system_dir() / "review-inbox"
    paths = ([Path(only)] if only else
             list(inbox.glob("notice-*.json")) + list((inbox / "processed").glob("notice-*.json")))
    for path in paths:
        notice = json.loads(path.read_text(encoding="utf-8"))
        if not notice.get("push_pending") or notice.get("push_attempts", 0) >= 2:
            continue
        selected = notice.setdefault("push_channel", channel)
        def persist():
            # Acknowledging a notice moves it while a push request may be in flight.
            destination = path if path.exists() else inbox / "processed" / path.name
            atomic_json(destination, notice)
        try:
            if selected == "webpush":
                shuki_webpush.send(notice, persist)
            else:
                if not topic:
                    raise RuntimeError("ntfy_topic is not configured; notices remain in the dashboard inbox")
                payload = {"topic": topic, "title": notice["title"], "message": notice["summary"],
                           "priority": 4 if notice["notification"] == "blocker" else 3}
                origin = shuki_webpush.config().get("origin")
                if origin:
                    payload["click"] = origin + "/notifications"
                req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=15) as response:
                    response.read()
        except Exception:
            notice["push_attempts"] = notice.get("push_attempts", 0) + 1
            notice["delivery_status"] = f"Delivery failed via {selected}; check notification settings."
            persist()
            raise
        notice["push_pending"] = False
        notice.pop("delivery_status", None)
        notice["delivered_at"] = time.time()
        notice["delivery_status"] = f"Accepted by {selected}; phone receipt is unverified."
        persist()


def retry_pending():
    """Explicit user recovery; preserve accepted-device receipts to avoid duplicates."""
    inbox = shuki_paths.system_dir() / "review-inbox"
    with shuki_webpush.state_guard("notification-delivery.lock"):
        for path in list(inbox.glob("notice-*.json")) + list((inbox / "processed").glob("notice-*.json")):
            notice = json.loads(path.read_text(encoding="utf-8"))
            if not notice.get("push_pending"):
                continue
            notice["push_attempts"] = 0
            receipts = notice.get("push_receipts", {})
            accepted = {identity: receipt for identity, receipt in receipts.items()
                        if receipt.get("status") == "accepted"}
            notice["push_receipts"] = accepted
            notice.pop("push_targets", None)
            if not accepted:
                notice.pop("push_channel", None)
            atomic_json(path, notice)
        _deliver_pending()
    return {"ok": True}
