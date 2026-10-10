"""
Google Calendar ユーティリティ — 共有ライブラリ
他スクリプトから import して使う。

  from calendar_utils import get_calendar_service, get_events, create_allday_event
"""
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


def get_events(time_min: datetime, time_max: datetime, max_results: int = 100) -> list[dict]:
    """指定期間のイベントを取得して返す（開始時刻順）。"""
    service = get_calendar_service()
    result = service.events().list(
        calendarId="primary",
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


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
