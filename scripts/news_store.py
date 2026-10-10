"""News records: daily issues, seen URLs, article ratings and one-shot watches.

Storage is ``<data_dir>/news/news.db`` once the guarded migration activates it
(or on a fresh install). Until then the JSON files in ``99_System/news`` stay
authoritative and are read and written in their original formats. The
hand-edited ``feeds.json`` is configuration and always stays a file.

Watches are application data: the daily fetch closes them. In the database a
closed watch keeps its status (``hit``/``expired``) and the article it found
instead of disappearing. Add one with ``python news_store.py watch "<query>"``.

``import_legacy``/``export_legacy`` round-trip the legacy files exactly; the
migration's parity check compares their parsed content.
"""
import argparse
from contextlib import closing
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shuki_paths  # noqa: E402
from shuki_core import db as feature_db  # noqa: E402

KEY = "news/news.db"
LEGACY_DIR = shuki_paths.VAULT / "99_System" / "news"
LEGACY_FILES = ("seen_urls.json", "feedback.json", "watches.json")
ISSUE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
ISSUE_KEYS = {"date", "generated_at", "items", "knowledge_feature"}
ITEM_KEYS = ("url", "title", "source", "category", "published", "reason", "stars")
RATING_KEYS = ("value", "ts", "title", "category", "source")
RATING_VALUES = ("good", "bad", "skip")
WATCH_KEYS = {"id", "query", "status", "created", "expires"}
WATCH_DAYS = 30

MIGRATIONS = [[
    """CREATE TABLE issues (
        day TEXT PRIMARY KEY,
        generated_at TEXT,
        knowledge_feature TEXT)""",
    """CREATE TABLE issue_items (
        day TEXT NOT NULL REFERENCES issues(day) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        url TEXT NOT NULL,
        title TEXT, source TEXT, category TEXT, published TEXT, reason TEXT,
        stars INTEGER,
        PRIMARY KEY (day, position))""",
    "CREATE INDEX idx_issue_items_url ON issue_items(url)",
    """CREATE TABLE articles (
        url TEXT PRIMARY KEY,
        first_seen_on TEXT NOT NULL)""",
    """CREATE TABLE ratings (
        url TEXT PRIMARY KEY,
        value TEXT NOT NULL CHECK (value IN ('good', 'bad', 'skip')),
        rated_at TEXT,
        title TEXT, category TEXT, source TEXT)""",
    """CREATE TABLE watches (
        id TEXT PRIMARY KEY,
        query TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active', 'hit', 'expired')),
        created TEXT,
        expires TEXT,
        hit_url TEXT,
        closed_on TEXT)""",
]]


def _legacy_data(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return [path for path in sorted(folder.iterdir())
            if path.name in LEGACY_FILES or ISSUE_NAME.match(path.name)]


def database():
    """The News database path, or None while the legacy JSON files are authoritative."""
    return feature_db.feature_db(KEY, _legacy_data(LEGACY_DIR))


def connect(path=None):
    return feature_db.connect(path or database(), MIGRATIONS)


def _reader():
    path = database()
    if not path.exists():
        return None
    return feature_db.connect(path, MIGRATIONS, readonly=True)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


# ── Issues ─────────────────────────────────────────────────────────────────

def _issue_from_rows(meta, items):
    data = {"date": meta["day"]}
    if meta["generated_at"] is not None:
        data["generated_at"] = meta["generated_at"]
    data["items"] = [{k: row[k] for k in ITEM_KEYS if row[k] is not None} for row in items]
    if meta["knowledge_feature"] is not None:
        data["knowledge_feature"] = json.loads(meta["knowledge_feature"])
    return data


def _load_issue(conn, day):
    meta = conn.execute("SELECT * FROM issues WHERE day = ?", (day,)).fetchone()
    if meta is None:
        return None
    items = conn.execute("SELECT * FROM issue_items WHERE day = ? ORDER BY position", (day,))
    return _issue_from_rows(meta, items)


def issue_days():
    """Days that have an issue, newest first."""
    if database() is None:
        return sorted((p.stem for p in _legacy_data(LEGACY_DIR) if ISSUE_NAME.match(p.name)),
                      reverse=True)
    conn = _reader()
    if conn is None:
        return []
    with closing(conn):
        return [row[0] for row in conn.execute("SELECT day FROM issues ORDER BY day DESC")]


def read_issue(day):
    """One day's issue in its original shape, or None."""
    if database() is None:
        data = _read_json(LEGACY_DIR / f"{day}.json")
        return data if isinstance(data, dict) else None
    conn = _reader()
    if conn is None:
        return None
    with closing(conn):
        return _load_issue(conn, day)


def latest_issue():
    days = issue_days()
    return read_issue(days[0]) if days else None


def _put_issue(conn, data):
    day = data["date"]
    feature = data.get("knowledge_feature")
    conn.execute("DELETE FROM issues WHERE day = ?", (day,))
    conn.execute("INSERT INTO issues (day, generated_at, knowledge_feature) VALUES (?, ?, ?)",
                 (day, data.get("generated_at"),
                  None if feature is None else json.dumps(feature, ensure_ascii=False)))
    conn.executemany(
        "INSERT INTO issue_items (day, position, %s) VALUES (?, ?, %s)"
        % (", ".join(ITEM_KEYS), ", ".join("?" * len(ITEM_KEYS))),
        [(day, position, *(item.get(k) for k in ITEM_KEYS))
         for position, item in enumerate(data.get("items") or [])])


def work_path(day, news_dir):
    """Where the daily fetch (and the AI it runs) writes the issue while building it.

    With legacy storage this is the issue file itself. With the database it is a
    temporary file that ``commit_issue`` imports and removes.
    """
    news_dir = Path(news_dir)
    return news_dir / (f"{day}.json" if database() is None else f"_issue_tmp_{day}.json")


def commit_issue(day, path):
    """Store a finished issue from ``work_path``; a no-op for legacy storage."""
    path = Path(path)
    if database() is None or not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("issue file is not a JSON object")
    data["date"] = day
    with closing(connect()) as conn, feature_db.write(conn):
        _put_issue(conn, data)
    path.unlink()


# ── Seen URLs ──────────────────────────────────────────────────────────────

def load_seen():
    """url -> first day it was offered to the selector."""
    if database() is None:
        data = _read_json(LEGACY_DIR / "seen_urls.json")
        return data if isinstance(data, dict) else {}
    conn = _reader()
    if conn is None:
        return {}
    with closing(conn):
        return dict(conn.execute("SELECT url, first_seen_on FROM articles ORDER BY rowid"))


def save_seen(seen):
    """Replace the seen-URL set (the caller has already applied retention)."""
    path = database()
    if path is None:
        _write_json(LEGACY_DIR / "seen_urls.json", seen)
        return
    with closing(connect(path)) as conn, feature_db.write(conn):
        conn.execute("DELETE FROM articles")
        conn.executemany("INSERT INTO articles (url, first_seen_on) VALUES (?, ?)", seen.items())


# ── Ratings ────────────────────────────────────────────────────────────────

def _rating_dict(row):
    out = {"value": row["value"]}
    if row["rated_at"] is not None:
        out["ts"] = row["rated_at"]
    out.update({k: row[k] for k in ("title", "category", "source") if row[k] is not None})
    return out


def load_ratings():
    """url -> {value, ts, title, category, source}."""
    if database() is None:
        data = _read_json(LEGACY_DIR / "feedback.json")
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, dict) else {}
    conn = _reader()
    if conn is None:
        return {}
    with closing(conn):
        return {row["url"]: _rating_dict(row)
                for row in conn.execute("SELECT * FROM ratings ORDER BY rowid")}


def set_rating(url, entry, write_legacy):
    """Record one rating. ``write_legacy(path, entries)`` publishes the legacy file atomically."""
    if entry.get("value") not in RATING_VALUES:
        raise ValueError("rating must be good, bad or skip")
    path = database()
    if path is None:
        entries = load_ratings()
        entries[url] = entry
        write_legacy(LEGACY_DIR / "feedback.json", entries)
        return
    with closing(connect(path)) as conn, feature_db.write(conn):
        conn.execute(
            "INSERT INTO ratings (url, value, rated_at, title, category, source)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(url) DO UPDATE SET value = excluded.value,"
            " rated_at = excluded.rated_at, title = excluded.title,"
            " category = excluded.category, source = excluded.source",
            (url, entry["value"], entry.get("ts"), entry.get("title"),
             entry.get("category"), entry.get("source")))


# ── Watches ────────────────────────────────────────────────────────────────

def _watch_dict(row):
    out = {"id": row["id"], "query": row["query"], "status": row["status"]}
    out.update({k: row[k] for k in ("created", "expires") if row[k] is not None})
    return out


def load_watches():
    """Open watches in their legacy shape (the legacy file only ever holds open ones)."""
    if database() is None:
        data = _read_json(LEGACY_DIR / "watches.json")
        watches = data.get("watches") if isinstance(data, dict) else None
        return watches if isinstance(watches, list) else []
    conn = _reader()
    if conn is None:
        return []
    with closing(conn):
        return [_watch_dict(row) for row in conn.execute(
            "SELECT * FROM watches WHERE status = 'active' ORDER BY rowid")]


def close_watches(expired_ids, hits, today):
    """Close expired watches and those that found an article (``hits``: id -> url)."""
    if not expired_ids and not hits:
        return
    path = database()
    if path is None:
        gone = set(expired_ids) | set(hits)
        _write_json(LEGACY_DIR / "watches.json",
                    {"watches": [w for w in load_watches() if w.get("id") not in gone]})
        return
    with closing(connect(path)) as conn, feature_db.write(conn):
        conn.executemany("UPDATE watches SET status = 'expired', closed_on = ? WHERE id = ?",
                         [(today, watch_id) for watch_id in expired_ids])
        conn.executemany("UPDATE watches SET status = 'hit', hit_url = ?, closed_on = ? WHERE id = ?",
                         [(url, today, watch_id) for watch_id, url in hits.items()])


def add_watch(query, expires=None, today=None):
    """Open a one-shot watch; the daily fetch checks it until it hits or expires."""
    query = (query or "").strip()
    if not query:
        raise ValueError("a watch needs a query")
    today = today or date.today().isoformat()
    expires = expires or (date.fromisoformat(today) + timedelta(days=WATCH_DAYS)).isoformat()
    date.fromisoformat(expires)
    path = database()
    if path is None:
        watches = load_watches()
        used = [w.get("id", "") for w in watches]
    else:
        with closing(connect(path)) as conn:
            used = [row[0] for row in conn.execute("SELECT id FROM watches")]
    number = max([int(m.group(1)) for i in used if (m := re.fullmatch(r"w(\d+)", i or ""))] + [0]) + 1
    watch = {"id": f"w{number}", "query": query, "status": "active",
             "created": today, "expires": expires}
    if path is None:
        _write_json(LEGACY_DIR / "watches.json", {"watches": watches + [watch]})
    else:
        with closing(connect(path)) as conn, feature_db.write(conn):
            conn.execute("INSERT INTO watches (id, query, status, created, expires)"
                         " VALUES (?, ?, 'active', ?, ?)", (watch["id"], query, today, expires))
    return watch


# ── Conversion and rollback (used by runtime_data_migrate.py) ──────────────

def legacy_records(folder):
    """Strictly parse the legacy News data files in ``folder`` (feeds.json excluded)."""
    folder = Path(folder)
    issues = {}
    for path in _legacy_data(folder):
        if not ISSUE_NAME.match(path.name):
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(data, dict) or set(data) - ISSUE_KEYS or data.get("date") != path.stem
                or not isinstance(data.get("items"), list)
                or any(not isinstance(i, dict) or set(i) - set(ITEM_KEYS) or "url" not in i
                       for i in data["items"])):
            raise ValueError("unexpected issue format: " + path.name)
        issues[path.stem] = data
    seen = _strict(folder / "seen_urls.json", {})
    if any(not isinstance(v, str) for v in seen.values()):
        raise ValueError("unexpected seen_urls format")
    ratings = _strict(folder / "feedback.json", {"entries": {}})
    if set(ratings) != {"entries"} or any(
            not isinstance(v, dict) or set(v) - set(RATING_KEYS) or v.get("value") not in RATING_VALUES
            for v in ratings["entries"].values()):
        raise ValueError("unexpected feedback format")
    watches = _strict(folder / "watches.json", {"watches": []})
    if set(watches) != {"watches"} or any(
            not isinstance(w, dict) or set(w) - WATCH_KEYS or not {"id", "query", "status"} <= set(w)
            or w["status"] != "active" for w in watches["watches"]):
        raise ValueError("unexpected watches format")
    return {"issues": issues, "seen": seen, "ratings": ratings["entries"],
            "watches": watches["watches"]}


def _strict(path, default):
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("unexpected format: " + path.name)
    return data


def import_legacy(conn, folder):
    records = legacy_records(folder)
    if any(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
           for table in ("issues", "articles", "ratings", "watches")):
        raise ValueError("news database is not empty")
    with feature_db.write(conn):
        for day in sorted(records["issues"]):
            _put_issue(conn, records["issues"][day])
        conn.executemany("INSERT INTO articles (url, first_seen_on) VALUES (?, ?)",
                         records["seen"].items())
        conn.executemany(
            "INSERT INTO ratings (url, value, rated_at, title, category, source) VALUES (?, ?, ?, ?, ?, ?)",
            [(url, e["value"], e.get("ts"), e.get("title"), e.get("category"), e.get("source"))
             for url, e in records["ratings"].items()])
        conn.executemany(
            "INSERT INTO watches (id, query, status, created, expires) VALUES (?, ?, ?, ?, ?)",
            [(w["id"], w["query"], w["status"], w.get("created"), w.get("expires"))
             for w in records["watches"]])
    return database_records(conn)


def database_records(conn):
    return {
        "issues": {row["day"]: _load_issue(conn, row["day"])
                   for row in conn.execute("SELECT day FROM issues ORDER BY day").fetchall()},
        "seen": dict(conn.execute("SELECT url, first_seen_on FROM articles ORDER BY rowid")),
        "ratings": {row["url"]: _rating_dict(row)
                    for row in conn.execute("SELECT * FROM ratings ORDER BY rowid")},
        "watches": [_watch_dict(row) for row in conn.execute(
            "SELECT * FROM watches WHERE status = 'active' ORDER BY rowid")],
    }


def comparable(records):
    return records


def export_legacy(conn, folder):
    """Write the database back as the legacy JSON files (used by rollback)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    records = database_records(conn)
    for day, data in records["issues"].items():
        _write_new(folder / f"{day}.json", data)
    _write_new(folder / "seen_urls.json", records["seen"])
    _write_new(folder / "feedback.json", {"entries": records["ratings"]})
    _write_new(folder / "watches.json", {"watches": records["watches"]})
    return records


def _write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=1)


def counts(conn):
    return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("issues", "issue_items", "articles", "ratings", "watches")}


def main(argv=None):
    parser = argparse.ArgumentParser(description="News watch helper")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("watch", help="Open a one-shot watch")
    add.add_argument("query")
    add.add_argument("--expires", help="YYYY-MM-DD (default: 30 days from today)")
    sub.add_parser("watches", help="List open watches")
    args = parser.parse_args(argv)
    if args.action == "watch":
        result = add_watch(args.query, args.expires)
    else:
        result = load_watches()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
