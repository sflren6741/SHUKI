"""Feature plugins: validate manifests, import only enabled plugins, route their requests.

Contract (design: 03_Projects/プロジェクト/AIイントラ公開（SHUKI）.md §Minimal plugin contract):
  - <scripts>/plugins/<id>/manifest.json declares the plugin; <entrypoint> defines register(api).
  - Manifests are read and validated without importing any plugin code. Activation comes from
    settings ({"<id>": {"enabled": false}}); a plugin is enabled unless switched off.
  - A disabled or invalid plugin contributes nothing: no routes, nav, assets or jobs. Its stored
    data is left untouched.
  - A plugin owns its declared top-level routes ("/quiz" covers /quiz and /quiz/...). It may only
    register handlers on those, and unhandled requests under them are answered 404 by the plugin.
  - Plugins depend on core only; `requires` lists plugin ids that must also be enabled.
  - A plugin may contribute one Home summary via page_summary(callback, after=<card key>).
  - Home widgets and named data providers are owned by the registering plugin.
  - Scheduled Python jobs use the existing runner definition in manifest.jobs, with an id.
  - A plugin may answer one shared ui-queue submission kind via queue_handler(name, source, callback).
  - on_start(callback) starts an owned background service once after the server binds.
"""
import importlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
VISIBILITIES = ("public", "private", "paid")
METHODS = ("GET", "POST")
_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")
_ROUTE_RE = re.compile(r"/[a-z0-9][a-z0-9_-]{0,31}")
_ENTRY_RE = re.compile(r"[a-z_][a-z0-9_]{0,31}\.py")
_SKILL_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_SCRIPT_RE = re.compile(r"[a-z_][a-z0-9_]*\.py")
_LIST_FIELDS = ("requires", "routes", "nav", "jobs", "migrations", "skills")


class PluginError(ValueError):
    pass


def _validate(manifest, folder):
    if not isinstance(manifest, dict):
        raise PluginError("manifest is not an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PluginError(f"unsupported schema_version {manifest.get('schema_version')!r}")
    pid = manifest.get("id")
    if not isinstance(pid, str) or not _ID_RE.fullmatch(pid) or pid != folder.name:
        raise PluginError("id must match the folder name and [a-z][a-z0-9_]*")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise PluginError("version must be a non-empty string")
    if manifest.get("visibility") not in VISIBILITIES:
        raise PluginError(f"visibility must be one of {', '.join(VISIBILITIES)}")
    entry = manifest.get("entrypoint")
    if not isinstance(entry, str) or not _ENTRY_RE.fullmatch(entry) or not (folder / entry).is_file():
        raise PluginError("entrypoint must name a .py file inside the plugin folder")
    for key in _LIST_FIELDS:
        if not isinstance(manifest.get(key, []), list):
            raise PluginError(f"{key} must be a list")
    for route in manifest.get("routes", []):
        if not isinstance(route, str) or not _ROUTE_RE.fullmatch(route):
            raise PluginError(f"route {route!r} must be one top-level segment like /quiz")
    for item in manifest.get("nav", []):
        if not (isinstance(item, dict) and all(isinstance(item.get(k), str) and item[k]
                                               for k in ("group", "key", "label", "href"))):
            raise PluginError("nav entries need string group, key, label and href")
        if not any(_owns(route, item["href"]) for route in manifest.get("routes", [])):
            raise PluginError(f"nav href {item['href']!r} is not one of the plugin's routes")
        if item.get("before") and item.get("after"):
            raise PluginError("nav cannot declare both before and after")
        for anchor in (item.get("before"), item.get("after")):
            if anchor is not None and (not isinstance(anchor, str) or not _ID_RE.fullmatch(anchor)):
                raise PluginError("nav anchors must be page keys")
    for dep in manifest.get("requires", []):
        if not isinstance(dep, str) or not _ID_RE.fullmatch(dep) or dep == pid:
            raise PluginError(f"invalid requirement {dep!r}")
    skills = manifest.get("skills", [])
    if any(not isinstance(skill, str) or not _SKILL_RE.fullmatch(skill) for skill in skills):
        raise PluginError("skills must be command names like crossword-gen")
    if len(skills) != len(set(skills)):
        raise PluginError("skills must not contain duplicate names")
    job_ids = set()
    for job in manifest.get("jobs", []):
        if not (isinstance(job, dict) and isinstance(job.get("id"), str)
                and _ID_RE.fullmatch(job["id"]) and job["id"] not in job_ids
                and all(isinstance(job.get(k), str) and job[k] for k in ("title", "log"))
                and _ID_RE.fullmatch(job["log"])):
            raise PluginError("jobs need a unique id, title and safe log name")
        job_ids.add(job["id"])
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            raise PluginError("jobs need non-empty Python steps")
        for step in steps:
            args = step.get("py") if isinstance(step, dict) else None
            if not (isinstance(args, list) and args and all(isinstance(a, str) for a in args)
                    and _SCRIPT_RE.fullmatch(args[0]) and (folder.parent.parent / args[0]).is_file()
                    and set(step) <= {"py", "label", "fatal"}
                    and isinstance(step.get("label", ""), str)
                    and isinstance(step.get("fatal", True), bool)):
                raise PluginError("job steps need an existing top-level Python entrypoint, label and optional fatal flag")


def _owns(route, path):
    return path == route or path.startswith(route + "/")


def read_manifests(plugins_dir=PLUGINS_DIR):
    """Valid manifests as {id: (manifest, folder)} plus readable errors. Imports no plugin code."""
    found, errors, owner, skill_owner, job_owner = {}, [], {}, {}, {}
    for path in sorted(Path(plugins_dir).glob("*/manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            _validate(manifest, path.parent)
        except (OSError, json.JSONDecodeError, PluginError) as exc:
            errors.append(f"{path.parent.name}: {exc}")
            continue
        clash = [r for r in manifest.get("routes", []) if r in owner]
        if clash:
            errors.append(f"{manifest['id']}: route {clash[0]} already owned by {owner[clash[0]]}")
            continue
        clash = [s for s in manifest.get("skills", []) if s in skill_owner]
        if clash:
            errors.append(f"{manifest['id']}: skill {clash[0]} already owned by {skill_owner[clash[0]]}")
            continue
        clash = [job["id"] for job in manifest.get("jobs", []) if job["id"] in job_owner]
        if clash:
            errors.append(f"{manifest['id']}: job {clash[0]} already owned by {job_owner[clash[0]]}")
            continue
        owner.update({r: manifest["id"] for r in manifest.get("routes", [])})
        skill_owner.update({s: manifest["id"] for s in manifest.get("skills", [])})
        job_owner.update({job["id"]: manifest["id"] for job in manifest.get("jobs", [])})
        found[manifest["id"]] = (manifest, path.parent)
    return found, errors


def enabled_ids(manifests, activation):
    """Ids that are switched on and whose requirements are also enabled (to a fixed point)."""
    activation = activation if isinstance(activation, dict) else {}

    def on(pid):
        state = activation.get(pid)
        return not (isinstance(state, dict) and state.get("enabled") is False)

    ids = {pid for pid in manifests if on(pid)}
    while True:
        kept = {pid for pid in ids if all(dep in ids for dep in manifests[pid][0].get("requires", []))}
        if kept == ids:
            return ids
        ids = kept


def scheduled_jobs(activation, reserved=(), plugins_dir=PLUGINS_DIR):
    """Return enabled manifests' runner definitions without importing plugin code.

    These are existing deterministic Python entrypoints, not Scheduler changes.
    Built-in job names remain reserved; an invalid plugin cannot contribute jobs.
    """
    manifests, errors = read_manifests(plugins_dir)
    jobs = {}
    for pid in sorted(enabled_ids(manifests, activation)):
        declared = manifests[pid][0].get("jobs", [])
        clash = [job["id"] for job in declared if job["id"] in reserved]
        if clash:
            errors.append(f"{pid}: job {clash[0]} is reserved by core")
            continue
        for job in declared:
            jobs[job["id"]] = {k: v for k, v in job.items() if k != "id"}
    return jobs, errors


class Registry:
    """Loaded plugins and their request handlers."""

    def __init__(self, errors=()):
        self.errors = list(errors)
        self.loaded = {}        # id -> manifest
        self._routes = {}       # route -> id
        self._handlers = {}     # (method, route) -> handler(req, path, query)
        self._skills = {}       # command -> owner, including disabled/absent owners
        self._summaries = []    # (owner, routes, callback, preceding card key)
        self._widgets = {}      # owner -> Home HTML callback
        self._data = {}         # (owner, name) -> data callback
        self._queue = {}        # (queue name, payload source) -> handler(req, payload)
        self._services = {}     # owner -> startup callback; never run during registration
        self._started = set()

    def start_services(self):
        """Start each enabled plugin's background service once; isolate failures."""
        for owner, callback in self._services.items():
            if owner in self._started:
                continue
            self._started.add(owner)
            try:
                callback()
            except Exception as exc:
                self.errors.append(f"{owner}: startup failed: {exc}")
                print(f"plugin service skipped: {owner}: {exc}", file=sys.stderr)

    def dispatch(self, req, method, path, query):
        """Answer a request owned by an enabled plugin. Returns False if no plugin owns the path."""
        route = next((r for r in self._routes if _owns(r, path)), None)
        if route is None:
            return False
        handler = self._handlers.get((method, route))
        if handler is None or not handler(req, path, query):
            req._respond(404, b"not found")
        return True

    def owns(self, path):
        return any(_owns(r, path) for r in self._routes)

    def skill_enabled(self, skill):
        owner = self._skills.get(skill)
        return owner is None or owner in self.loaded

    def page_summaries(self, cards):
        """Merge enabled plugins' cards; the first available anchor determines position.

        A failed callback or a card outside its owner's routes is skipped without
        interrupting the Home page. The caller's existing cards are left intact.
        """
        out = list(cards)
        for owner, routes, callback, after in self._summaries:
            try:
                card = callback()
                if not (isinstance(card, dict) and card.get("key") == owner
                        and all(isinstance(card.get(k), str)
                                for k in ("label", "href", "value", "sub", "tone"))
                        and any(_owns(route, card["href"].split("?", 1)[0].split("#", 1)[0])
                                for route in routes)):
                    continue
                keys = [c["key"] for c in out]
                if owner in keys:
                    continue
                anchors = (after,) if isinstance(after, str) else after or ()
                anchor = next((key for key in anchors if key in keys), None)
                pos = len(out) if after is None else keys.index(anchor) + 1 if anchor is not None else 0
                out.insert(pos, card)
            except Exception:
                continue
        return out

    def handle_queue(self, req, name, payload):
        """Let the owning plugin answer a shared ui-queue submission. False if none owns it."""
        handler = self._queue.get((name, payload.get("source")))
        if handler is None:
            return False
        handler(req, payload)
        return True

    def home_widget_html(self, owner):
        callback = self._widgets.get(owner)
        if callback is None:
            return ""
        try:
            value = callback()
            return value if isinstance(value, str) else ""
        except Exception:
            return ""

    def data(self, owner, name, default=None):
        callback = self._data.get((owner, name))
        if callback is None:
            return default
        try:
            return callback()
        except Exception:
            return default


class PluginAPI:
    """What a plugin's register(api) may use: core services and its own declared routes."""

    def __init__(self, registry, manifest, core):
        self._registry, self._manifest, self.core = registry, manifest, core

    def route(self, method, route, handler):
        if method not in METHODS:
            raise PluginError(f"unsupported method {method!r}")
        if route not in self._manifest.get("routes", []):
            raise PluginError(f"{self._manifest['id']} did not declare route {route!r}")
        self._registry._handlers[(method, route)] = handler

    def start_job(self, skill, text, **options):
        if skill not in self._manifest.get("skills", []):
            raise PluginError(f"{self._manifest['id']} did not declare skill {skill!r}")
        return self.core.start_job(skill, text, **options)

    def page_summary(self, callback, after=None):
        anchors = (after,) if isinstance(after, str) else after
        if not callable(callback) or (after is not None and (
                not isinstance(anchors, tuple) or not anchors
                or any(not isinstance(key, str) or not _ID_RE.fullmatch(key) for key in anchors))):
            raise PluginError("page_summary needs a callback and optional card keys")
        owner = self._manifest["id"]
        if any(item[0] == owner for item in self._registry._summaries):
            raise PluginError(f"{owner} already registered a page summary")
        self._registry._summaries.append((owner, tuple(self._manifest.get("routes", [])), callback, after))

    def home_widget(self, callback):
        owner = self._manifest["id"]
        if not callable(callback) or owner in self._registry._widgets:
            raise PluginError("home_widget needs one callback per owner")
        self._registry._widgets[owner] = callback

    def on_start(self, callback):
        owner = self._manifest["id"]
        if not callable(callback) or owner in self._registry._services:
            raise PluginError("on_start needs one callback per owner")
        self._registry._services[owner] = callback

    def data_provider(self, name, callback):
        key = (self._manifest["id"], name)
        if not (isinstance(name, str) and _ID_RE.fullmatch(name) and callable(callback)):
            raise PluginError("data_provider needs a safe name and callback")
        if key in self._registry._data:
            raise PluginError(f"{key[0]} already registered data provider {name}")
        self._registry._data[key] = callback

    def queue_handler(self, name, source, callback):
        key = (name, source)
        if not (isinstance(name, str) and _ID_RE.fullmatch(name) and isinstance(source, str)
                and _ID_RE.fullmatch(source) and callable(callback)):
            raise PluginError("queue_handler needs safe queue and source names and a callback")
        if key in self._registry._queue:
            raise PluginError(f"queue {name}/{source} already has a handler")
        self._registry._queue[key] = callback


def load(activation, core=None, add_nav=None, plugins_dir=PLUGINS_DIR, package="plugins", known_skills=None):
    """Import and register every enabled, valid plugin. Failures disable that plugin only."""
    manifests, errors = read_manifests(plugins_dir)
    registry = Registry(errors)
    registry._skills = dict(known_skills or {})
    for pid, (manifest, _folder) in tuple(manifests.items()):
        for skill in manifest.get("skills", []):
            if skill in registry._skills and registry._skills[skill] != pid:
                registry.errors.append(f"{pid}: skill {skill} is reserved for {registry._skills[skill]}")
                break
        else:
            registry._skills.update({skill: pid for skill in manifest.get("skills", [])})
            continue
        del manifests[pid]
    for pid in sorted(enabled_ids(manifests, activation)):
        manifest, _folder = manifests[pid]
        try:
            module = importlib.import_module(f"{package}.{pid}.{manifest['entrypoint'][:-3]}")
            staged = Registry()
            module.register(PluginAPI(staged, manifest, core))
        except Exception as exc:  # one broken plugin must not take the dashboard down
            registry.errors.append(f"{pid}: failed to load: {exc}")
            continue
        clash = [key for key in staged._queue if key in registry._queue]
        if clash:
            registry.errors.append(f"{pid}: queue {clash[0][0]}/{clash[0][1]} already has a handler")
            continue
        registry._handlers.update(staged._handlers)
        registry._summaries.extend(staged._summaries)
        registry._widgets.update(staged._widgets)
        registry._data.update(staged._data)
        registry._queue.update(staged._queue)
        registry._services.update(staged._services)
        registry._routes.update({r: pid for r in manifest.get("routes", [])})
        registry.loaded[pid] = manifest
        for item in manifest.get("nav", []):
            if add_nav:
                if item.get("before"):
                    add_nav(item["group"], item["key"], item["label"], item["href"], before=item["before"])
                else:
                    add_nav(item["group"], item["key"], item["label"], item["href"], item.get("after"))
    return registry
