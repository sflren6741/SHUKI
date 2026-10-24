"""
Google Calendar ユーティリティ — 共有ライブラリ
他スクリプトから import して使う。

  from calendar_utils import get_calendar_service, get_events, create_allday_event
"""
import hashlib
import re
import threading
from datetime import datetime, date, timezone, timedelta
from pathlib import Path


SCOPES         = ["https://www.googleapis.com/auth/calendar"]
import sys as _s; _s.path.insert(0, str(Path(__file__).resolve().parent))
import shuki_paths  # noqa: E402  (資格情報の置き場。2026-09-28)

SCRIPT_DIR     = Path(__file__).parent
CREDENTIALS    = shuki_paths.secret_file("credentials.json")
CALENDAR_TOKEN = shuki_paths.secret_file("calendar_token.json")


class CalendarNotConnected(RuntimeError):
    pass


def validate_event_title(summary: str) -> None:
    """Reject visibly lost Unicode before any Calendar connection or write."""
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("A Calendar title is required")
    if "\ufffd" in summary or re.search(r"\?{3,}", summary):
        raise ValueError("Calendar title appears encoding-damaged; reload the original text using UTF-8")


def get_calendar_service(*, authorize=False):
    """Use a configured account; interactive OAuth requires an explicit setup call."""
    if not CALENDAR_TOKEN.exists() and not authorize:
        raise CalendarNotConnected("Connect Google Calendar during setup to see events.")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None
    if CALENDAR_TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(CALENDAR_TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not authorize:
                raise CalendarNotConnected("Reconnect Google Calendar during setup.")
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        CALENDAR_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


# 読み取り用クライアントの使い回し（2026-10-10）。予定そのものは毎回APIから取る（キャッシュしない
# ＝開くたび最新、は従来どおり）。毎回 build() すると TLS の準備と新規接続で1回 ~560ms、使い回すと
# ~280ms（実測）。httplib2 はスレッド安全でないのでロックで直列化し、トークンファイルが
# 変わった時（再接続）と失敗した時は作り直す。
_READ_SERVICE = {"stamp": None, "service": None}
_READ_LOCK = threading.Lock()


def get_events(
    time_min: datetime,
    time_max: datetime,
    max_results: int = 100,
    *,
    fields: str | None = None,
    paginate: bool = False,
) -> list[dict]:
    """指定期間のイベントを取得して返す（開始時刻順）。"""
    with _READ_LOCK:
        try:
            st = CALENDAR_TOKEN.stat()
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            stamp = None
        if _READ_SERVICE["service"] is None or _READ_SERVICE["stamp"] != stamp:
            _READ_SERVICE["service"] = get_calendar_service()
            _READ_SERVICE["stamp"] = stamp
        try:
            items, page_token = [], None
            while True:
                params = {
                    "calendarId": "primary",
                    "timeMin": time_min.isoformat(),
                    "timeMax": time_max.isoformat(),
                    "maxResults": max_results,
                    "singleEvents": True,
                    "orderBy": "startTime",
                }
                if fields:
                    params["fields"] = fields
                if page_token:
                    params["pageToken"] = page_token
                result = _READ_SERVICE["service"].events().list(**params).execute()
                items.extend(result.get("items", []))
                page_token = result.get("nextPageToken")
                if not paginate or not page_token:
                    break
        except Exception:
            _READ_SERVICE["service"] = None
            raise
    return items


def format_event_time(event: dict) -> str:
    """イベントの開始時刻を 'HH:MM' or '終日' の文字列に整形する。"""
    start = event["start"]
    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"])
        return dt.strftime("%H:%M")
    return "終日"


def create_allday_event(
    summary: str,
    event_date: date,
    description: str = "",
    calendar_id: str = "primary",
) -> str:
    """終日イベントを作成してイベントIDを返す。"""
    validate_event_title(summary)
    service = get_calendar_service()
    body = {
        "summary": summary,
        "start":   {"date": event_date.isoformat()},
        "end":     {"date": (event_date + timedelta(days=1)).isoformat()},
    }
    if description:
        body["description"] = description
    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]


def create_event(
    summary: str,
    event_date: date,
    start_time: str | None = None,
    end_time: str | None = None,
    location: str = "",
    description: str = "",
    calendar_id: str = "primary",
) -> str:
    """予定を作成してイベントIDを返す。

    start_time/end_time（"HH:MM"、JST固定）を両方渡すと時刻指定予定、渡さなければ
    event_date 1日だけの終日予定（create_allday_event と同じ形）になる。
    """
    validate_event_title(summary)
    service = get_calendar_service()
    body: dict = {"summary": summary}
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    if start_time and end_time:
        jst = timezone(timedelta(hours=9))
        sh, sm = (int(x) for x in start_time.split(":"))
        eh, em = (int(x) for x in end_time.split(":"))
        start_dt = datetime(event_date.year, event_date.month, event_date.day, sh, sm, tzinfo=jst)
        end_dt = datetime(event_date.year, event_date.month, event_date.day, eh, em, tzinfo=jst)
        body["start"] = {"dateTime": start_dt.isoformat()}
        body["end"] = {"dateTime": end_dt.isoformat()}
    else:
        body["start"] = {"date": event_date.isoformat()}
        body["end"] = {"date": (event_date + timedelta(days=1)).isoformat()}
    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]


def get_decision_availability(start: datetime, end: datetime, *, service=None) -> list[dict]:
    """Fresh, paginated primary-calendar events for a bounded scheduling window."""
    if (start.utcoffset() is None or end.utcoffset() is None or end <= start
            or end - start > timedelta(days=31)):
        raise ValueError("Use timezone-aware bounds spanning at most 31 days")
    service = service if service is not None else get_calendar_service()
    events, page_token = [], None
    while True:
        result = service.events().list(
            calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=2500,
            pageToken=page_token).execute()
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return events


def create_decision_event(decision_id: str, summary: str, start: datetime,
                          duration_minutes: int, *, location: str = "",
                          description: str = "") -> dict:
    """Create once for a recorded scheduling answer; never invite, update or delete.

    The scheduled processor determines duration/deadline/preferences from permitted
    source notes, then supplies one candidate. A fresh primary-calendar check here
    prevents overlap; a stable Google event ID prevents repeat-run duplicates.
    """
    import decisions
    from googleapiclient.errors import HttpError

    answer = decisions.scheduling_answer(decision_id)
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 200:
        raise ValueError("A session title of at most 200 characters is required")
    validate_event_title(summary)
    if type(duration_minutes) is not int or not 0 < duration_minutes <= 1440:
        raise ValueError("A verified duration from 1 to 1440 minutes is required")
    if start.utcoffset() is None:
        raise ValueError("A timezone-aware start is required")
    jst = timezone(timedelta(hours=9))
    start = start.astimezone(jst)
    end = start + timedelta(minutes=duration_minutes)
    if answer.get("scheduling_mode") != "auto" and answer.get("answer") != "auto_schedule" \
            and answer.get("selected_option") != "c":
        if start.strftime("%Y-%m-%d %H:%M") != answer["answer"]:
            raise ValueError("Start differs from the user's confirmed time")
    event_id = "shuki" + hashlib.sha256(decision_id.encode("utf-8")).hexdigest()
    service = get_calendar_service()
    try:
        existing = service.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as error:
        if error.resp.status != 404:
            raise
    else:
        if (existing.get("id") != event_id or existing.get("status") == "cancelled" or
                not existing.get("start", {}).get("dateTime") or
                not existing.get("end", {}).get("dateTime") or
                existing.get("extendedProperties", {}).get("private", {}).get("shuki_decision") != decision_id):
            raise ValueError("The decision event was cancelled or no longer matches; review it")
        validate_event_title(existing.get("summary", ""))
        return existing
    if start <= datetime.now(jst):
        raise ValueError("The selected time has passed; leave the request pending")
    busy = get_decision_availability(start, end, service=service)
    if any(event.get("status") != "cancelled" and event.get("transparency") != "transparent"
           and not any(a.get("self") and a.get("responseStatus") == "declined"
                       for a in event.get("attendees", [])) for event in busy):
        raise ValueError("Calendar conflict; leave the request pending for a new slot")
    body = {"id": event_id, "summary": summary.strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Tokyo"},
            "location": str(location)[:200], "description": str(description)[:1000],
            "extendedProperties": {"private": {"shuki_decision": decision_id}}}
    service.events().insert(calendarId="primary", body=body, sendUpdates="none").execute()
    # A successful insert without a verified record is not reported as completion.
    created = service.events().get(calendarId="primary", eventId=event_id).execute()
    if (created.get("id") != event_id or created.get("status") == "cancelled"
            or created.get("summary") != body["summary"]
            or datetime.fromisoformat(created.get("start", {}).get("dateTime", "0001-01-01")) != start
            or datetime.fromisoformat(created.get("end", {}).get("dateTime", "0001-01-01")) != end):
        raise ValueError("Calendar creation could not be verified; retain the queue item")
    return created


def today_range() -> tuple[datetime, datetime]:
    """今日の 00:00〜23:59 の UTC 範囲を返す（ローカル日付ベース）。"""
    now   = datetime.now()
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end   = start + timedelta(days=1)
    return start, end


def week_range(anchor: date | None = None) -> tuple[datetime, datetime]:
    """anchor（デフォルト=今日）を含む月曜〜日曜の UTC 範囲を返す。"""
    if anchor is None:
        anchor = date.today()
    monday = anchor - timedelta(days=anchor.weekday())
    start  = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    end    = start + timedelta(days=7)
    return start, end
