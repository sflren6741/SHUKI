"""Local MCP inventory and bounded read-only protocol checks; never calls tools."""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import tomllib
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import shuki_notifications as notices
import shuki_paths

INTERVAL = 900
TIMEOUT = 12
STDIO_TIMEOUT = 45
WARNING = 7 * 86400
LIMIT = 1024 * 1024
STATE_PATH = shuki_paths.code_store("core/mcp-health.json")
INIT = {"protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "shuki-health", "version": "1.0"}}
# Discovery is client-specific; checks, reminders and controls use the same MCP core.
CLIENT_HELP = {
    "Claude": "https://code.claude.com/docs/en/mcp",
    "Codex": "https://learn.chatgpt.com/docs/extend/mcp?surface=cli",
    "Cursor": "https://prod.cursor.com/help/customization/mcp",
    "VS Code": "https://code.visualstudio.com/docs/agent-customization/mcp-servers",
}
JSON_CLIENTS = (("Cursor", ".cursor/mcp.json", ".cursor/mcp.json"),
                ("VS Code", None, ".vscode/mcp.json"))


def connection_id(runtime, name):
    return hashlib.sha256((runtime + ":" + name).encode()).hexdigest()[:20]


def server_map(data):
    """Existing portable JSON, VS Code JSON and Codex TOML schemas."""
    for key in ("mcpServers", "servers", "mcp_servers"):
        if key in data:
            return data[key]
    return {}


def stamp(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value / 1000 if value > 100000000000 else value
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()


def read_config(path, jsonc=False):
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    if jsonc and path.suffix != ".toml":
        strings = r'("(?:\\.|[^"\\])*")'
        text = re.sub(strings + r'|/\*[\s\S]*?\*/|//[^\r\n]*', lambda m: m.group(1) or " ", text)
        text = re.sub(strings + r'|,(?=\s*[}\]])', lambda m: m.group(1) or "", text)
    value = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Configuration must be an object")
    return value


def inventory(home=None, vault=None, extra_sources=(), environment=None, known_ids=None):
    real_home = home is None
    env = dict(os.environ) if environment is None and real_home else dict(environment or {})
    home, vault = Path(home or Path.home()), Path(vault or shuki_paths.VAULT)
    rows, errors = [], []

    def load(path):
        try:
            return read_config(path, jsonc=True)
        except (OSError, ValueError):
            errors.append(f"Cannot read {path.name}; repair its syntax or file permissions.")
            return {}

    def add(runtime, source, servers, disabled=(), client=None):
        if not isinstance(servers, dict):
            errors.append(f"Invalid MCP server map in {source}.")
            return
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                errors.append(f"Invalid MCP entry in {source}.")
                continue
            row = {"id": connection_id(runtime, str(name)),
                   "name": str(name), "runtime": runtime, "source": source,
                   "client": client or runtime, "help_url": CLIENT_HELP.get(client or runtime, ""),
                   "transport": cfg.get("type", "stdio" if cfg.get("command") else "http"),
                   "enabled": cfg.get("enabled", True) is not False and name not in disabled,
                   "config": cfg}
            # Later scopes override earlier ones; duplicated Windows path casing is collapsed.
            rows[:] = [r for r in rows if r["id"] != row["id"]]
            rows.append(row)

    portable = load(vault / ".mcp.json")
    primary = load(home / ".claude.json")
    if known_ids is None:
        known_ids = set(load(STATE_PATH)) if real_home else set()
    roots = [home / ".claude"]
    for value in (env.get("CLAUDE_CONFIG_DIR", ""), *env.get("SHUKI_CLAUDE_CONFIG_DIRS", "").split(os.pathsep)):
        if value:
            root = Path(value).expanduser()
            if root not in roots:
                roots.append(root)
    # Retain previously monitored profiles without assuming everybody has two accounts.
    names = set(server_map(portable)) | set(primary.get("mcpServers", {}))
    for project in primary.get("projects", {}).values():
        if isinstance(project, dict):
            names.update(project.get("mcpServers", {}))
    for candidate in sorted(home.glob(".claude-*")):
        label = "Claude " + candidate.name[len(".claude-"):].title()
        if candidate.is_dir() and any(connection_id(label, n) in known_ids for n in names) and candidate not in roots:
            roots.append(candidate)
    for root in roots:
        label = "Claude" if root == home / ".claude" else "Claude " + root.name.removeprefix(".claude-").title()
        data = primary if root == home / ".claude" else load(root / ".claude.json")
        if not root.exists() and not data:
            continue
        add(label, "User configuration", data.get("mcpServers", {}), client="Claude")
        project = {}
        for path, value in data.get("projects", {}).items():
            if path.replace("\\", "/").rstrip("/").casefold() == str(vault).replace("\\", "/").rstrip("/").casefold():
                project.update(value)
        disabled = project.get("disabledMcpServers", [])
        add(label, "Project .mcp.json", server_map(portable), disabled, client="Claude")
        add(label, "Project local configuration", project.get("mcpServers", {}), disabled, client="Claude")
        installed = load(root / "plugins/installed_plugins.json").get("plugins", {})
        enabled_plugins = load(root / "settings.json").get("enabledPlugins", {})
        enabled_plugins.update(load(vault / ".claude/settings.json").get("enabledPlugins", {}))
        for plugin, entries in installed.items():
            if not enabled_plugins.get(plugin):
                continue
            for entry in entries:
                if entry.get("scope") == "project" and str(entry.get("projectPath", "")).replace("\\", "/").casefold() != str(vault).replace("\\", "/").casefold():
                    continue
                directory = Path(entry.get("installPath", ""))
                content = load(directory / ".mcp.json")
                servers = content.get("mcpServers", content)
                for cfg in servers.values():
                    if isinstance(cfg, dict):
                        cfg.setdefault("env", {})["CLAUDE_PLUGIN_ROOT"] = str(directory)
                add(label, "Plugin: " + plugin, {plugin + ":" + n: c for n, c in servers.items()}, client="Claude")
    codex_root = Path(env.get("CODEX_HOME") or home / ".codex")
    for path, source in ((codex_root / "config.toml", "User config.toml"),
                         (vault / ".codex/config.toml", "Project config.toml")):
        add("Codex", source, server_map(load(path)))
    if os.name == "nt":
        editor_root = Path(env.get("APPDATA") or home / "AppData/Roaming") / "Code/User"
    elif __import__("sys").platform == "darwin":
        editor_root = home / "Library/Application Support/Code/User"
    else:
        editor_root = Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "Code/User"
    for client, user_rel, project_rel in JSON_CLIENTS:
        user_file = home / user_rel if user_rel else editor_root / "mcp.json"
        for path, source in ((user_file, "User MCP configuration"), (vault / project_rel, "Project MCP configuration")):
            add(client, source, server_map(load(path)))
    for path in env.get("SHUKI_MCP_CONFIG_FILES", "").split(os.pathsep):
        if path:
            extra_sources = (*extra_sources, ("Other client", Path(path).expanduser()))
    for label, path in extra_sources:
        path = Path(path)
        runtime = label + " " + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:8]
        add(runtime, path.name, server_map(load(path)), client=label)
    return rows, errors


def google_files(row, home=None):
    env = dict(os.environ)
    env.update(row["config"].get("env", {}))
    base = Path(env.get("XDG_CONFIG_HOME") or Path(home or Path.home()) / ".config")
    token = Path(env.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH") or base / "google-calendar-mcp/tokens.json")
    client = env.get("GOOGLE_OAUTH_CREDENTIALS")
    return token, Path(client) if client else None


def credentials(row, home=None):
    """Expose only expiry metadata. Refreshable access expiry is not a disconnection."""
    if not google_adapter(row):
        return {"auth": "Provider authentication not verified", "access_expires": None}
    path, _ = google_files(row, home)
    try:
        data = read_config(path)
        records = [data] if "access_token" in data else list(data.values())
        records = [r for r in records if isinstance(r, dict)]
        if not records or not any(r.get("access_token") or r.get("refresh_token") for r in records):
            return {"auth": "Credentials missing — reconnect in the MCP client", "auth_problem": True}
        expiries = [stamp(r.get("expiry_date")) for r in records if r.get("expiry_date")]
        refresh = all(bool(r.get("refresh_token")) for r in records)
        return {"auth": "Refresh token present; provider acceptance not verified" if refresh else "Access token only",
                "refreshable": refresh, "access_expires": min(expiries) if expiries else None}
    except (ValueError, OSError, TypeError):
        return {"auth": "Credentials unreadable — check the MCP client", "auth_problem": True}


class ProbeError(Exception):
    def __init__(self, status, message, stop=False):
        super().__init__(message)
        self.status, self.stop = status, stop


def google_adapter(row):
    cfg = row["config"]
    return (row["name"] == "google-calendar" or "GOOGLE_CALENDAR_MCP_TOKEN_PATH" in cfg.get("env", {})
            or any("google-calendar-mcp" in str(x) for x in [cfg.get("command", ""), *cfg.get("args", [])]))


def probe_google_auth(row):
    """Validate the existing Google refresh grant without reading Calendar data or saving tokens."""
    token_path, client_path = google_files(row)
    if not client_path:
        return {"auth": "OAuth client path unavailable; provider access unverified"}
    client_data = read_config(client_path)
    client = client_data.get("installed", client_data.get("web", {}))
    if not client.get("client_id") or not client.get("client_secret"):
        raise ProbeError("auth_required", "OAuth client credentials are missing or unsupported.", True)
    data = read_config(token_path)
    records = [data] if "access_token" in data else list(data.values())
    if not records:
        raise ProbeError("auth_required", "Google credentials are missing.", True)
    expiries = []
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    for record in records:
        if not isinstance(record, dict) or not record.get("refresh_token"):
            return {"auth": "Refresh grant unavailable; provider access unverified"}
        body = urllib.parse.urlencode({"client_id": client["client_id"], "client_secret": client["client_secret"],
                                       "refresh_token": record["refresh_token"], "grant_type": "refresh_token"}).encode()
        request = urllib.request.Request("https://oauth2.googleapis.com/token", body,
                                         {"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                value = json.loads(response.read(LIMIT))
                if not value.get("access_token"):
                    raise ProbeError("auth_required", "Google did not accept the refresh grant.", True)
                remaining = value.get("refresh_token_expires_in")
                if isinstance(remaining, (int, float)):
                    expiries.append(time.time() + remaining)
        except urllib.error.HTTPError as error:
            error.close()
            status = "rate_limited" if error.code == 429 else "auth_required" if error.code in (400, 401, 403) else "unavailable"
            raise ProbeError(status, f"Google OAuth HTTP {error.code}; reconnect or check the provider.", True) from None
    return {"auth": "Google refresh grant verified; Calendar permissions not tested",
            "provider_expires": min(expiries) if expiries else None}


def rpc_result(value, identity):
    if value.get("id") != identity:
        return None
    if "error" in value:
        # Inspect privately; never persist provider error text, which may contain secrets.
        message = str(value["error"]).lower()
        auth = any(x in message for x in ("unauthorized", "invalid_grant", "expired", "forbidden", "401", "403"))
        raise ProbeError("auth_required" if auth else "unavailable",
                         "Reconnect in the MCP client." if auth else "MCP returned a protocol error.", auth)
    if not isinstance(value.get("result"), dict):
        raise ProbeError("unavailable", "Invalid MCP response.")
    return value["result"]


def probe_stdio(cfg, cwd):
    command = shutil.which(cfg.get("command", ""))
    if not command:
        raise ProbeError("unavailable", "Configured executable is missing.", True)
    args = cfg.get("args", [])
    if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise ProbeError("unavailable", "Invalid command arguments.", True)
    argv = [command, *args]
    if Path(command).stem.lower() == "cmd":
        # Accept the common `cmd /c npx ...` launcher without executing a shell.
        if len(args) < 2 or args[0].lower() != "/c" or args[1].lower() not in {"npx", "npm"}:
            raise ProbeError("unsupported", "Shell command checks require a native executable.", True)
        command = shutil.which(args[1])
        if not command:
            raise ProbeError("unavailable", "Configured npm launcher is missing.", True)
        args = args[2:]
        argv = [command, *args]
    if Path(command).suffix.lower() in {".cmd", ".bat"}:
        # Avoid cmd.exe argument injection. npx/npm have a native Node entry point.
        entry = Path(command).parent / "node_modules/npm/bin" / (Path(command).stem + "-cli.js")
        node = shutil.which("node")
        if Path(command).stem.lower() not in {"npx", "npm"} or not entry.exists() or not node:
            raise ProbeError("unsupported", "Batch launcher checks are unsupported; use a native executable.", True)
        argv = [node, str(entry), *args]
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in cfg.get("env", {}).items()})
    if any("${" in x for x in argv + list(env.values())):
        raise ProbeError("unsupported", "Client variable expansion requires checking in the MCP client.", True)
    proc = subprocess.Popen(argv, cwd=cfg.get("cwd", str(cwd)), env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                            start_new_session=os.name != "nt")
    messages = queue.Queue(maxsize=128)

    def reader():
        while True:
            line = proc.stdout.readline(LIMIT + 1)
            if not line:
                break
            if len(line) > LIMIT:
                break
            try:
                messages.put(json.loads(line), timeout=0.1)
            except (ValueError, queue.Full):
                break
        try:
            messages.put(None, timeout=0.1)
        except queue.Full:
            pass

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.monotonic() + STDIO_TIMEOUT

    def send(method, identity=None, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if identity is not None:
            message["id"] = identity
        if params is not None:
            message["params"] = params
        proc.stdin.write(json.dumps(message).encode() + b"\n")
        proc.stdin.flush()
        if identity is None:
            return
        while True:
            try:
                item = messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise ProbeError("unavailable", "MCP check timed out.") from None
            if not isinstance(item, dict):
                raise ProbeError("unavailable", "MCP exited before replying.")
            result = rpc_result(item, identity)
            if result is not None:
                return result
            if time.monotonic() >= deadline:
                raise ProbeError("unavailable", "MCP check timed out.")
    try:
        send("initialize", 1, INIT)
        send("notifications/initialized")
        result = send("tools/list", 2, {})
        if not isinstance(result.get("tools"), list):
            raise ProbeError("unavailable", "MCP did not return its tool list.")
    finally:
        if os.name == "nt" and proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        elif os.name != "nt":
            import signal
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout):
            stream.close()


def probe_http(cfg):
    if cfg.get("type") == "sse":
        raise ProbeError("unsupported", "Legacy SSE requires checking in the MCP client.", True)
    headers = dict(cfg.get("headers", cfg.get("http_headers", {})))
    for key, env in cfg.get("env_http_headers", {}).items():
        if os.environ.get(env):
            headers[key] = os.environ[env]
    if cfg.get("bearer_token_env_var"):
        token = os.environ.get(cfg["bearer_token_env_var"])
        if not token:
            raise ProbeError("auth_required", "Bearer token environment variable is missing.", True)
        headers["Authorization"] = "Bearer " + token
    supplied_auth = bool(headers)
    headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect())
    deadline = time.monotonic() + TIMEOUT

    def send(method, identity=None, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if identity is not None:
            message["id"] = identity
        if params is not None:
            message["params"] = params
        req = urllib.request.Request(cfg["url"], json.dumps(message).encode(), headers, method="POST")
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError("unavailable", "MCP check timed out.")
            with opener.open(req, timeout=remaining) as response:
                if response.headers.get("Mcp-Session-Id"):
                    headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
                if identity is None:
                    return
                streaming = "text/event-stream" in response.headers.get("Content-Type", "")
                body, size = b"", 0
                while True:
                    if time.monotonic() >= deadline:
                        raise ProbeError("unavailable", "MCP check timed out.")
                    chunk = response.read1(4096)
                    size += len(chunk)
                    if size > LIMIT:
                        raise ProbeError("unavailable", "MCP response exceeded the check limit.")
                    body += chunk
                    if streaming:
                        body = body.replace(b"\r\n", b"\n")
                        while b"\n\n" in body:
                            frame, body = body.split(b"\n\n", 1)
                            data = b"\n".join(line[5:].lstrip() for line in frame.splitlines() if line.startswith(b"data:"))
                            if data:
                                result = rpc_result(json.loads(data), identity)
                                if result is not None:
                                    return result
                    if not chunk:
                        if streaming:
                            raise ProbeError("unavailable", "No matching MCP response.")
                        return rpc_result(json.loads(body), identity)
        except urllib.error.HTTPError as exc:
            exc.close()
            auth = exc.code in (401, 403)
            if auth and not supplied_auth:
                raise ProbeError("unsupported", "The monitor has no HTTP credentials; verify client-managed OAuth in the MCP client.", True) from None
            raise ProbeError("auth_required" if auth else "rate_limited" if exc.code == 429 else "unavailable",
                             f"HTTP {exc.code}; " + ("reconnect in the MCP client." if auth else "check the provider."),
                             auth or exc.code == 429) from None

    initialized = send("initialize", 1, INIT)
    if not initialized:
        raise ProbeError("unavailable", "Invalid initialization response.")
    headers["MCP-Protocol-Version"] = initialized.get("protocolVersion", INIT["protocolVersion"])
    send("notifications/initialized")
    result = send("tools/list", 2, {})
    if not result or not isinstance(result.get("tools"), list):
        raise ProbeError("unavailable", "MCP did not return its tool list.")


def probe(row):
    try:
        auth = probe_google_auth(row) if google_adapter(row) else {}
        if row["transport"] == "stdio":
            probe_stdio(row["config"], shuki_paths.VAULT)
        else:
            probe_http(row["config"])
        return {"health": "reachable", "detail": "Initialize and tool list succeeded; tool permissions were not tested.", **auth}
    except ProbeError as exc:
        return {"health": exc.status, "detail": str(exc), "stop": exc.stop}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return {"health": "unavailable", "detail": "Connection check failed; inspect the MCP client."}


def display_status(row):
    if not row.get("enabled", True):
        return "disabled", "Disabled"
    if row.get("paused"):
        return "paused", "Paused"
    if row.get("auth_problem") or row.get("health") == "auth_required":
        return "attention", "Sign-in needed"
    if row.get("health") == "unavailable":
        return "attention", "Unavailable"
    if row.get("expiry_state") in {"expired", "expiring"}:
        return "attention", "Expiry warning"
    if row.get("health") == "rate_limited":
        return "attention", "Rate limited"
    if row.get("health") == "reachable":
        return "checked", "Checked"
    return "unverified", "Not checked"


def group_connections(rows):
    """One compact service row; all distinct client configurations remain in its details."""
    groups = {}
    order = {"attention": 0, "unverified": 1, "checked": 2, "paused": 3, "disabled": 4}
    for row in rows:
        name = row["name"].casefold()
        group = groups.setdefault(name, {"id": "mcp-" + hashlib.sha256(name.encode()).hexdigest()[:16],
                                        "name": row["name"], "members": []})
        group["members"].append(dict(row))
    for group in groups.values():
        members = group["members"]
        states = [display_status(m) for m in members]
        group["status"], group["status_label"] = min(states, key=lambda s: order[s[0]])
        active = [m for m in members if m.get("enabled", True) and not m.get("paused")]
        expiries = [m["expires_at"] for m in active if m.get("expires_at")]
        group["expires_at"] = min(expiries) if expiries else None
        reminders = {m.get("reminder", "") for m in members}
        group["reminder"] = reminders.pop() if len(reminders) == 1 else ""
        group["clients"] = sorted({m.get("client", "Claude" if m["runtime"].startswith("Claude") else m["runtime"]) for m in members})
        group["label"] = re.sub(r"[-_]", " ", group["name"]).title()
    return sorted(groups.values(), key=lambda g: (order[g["status"]], g["label"].casefold()))


class Monitor:
    def __init__(self, path=None, discover=inventory, checker=probe, auth=credentials, notice=None):
        self.path = Path(path or STATE_PATH)
        self.discover, self.checker, self.auth, self.notice = discover, checker, auth, notice or notify
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.thread = None
        self.load_error = ""
        try:
            self.state = read_config(self.path)
            if not all(isinstance(x, dict) for x in self.state.values()):
                raise ValueError("Invalid monitoring state")
        except (OSError, ValueError):
            self.state = {}
            self.load_error = "MCP monitoring state is unreadable. Repair runner_state/mcp-health.json, then restart SHUKI."
        self.rows = []
        self.initialized = False
        self.errors = [self.load_error] if self.load_error else []

    def save(self):
        notices.atomic_json(self.path, self.state)

    def tick(self, now=None, checks=True):
        if self.load_error:
            return
        now = time.time() if now is None else now
        rows, errors = self.discover()
        checked = {}
        with self.lock:
            self.errors = errors
            if errors:
                fingerprint = hashlib.sha256(json.dumps(errors).encode()).hexdigest()[:20]
                if self.state.get("_inventory", {}).get("alert") != fingerprint:
                    self.lock.release()
                    try:
                        self.notice("mcp:inventory:" + fingerprint, "MCP inventory needs attention",
                                    "Some connection configurations cannot be read. Open Settings → MCP connections; check file permissions and syntax.", kind="blocker")
                    finally:
                        self.lock.acquire()
                    self.state["_inventory"] = {"alert": fingerprint}
            else:
                self.state.pop("_inventory", None)
            output = []
            service_alerts = {}
            for row in rows:
                key = row["id"]
                state = self.state.setdefault(key, {})
                cfg_hash = hashlib.sha256(json.dumps(row["config"], sort_keys=True).encode()).hexdigest()
                if state.get("config_hash") != cfg_hash:
                    state.update(config_hash=cfg_hash, failures=0, stopped=False, checked_at=0, health="unknown")
                    state.pop("auth", None)
                    state.pop("provider_expires", None)
                public = {k: v for k, v in row.items() if k != "config"}
                public.update(self.auth(row))
                if public.get("auth_problem"):
                    state.update(stopped=True, health="auth_required", detail=public["auth"])
                paused = state.get("paused", False)
                public.update(paused=paused, reminder=state.get("reminder", ""), stopped=state.get("stopped", False))
                if checks and row["enabled"] and not paused and not state.get("stopped") and now - state.get("checked_at", 0) >= INTERVAL:
                    # Allow status reads and controls while a slow MCP starts up.
                    self.lock.release()
                    try:
                        if cfg_hash not in checked:
                            checked[cfg_hash] = self.checker(row)
                        result = checked[cfg_hash]
                    finally:
                        self.lock.acquire()
                    state.update(result, checked_at=now)
                    state["failures"] = 0 if result["health"] == "reachable" else state.get("failures", 0) + 1
                    state["stopped"] = bool(result.get("stop") or state["failures"] >= 2)
                public.update({k: state[k] for k in ("health", "detail", "checked_at", "stopped", "auth") if k in state})
                public.setdefault("health", "unknown")
                expiries = [x for x in (stamp(state.get("reminder")), state.get("provider_expires"),
                                       None if public.get("refreshable") else public.get("access_expires")) if x]
                expiry = min(expiries) if expiries else None
                alert = ""
                alert_key = ""
                if row["enabled"] and not paused:
                    if public.get("auth_problem"):
                        alert = "Credentials require attention. Reconnect in your MCP client."
                        alert_key = "auth_required"
                    elif public["health"] in {"auth_required", "rate_limited", "unavailable"}:
                        # A single startup timeout is evidence in Settings, not yet a blocker.
                        if public["health"] != "unavailable" or state.get("stopped") or state.get("failures", 0) >= 2:
                            alert = public.get("detail", "Connection unavailable.")
                            alert_key = public["health"]
                    elif expiry and expiry <= now + WARNING:
                        alert = "Credential expiry reminder has passed." if expiry <= now else "Credentials expire within seven days."
                        alert_key = ("expired:" if expiry <= now else "expiring:") + state.get("reminder", "")
                public["expiry_state"] = "expired" if expiry and expiry <= now else "expiring" if expiry and expiry <= now + WARNING else "unknown" if not expiry else "valid"
                public["expires_at"] = expiry
                if alert:
                    service_alerts.setdefault(row["name"].casefold(), []).append((alert_key, row["runtime"], alert))
                output.append(public)
            for group in group_connections(output):
                state = self.state.setdefault("_service:" + group["id"], {})
                alerts = service_alerts.get(group["name"].casefold(), [])
                if alerts:
                    # Stable service/category identity survives detail changes and client differences.
                    fingerprint = hashlib.sha256(json.dumps(sorted({a[0] for a in alerts})).encode()).hexdigest()
                    if state.get("alert") != fingerprint:
                        event = f"mcp:{group['id']}:{state.get('episode', 0)}:{fingerprint}"
                        clients = ", ".join(sorted({a[1] for a in alerts}))
                        self.lock.release()
                        try:
                            self.notice(event, "MCP attention: " + group["name"],
                                        f"{clients}: {alerts[0][2]} Open Settings → MCP connections.", kind="blocker")
                        finally:
                            self.lock.acquire()
                        state["alert"] = fingerprint
                else:
                    active = [m for m in group["members"] if m.get("enabled", True) and not m.get("paused")]
                    if active and all(m["health"] in {"reachable", "unsupported"} and not m.get("auth_problem")
                                      and m["expiry_state"] not in {"expired", "expiring"} for m in active):
                        if state.pop("alert", None):
                            state["episode"] = state.get("episode", 0) + 1
                        # Retire legacy per-client markers only after observed recovery.
                        for member in active:
                            self.state[member["id"]].pop("alert", None)
            self.rows = output
            self.initialized = True
            self.save()

    def public(self):
        with self.lock:
            return {"connections": list(self.rows), "issues": list(self.errors),
                    "groups": group_connections(self.rows),
                    "initialized": self.initialized,
                    "running": bool(self.thread and self.thread.is_alive()), "interval_seconds": INTERVAL,
                    "coverage": "Reads local MCP configuration. Cloud-only connections and private client sign-in stores may need checking in their app.",
                    "clients": list(CLIENT_HELP)}

    def update(self, payload):
        with self.lock:
            key = payload.get("id")
            targets = [r["id"] for r in self.rows if r["id"] == key]
            for group in group_connections(self.rows):
                if group["id"] == key:
                    targets = [m["id"] for m in group["members"]]
            if not targets:
                raise ValueError("Unknown MCP connection.")
            changes = {}
            if "paused" in payload:
                if not isinstance(payload["paused"], bool):
                    raise ValueError("paused must be a boolean.")
                changes["paused"] = payload["paused"]
            if "reminder" in payload:
                value = payload["reminder"]
                if not isinstance(value, str) or len(value) > 10:
                    raise ValueError("Use an expiry reminder date: YYYY-MM-DD.")
                if value:
                    datetime.strptime(value, "%Y-%m-%d")
                changes["reminder"] = value
            if payload.get("retry"):
                changes.update(stopped=False, failures=0, checked_at=0)
            for target in targets:
                self.state.setdefault(target, {}).update(changes)
            self.save()
        self.wake.set()
        return {"ok": True, "queued": bool(payload.get("retry"))}

    def start(self):
        if self.load_error:
            try:
                self.notice("mcp:state-unreadable", "MCP monitoring stopped", self.load_error, kind="blocker")
            except Exception:
                pass  # The Settings warning remains visible even when the inbox is unavailable.
            return
        if self.thread and self.thread.is_alive():
            return
        def run():
            while True:
                try:
                    self.tick()
                except Exception:
                    with self.lock:
                        self.errors = ["MCP monitoring stopped: cannot read or save state. Check local permissions and configuration."]
                    try:
                        self.notice("mcp:monitor-stopped", "MCP monitoring stopped", self.errors[0], kind="blocker")
                    except Exception:
                        pass  # A failed inbox write cannot be retried safely in this worker.
                    return
                self.wake.wait(60)
                self.wake.clear()
        self.thread = threading.Thread(target=run, name="mcp-health", daemon=True)
        self.thread.start()


SERVICE = None


def notify(event, title, summary, kind="blocker"):
    path = notices.post_notice(event, title, summary, kind=kind)
    try:
        notices.deliver_pending(only=path)
    except Exception:
        # Delivery persists its own blocker; no repeat network attempts in this episode.
        pass
    return path


def service():
    global SERVICE
    if SERVICE is None:
        SERVICE = Monitor()
    return SERVICE


def settings_html():
    return '''<details class="card settings-group" id="mcp-settings">
<summary>MCP connections</summary><div class="settings-body">
<p id="mcp-summary" role="status" aria-live="polite">Loading connection status…</p>
<div class="mcp-columns" aria-hidden="true"><span>MCP</span><span>Status</span><span>Expires</span><span>Used by</span><span></span></div>
<div id="mcp-list"></div>
<p class="hint">Connection problems and expiry warnings appear in <a href="/notifications">Notifications</a>.</p>
<details class="mcp-help"><summary>About checks and supported apps</summary>
<p class="hint">Checks run every 15 minutes while SHUKI is running. “Checked” means the MCP responded. Service permissions may still need verification. An unavailable automatic check is shown as “Not checked”.</p>
<p class="hint">Expiry warnings start seven days ahead. “Not provided” means the provider has not shared an expiry date; you can add a reminder. Normal access-token renewal is handled separately.</p>
<p class="hint">Local configuration: Claude, Codex, Cursor and VS Code. Other apps can use the same monitor through their existing MCP configuration file.</p>
<p id="mcp-coverage" class="hint"></p>
</details>
</div></details>
<style>
#mcp-settings .mcp-columns,#mcp-settings .mcp-row>summary{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) minmax(0,.9fr) minmax(0,1fr) 16px;gap:12px;align-items:center}
#mcp-settings .mcp-columns{font-size:12px;color:var(--muted);padding:0 0 6px}
#mcp-settings .mcp-row{border-top:1px solid var(--line);margin:0}
#mcp-settings .mcp-row>summary{list-style:none;cursor:pointer;padding:12px 0;font-size:13px;line-height:1.5;font-weight:400}
#mcp-settings .mcp-row>summary::-webkit-details-marker{display:none}
#mcp-settings .mcp-row>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#mcp-settings .mcp-row>summary>*{min-width:0;overflow-wrap:anywhere}
#mcp-settings .mcp-name{font-weight:600;color:var(--fg)}
#mcp-settings .mcp-expiry,#mcp-settings .mcp-clients{color:var(--muted);font-size:12px}
#mcp-settings [data-state="attention"]{color:var(--danger,var(--red))}
#mcp-settings [data-state="checked"]{color:var(--ok,var(--teal))}
#mcp-settings [data-state="unverified"],#mcp-settings [data-state="paused"],#mcp-settings [data-state="disabled"]{color:var(--muted)}
#mcp-settings .mcp-chevron{color:var(--muted);width:14px;height:14px;line-height:14px;text-align:center;justify-self:end;align-self:center}
#mcp-settings .mcp-row[open]>summary .mcp-chevron{transform:rotate(90deg)}
#mcp-settings .mcp-body{padding:0 0 12px}
#mcp-settings .mcp-actions{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 8px}
#mcp-settings .mcp-reminder{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}
#mcp-settings .mcp-reminder input{max-width:100%;min-width:0}
#mcp-settings .mcp-member{display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap;font-size:12px;padding:6px 0}
#mcp-settings .mcp-help,#mcp-settings .mcp-diagnostics{margin:10px 0;font-size:12px;color:var(--muted)}
#mcp-settings .mcp-mobile-label{display:none}
@media(max-width:600px){
 #mcp-settings .mcp-columns{display:none}
 #mcp-settings .mcp-row>summary{grid-template-columns:minmax(0,1fr) minmax(0,1fr) 14px;gap:2px 10px}
 #mcp-settings .mcp-name{grid-column:1;grid-row:1}
 #mcp-settings .mcp-status{grid-column:2;grid-row:1}
 #mcp-settings .mcp-expiry{grid-column:1;grid-row:2}
 #mcp-settings .mcp-clients{grid-column:2;grid-row:2}
 #mcp-settings .mcp-chevron{grid-column:3;grid-row:1/3}
 #mcp-settings .mcp-mobile-label{display:inline}
}
</style>
<script>
(() => {
const root=document.getElementById('mcp-list'), status=document.getElementById('mcp-summary');
const opened=new Set();
root.addEventListener('toggle',e=>{if(e.target.classList.contains('mcp-row')){if(e.target.open)opened.add(e.target.dataset.id);else opened.delete(e.target.dataset.id);}},true);
function element(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
function button(text,action){const b=element('button',text);b.type='button';b.className='hbtn';b.onclick=action;return b;}
async function change(payload){
 try {
  const cfg=await (await fetch('/push/config')).json();
  const r=await fetch('/connections/update',{method:'POST',headers:{'Content-Type':'application/json','X-SHUKI-Push':cfg.csrf},body:JSON.stringify(payload)});
  const result=await r.json();if(!r.ok)throw new Error(result.error||'Could not save');
  status.textContent=payload.retry?'Check queued; waiting for results…':'Saved.';
  setTimeout(()=>{if(!root.contains(document.activeElement)||document.activeElement.tagName!=='INPUT')load();},1000);
 }catch(e){status.textContent=e.message;}
}
async function load(){
 try {
  const r=await fetch('/connections/data');if(!r.ok)throw new Error('Cannot load connection status.');
  const data=await r.json(), groups=data.groups||[];root.replaceChildren();
  const attention=groups.filter(x=>x.status==='attention');
  status.textContent=data.issues.length?data.issues.join(' '):!data.running?'Automatic monitoring is stopped.':!groups.length?data.initialized?'No configured MCPs found.':'Scanning connections…':attention.length?attention.length+' need attention.':'Select an MCP for details.';
  document.querySelector('#mcp-settings > summary').textContent='MCP connections'+(groups.length?' · '+groups.length:'')+(data.issues.length||!data.running?' · Monitoring stopped':attention.length?' · Needs attention':'');
  groups.forEach(g=>{
   const item=element('details');item.className='mcp-row';item.dataset.id=g.id;item.open=opened.has(g.id);
   const summary=element('summary'),name=element('span',g.label),state=element('span',g.status_label),expiry=element('span'),clients=element('span'),chevron=element('span','›');
   name.className='mcp-name';state.className='mcp-status';state.dataset.state=g.status;
   expiry.className='mcp-expiry';clients.className='mcp-clients';chevron.className='mcp-chevron';chevron.setAttribute('aria-hidden','true');
   const exLabel=element('span','Expires: '),clientLabel=element('span','Used by: ');exLabel.className=clientLabel.className='mcp-mobile-label';
   expiry.append(exLabel,document.createTextNode(g.expires_at?new Date(g.expires_at*1000).toLocaleDateString():'Not provided'));
   clients.append(clientLabel,document.createTextNode(g.clients.join(', ')));summary.append(name,state,expiry,clients,chevron);item.append(summary);
   summary.setAttribute('aria-label',g.label+', '+g.status_label+', expires '+(g.expires_at?new Date(g.expires_at*1000).toLocaleDateString():'not provided')+', used by '+g.clients.join(', '));
   const body=element('div');body.className='mcp-body';const actions=element('div');actions.className='mcp-actions';
   const paused=g.members.every(x=>x.paused),check=button('Check now',()=>change({id:g.id,retry:true}));check.disabled=!g.members.some(x=>x.enabled&&!x.paused);
   actions.append(check,button(paused?'Resume monitoring':'Pause monitoring',()=>change({id:g.id,paused:!paused})));body.append(actions);
   const line=element('div');line.className='mcp-reminder';const label=element('label','Expiry reminder '),input=element('input');input.type='date';input.value=g.reminder||'';label.append(input);
   line.append(label,button('Save reminder',()=>change({id:g.id,reminder:input.value})));body.append(line,element('p','Controls apply to all clients listed below.'));
   g.members.forEach(x=>{
    const member=element('div');member.className='mcp-member';const client=element('span',x.runtime),statusText=element('span',!x.enabled?'Disabled':x.paused?'Paused':x.health==='reachable'?'Checked':x.health==='auth_required'?'Sign-in needed':x.health==='unavailable'?'Unavailable':x.health==='rate_limited'?'Rate limited':'Not checked');
    member.append(client,statusText);body.append(member);
   });
   const diagnostics=element('details');diagnostics.className='mcp-diagnostics';diagnostics.append(element('summary','Check details and app setup'));
   g.members.forEach(x=>{
    diagnostics.append(element('p',x.runtime+' · '+x.source+' · Last check: '+(x.checked_at?new Date(x.checked_at*1000).toLocaleString():'Not checked')));
    if(x.auth)diagnostics.append(element('p',x.auth));if(x.detail)diagnostics.append(element('p',x.detail));
    if(x.stopped)diagnostics.append(element('p','Automatic checks stopped. After fixing the issue, use Check now.'));
    if(x.help_url){const help=element('a','Configure '+(x.client||x.runtime));help.href=x.help_url;help.target='_blank';help.rel='noopener noreferrer';diagnostics.append(help);}
   });
   body.append(diagnostics);item.append(body);root.append(item);
  });
  document.getElementById('mcp-coverage').textContent=data.coverage;
 }catch(e){status.textContent=e.message;}
}
document.getElementById('mcp-settings').addEventListener('toggle',e=>{if(e.target.open)load();});
setInterval(()=>{if(!document.hidden&&!root.contains(document.activeElement))load();},15000);
load();
})();
</script>'''
