"""対話パネルのアクションカード（2026-10-14 新設）。

AI は回答に ```shuki-action ブロック（JSON）を書いて「提案」するだけで、実行はしない。
パネルがそれをカード（内容を確認・修正できるフォーム）として描き、ユーザーがボタンを押した時だけ
このモジュールがサーバー側で実行する。押す行為そのものが人間確認なので、GCal 書き込みは人間確認
必須の原則（AGENTS.md §📜 ルール3）を守ったまま対話の中で完結する。

  calendar … {"type":"calendar","events":[{"title","date","start","end","location","description"}]}
              start/end（HH:MM）を省くと終日予定。登録前に同じ日の既存予定との重なりを返す。
  task     … {"type":"task","title","area","due","next_action","completion_criteria","parent","reason"}
              タスクDBに1ファイル作る。同名ファイルがあれば作らない。

二重実行防止：カードごとの key（提案本文のハッシュ＋行番号。クライアントが付ける）で実行結果を
<system>/chat_actions.jsonl に残し、同じ key は再実行せず前回の結果を返す。履歴を開き直しても、
別端末から同じ会話を見ても「登録済み」と表示される。
"""
import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import calendar_utils
import shuki_paths
import shuki_profile
from shuki_core import vault as core_vault

VAULT = core_vault.VAULT
TASK_DIR = VAULT / "04_Tasks" / "タスク管理" / "タスク"
LOG = shuki_paths.system_dir_for(VAULT) / "chat_actions.jsonl"
AREAS = tuple(shuki_profile.valid_area_names())
KEY_RE = re.compile(r"[a-z0-9][a-z0-9:-]{0,79}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
MAX_EVENTS = 12
_LOCK = threading.Lock()


def _text(d, name, limit, required=False):
    value = d.get(name, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} is too long (max {limit})")
    return value


def _date(d, name, required=False):
    value = _text(d, name, 10, required)
    if value:
        if not DATE_RE.fullmatch(value):
            raise ValueError(f"{name} must be YYYY-MM-DD")
        date.fromisoformat(value)
    return value


def clean_event(d):
    """カードから来た1予定を検証して正規化する。"""
    if not isinstance(d, dict):
        raise ValueError("event must be an object")
    ev = {"title": _text(d, "title", 200, True), "date": _date(d, "date", True),
          "start": _text(d, "start", 5), "end": _text(d, "end", 5),
          "location": _text(d, "location", 200), "description": _text(d, "description", 1000)}
    if ev["start"] or ev["end"]:
        if not (TIME_RE.fullmatch(ev["start"]) and TIME_RE.fullmatch(ev["end"])):
            raise ValueError("start and end must both be HH:MM (or both empty for all-day)")
        if ev["end"] <= ev["start"]:
            raise ValueError("end must be after start on the same day")
    return ev


def _span(ev):
    day = datetime.combine(date.fromisoformat(ev["date"]), datetime.min.time(), core_vault.JST)
    if not ev["start"]:
        return day, day + timedelta(days=1)
    sh, sm = map(int, ev["start"].split(":"))
    eh, em = map(int, ev["end"].split(":"))
    return day.replace(hour=sh, minute=sm), day.replace(hour=eh, minute=em)


def _gcal_span(item):
    s, e = item.get("start", {}), item.get("end", {})
    if "dateTime" in s:
        return (datetime.fromisoformat(s["dateTime"]).astimezone(core_vault.JST),
                datetime.fromisoformat(e["dateTime"]).astimezone(core_vault.JST))
    start = datetime.combine(date.fromisoformat(s["date"]), datetime.min.time(), core_vault.JST)
    end = datetime.combine(date.fromisoformat(e.get("date", s["date"])), datetime.min.time(), core_vault.JST)
    return start, max(end, start + timedelta(days=1))


def conflicts(events):
    """各予定と重なる既存の GCal 予定を返す。日付ごとに1回だけ API を呼ぶ（読み取りのみ）。"""
    events = [clean_event(e) for e in events[:MAX_EVENTS]]
    by_day = {}
    for ev in events:
        if ev["date"] not in by_day:
            start = datetime.combine(date.fromisoformat(ev["date"]), datetime.min.time(), core_vault.JST)
            by_day[ev["date"]] = calendar_utils.get_events(start, start + timedelta(days=1))
    out = []
    for ev in events:
        a, b = _span(ev)
        hits = []
        for item in by_day[ev["date"]]:
            try:
                s, e = _gcal_span(item)
            except (KeyError, ValueError):
                continue
            all_day = "dateTime" not in item.get("start", {})
            # 終日予定同士・時刻予定同士の重なりだけを見る（終日の「誕生日」等で時刻予定を警告しない）
            if all_day != (not ev["start"]):
                continue
            if s < b and a < e:
                hits.append({"title": item.get("summary") or "(no title)",
                             "time": "all day" if all_day else f"{s:%H:%M}–{e:%H:%M}"})
        out.append(hits)
    return out


def _yaml_str(value):
    """YAML のダブルクォート文字列（JSON 文字列は YAML として有効）。"""
    return json.dumps(value, ensure_ascii=False)


def clean_task(d):
    if not isinstance(d, dict):
        raise ValueError("task must be an object")
    task = {"title": _text(d, "title", 120, True), "area": _text(d, "area", 20),
            "due": _date(d, "due"), "next_action": _text(d, "next_action", 300),
            "completion_criteria": _text(d, "completion_criteria", 300),
            "parent": _text(d, "parent", 120), "reason": _text(d, "reason", 2000)}
    if re.search(r'[\\/:*?"<>|\[\]#^]', task["title"]) or task["title"].startswith("."):
        raise ValueError("title cannot contain \\ / : * ? \" < > | [ ] # ^")
    if task["area"] and task["area"] not in AREAS:
        raise ValueError("area must be one of: " + " / ".join(AREAS))
    task["parent"] = task["parent"].removeprefix("[[").removesuffix("]]").strip()
    return task


def create_task(d, today=None, task_dir=None):
    """タスクDBに1ファイル作る。戻り値は vault 相対パス。同名があれば FileExistsError。"""
    task = clean_task(d)
    today = (today or date.today()).isoformat()
    task_dir = Path(task_dir or TASK_DIR)
    path = task_dir / f"{task['title']}.md"
    fm = [f"title: {_yaml_str(task['title'])}", f"area: {task['area']}", "type: タスク",
          "status: todo", f"created: {today}", f"date: {today}"]
    if task["due"]:
        fm.append(f"due: {task['due']}")
    if task["next_action"]:
        fm.append(f"next_action: {_yaml_str(task['next_action'])}")
    if task["completion_criteria"]:
        fm.append(f"completion_criteria: {_yaml_str(task['completion_criteria'])}")
    else:
        fm.append("human_only: true")  # 完了条件が書けない仕事は人間へ（AGENTS.md ルール5）
    if task["parent"]:
        fm.append(f"parent: {_yaml_str('[[' + task['parent'] + ']]')}")
    body = [f"# {task['title']}", ""]
    if task["reason"]:
        body += ["## 起票理由", "", task["reason"], ""]
    body += ["## 履歴", "", f"- {today}: 作成（対話パネルのタスクカードから）", ""]
    task_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as f:  # "x" = 既存なら FileExistsError
        f.write("---\n" + "\n".join(fm) + "\n---\n\n" + "\n".join(body))
    try:
        return path.relative_to(VAULT).as_posix()
    except ValueError:
        return path.name


def _records():
    out = {}
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("key"):
            out[rec["key"]] = rec
    return out


def _public(rec):
    return {k: rec[k] for k in ("kind", "id", "path", "title", "at") if k in rec}


def handle(data):
    """POST /chat/action の本体。(HTTPステータス, 応答dict) を返す。

    op=status … {"keys":[...]} → 実行済みの key だけ {"done":{key: 結果}}
    op=check  … {"events":[...]} → {"conflicts":[[...], ...]}（予定ごとの重なり）
    op=run    … {"kind","key","payload"} → 実行。実行済み key なら再実行せず already=True
    """
    if not isinstance(data, dict):
        return 400, {"error": "expected an object"}
    op = data.get("op")
    try:
        if op == "status":
            keys = [k for k in data.get("keys") or [] if isinstance(k, str)][:50]
            recs = _records()
            return 200, {"done": {k: _public(recs[k]) for k in keys if k in recs}}
        if op == "check":
            events = data.get("events")
            if not isinstance(events, list) or not events:
                raise ValueError("events must be a non-empty list")
            return 200, {"conflicts": conflicts(events)}
        if op != "run":
            return 400, {"error": "unknown op"}
        kind, key, payload = data.get("kind"), data.get("key"), data.get("payload")
        if kind not in ("calendar", "task") or not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise ValueError("bad kind or key")
        with _LOCK:  # 連打・2端末同時押しでも1回だけ実行する
            prev = _records().get(key)
            if prev:
                return 200, {"ok": True, "already": True, **_public(prev)}
            if kind == "calendar":
                ev = clean_event(payload)
                event_id = calendar_utils.create_event(
                    ev["title"], date.fromisoformat(ev["date"]),
                    start_time=ev["start"] or None, end_time=ev["end"] or None,
                    location=ev["location"], description=ev["description"])
                rec = {"kind": kind, "id": event_id, "title": ev["title"]}
            else:
                rec = {"kind": kind, "path": create_task(payload), "title": payload.get("title", "")}
            rec.update(key=key, at=datetime.now(core_vault.JST).isoformat(timespec="seconds"))
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return 200, {"ok": True, **_public(rec)}
    except FileExistsError:
        return 409, {"error": "A task with this title already exists. Change the title and try again."}
    except calendar_utils.CalendarNotConnected as e:
        return 503, {"error": f"Google Calendar is not connected: {e}"}
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:  # GCal API 失敗等。原文を返して停止ルールの材料にする
        return 502, {"error": f"{type(e).__name__}: {e}"}
