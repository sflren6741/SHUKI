#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claude_accounts.py — Claude Code アカウント2契約の単一情報源＋選択ロジック（2026-08-10 新設）。

背景：定期便（PS1）側には claude_launcher.ps1 の Invoke-ClaudeFailover があったが、
SHUKI ダッシュボード（dashboard_server.py）から手動で叩く claude -p は
CLAUDE_CONFIG_DIR を設定しておらず、常に既定 ~/.claude 固定＝空いている方に
切り替わらなかった。このモジュールがその選択ロジックを持つ。

同時に、dashboard_server.py に直書きされていたアカウント定義（Claudeアカウントパネル用の
CC_ACCOUNTS）がここへ統合された。旧定義は ~/.claude-a を A としていたが、実際には
.claude-a は 2026-08-03 に失効し、A のログインは既定 ~/.claude に入っている
＝パネルの A は常に取得失敗・B のラベルで A の数字を表示していた（2026-08-10 実測で判明）。

claude_launcher.ps1 と **同じ state ファイル**（%TEMP%\\claude_acct_state.json）を読み書きする
ので、どちらが上限を検知しても互いに避け合う（定期便で上限に当たったアカウントは
ダッシュボードからも使われない、逆も同様）。

アカウント選択の材料は3つ:
  1. state の limited_until（上限検知時刻＋resets まで）→ 期限内の候補は外す
  2. 残量API（oauth/usage）の使用率 → 低い方を先に
  3. --resume するセッションの所在（セッション jsonl はアカウントごとに分かれるため、
     継続会話は所属アカウントに固定するしかない＝ここだけ 1・2 より優先）
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import queue
from datetime import datetime, timedelta
from pathlib import Path

import shuki_paths
from shuki_i18n import t  # 画面に出るエラー文言の言語切り替え

# ── アカウント定義（単一情報源）─────────────────────
# shuki_paths.json の "claude_accounts": [{"key","label","dir"}, …]。
# 未設定なら既定プロファイル1本＝従来どおりの単一アカウント動作にフォールバックする。
_configured = shuki_paths.get_names_list("claude_accounts")
if _configured:
    ACCOUNTS = [{"key": a.get("key") or Path(a["dir"]).name,
                 "label": a.get("label") or Path(a["dir"]).name,
                 "kind": a.get("kind") or "claude",
                 "dir": Path(a["dir"])}
                for a in _configured if isinstance(a, dict) and a.get("dir")]
else:
    ACCOUNTS = [{"key": "A", "label": "default", "kind": "claude", "dir": Path.home() / ".claude"}]

# CANDIDATES / plan() / score() は Claude 契約の残量APIしか叩けないため kind=claude のみが対象。
# アカウント構成（何契約・何アカウントか）が変わっても shuki_paths.json の claude_accounts を
# 書き換えるだけで追従できるよう、kind でフィルタする形にしてある（2026-09-05 Codex統合時点）。
CANDIDATES = [a["dir"] for a in ACCOUNTS if a["kind"] == "claude"]


def codex_account():
    """kind=codex のアカウント定義（無ければ None）。Claude 2アカウントが両方上限の時の
    最終フォールバック、またはユーザーがモデル選択で明示的に Codex を選んだ時に使う。"""
    for a in ACCOUNTS:
        if a["kind"] == "codex":
            return a
    return None


def find(config_dir):
    """config_dir からアカウント定義を引く。無ければ None。"""
    for a in ACCOUNTS:
        if a["dir"] == Path(config_dir):
            return a
    return None

# claude_launcher.ps1 と共有する状態ファイル（キー＝config dir のフルパス文字列）。
# PowerShell の Out-File -Encoding utf8 は BOM 付きで書くため、読み書きとも utf-8-sig で揃える。
STATE_FILE = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp") / "claude_acct_state.json"
STATE_LOCK = threading.Lock()

# OAuth refresh失敗も、別アカウントへ切り替えれば継続できる一時的な認証エラーとして扱う。
LIMIT_RE = re.compile(
    r"(?i)(hit your .*limit|session.?limit|usage limit|rate.?limit|limit reached|"
    r"oauth\s+session\s+expired(?:\s+and\s+could\s+not\s+be\s+refreshed)?)"
)
UNKNOWN_RESET_HOURS = 6   # resets 表記をパースできなかった時の保守的な待ち時間
MAX_LIMIT_DAYS = 7        # 復帰予定がこれより先ならパース誤りとみなす安全弁（誤って長期封印しない）


def label(config_dir):
    """表示用の短い名前（例: .claude / .claude-b）。"""
    name = Path(config_dir).name
    for a in ACCOUNTS:
        if a["dir"] == Path(config_dir):
            return f'{a["key"]}・{a["label"]}'
    return name


# ── 残量API（clc.py と同じ oauth/usage を標準ライブラリで直接叩く）──────
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_TTL = 300  # 秒（5分。使用量は瞬時に動かないため頻繁な呼び出しを避ける）
USAGE_REFRESH_MIN = 60  # Manual refresh may bypass the TTL, never the provider cooldown.
USAGE_TIMEOUT = 8
UNKNOWN_SCORE = 50.0     # 残量が取れなかったアカウントの中立スコア。999（＝最下位）にすると
# 429 のたびにそのアカウントが後回しになり、結果としていつも同じ方に偏って片肺運用になる。
# 取れない＝使えない ではない（claude 実行時にトークンは自動更新される）ので中立に置く。
_usage_cache = {}  # {config_dir_str: {"ts": epoch, "data": dict|None}}
_usage_lock = threading.Lock()


def _fetch_usage_raw(config_dir):
    """1アカウント分の oauth/usage 生レスポンス（キャッシュなし・失敗時は例外）。"""
    creds = json.loads((Path(config_dir) / ".credentials.json").read_text(encoding="utf-8"))
    oauth = creds.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        raise RuntimeError(t("認証情報に accessToken がありません"))
    expires_at = oauth.get("expiresAt")
    if expires_at and expires_at / 1000 < time.time():
        raise RuntimeError(t("OAuthトークンが期限切れです（Claude Codeを一度起動すると更新されます）"))
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json", "User-Agent": "dashboard-usage/1.0",
    })
    with urllib.request.urlopen(req, timeout=USAGE_TIMEOUT) as res:
        return json.loads(res.read())


def usage(config_dir, force=False):
    """Usage cached for five minutes; manual checks may refresh after one minute.

    Failures retain the last values with an error/stale marker and are also cached.
    Each check makes only one provider request; fetched_at is the last successful fetch.
    """
    key = str(config_dir)
    with _usage_lock:
        cache = _usage_cache.setdefault(key, {"ts": 0, "data": None})
        cooldown = USAGE_REFRESH_MIN if force else USAGE_TTL
        if cache["data"] is not None and time.time() - cache["ts"] < cooldown:
            return cache["data"]
        try:
            data = dict(_fetch_usage_raw(config_dir), fetched_at=time.time())
            cache.update(ts=time.time(), data=data)
            return data
        except Exception as e:
            error_message = str(e)
        data = dict(cache["data"] or {}, error=error_message)
        if data.get("fetched_at"):
            data["stale"] = True
        cache.update(ts=time.time(), data=data)
        return data


def refresh_expiry(config_dir):
    """credentials.json の refreshTokenExpiresAt をローカルファイルから直接読むだけ（API不要）。
    ISO文字列（naive）を返す。読めない・値がなければ None。

    accessToken は refreshToken がある限り claude 実行時に自動更新されるが、refreshToken 自体が
    切れると「Failed to authenticate: OAuth session expired and could not be refreshed」で
    そのアカウントが完全に使えなくなる（2026-08-28 実測・.claude-b が数時間このまま気づかれず
    ダッシュボードのジョブが失敗し続けた）。ホーム画面のアカウントパネルで期限を先読み表示し、
    切れる前に再ログインを促すために追加した。"""
    try:
        creds = json.loads((Path(config_dir) / ".credentials.json").read_text(encoding="utf-8"))
        raw = (creds.get("claudeAiOauth") or {}).get("refreshTokenExpiresAt")
        return datetime.fromtimestamp(raw / 1000).isoformat() if raw else None
    except (OSError, json.JSONDecodeError, ValueError, OverflowError, KeyError):
        return None


def usage_all(force=False):
    """全アカウント分をまとめて返す（{"A": {...}, "B": {...}}）。ダッシュボードの /usage-accounts 用。
    各アカウントの dict に refresh_expires_at（ISO文字列 or None）も混ぜて返す
    （refreshToken の残り寿命をホーム画面で先読み警告するため・2026-08-28 追加）。
    Codex は CLI の app-server が持つ account/rateLimits/read を別キーで返す。"""
    out = {}
    for a in ACCOUNTS:
        if a["kind"] != "claude":
            continue
        data = dict(usage(a["dir"], force=force))  # Do not mutate the cached response.
        data["refresh_expires_at"] = refresh_expiry(a["dir"])
        out[a["key"]] = data
        
    if codex_account():
        out["codex"] = codex_usage()
    return out


# Codex CLI v0.153+ の app-server が認証済みChatGPTアカウントのレート情報を返す。
# 公開HTTP APIではないが、CLI自身が利用する機械可読プロトコルなので、ブラウザ認証情報や
# 内部Webエンドポイントを直接扱わずにホーム表示へ再利用できる。
_codex_usage_cache = {"ts": 0, "data": None}
_codex_usage_lock = threading.Lock()


def _codex_cli_cmd():
    shim = shutil.which("codex")
    if shim:
        js = Path(shim).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if node and js.is_file():
            return [node, str(js)]
    return [shim or "codex"]


def _codex_rpc(proc, message, responses, timeout=8):
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    while True:
        line = responses.get(timeout=timeout)
        if not line:
            continue
        item = json.loads(line)
        if item.get("id") == message.get("id"):
            return item


def _codex_usage_raw():
    proc = subprocess.Popen(
        _codex_cli_cmd() + ["app-server", "--stdio"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    responses = queue.Queue()

    def read_stdout():
        for line in proc.stdout:
            responses.put(line.strip())

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        _codex_rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"clientInfo": {"name": "shuki-dashboard", "version": "1.0"},
                                      "capabilities": {}}}, responses)
        proc.stdin.write('{"jsonrpc":"2.0","method":"initialized","params":{}}\n')
        proc.stdin.flush()
        result = _codex_rpc(proc, {"jsonrpc": "2.0", "id": 2,
                                   "method": "account/rateLimits/read", "params": None}, responses)
        return result.get("result") or {}
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def _codex_window(raw, key):
    w = (raw.get("rateLimits") or {}).get(key) or {}
    if not w:
        return None
    reset = w.get("resetsAt")
    return {"utilization": w.get("usedPercent"),
            "resets_at": datetime.fromtimestamp(reset).isoformat() if reset else None}


def codex_usage():
    """Codexの5時間/週次使用率、購入クレジット、リセット権を返す（60秒キャッシュ）。"""
    with _codex_usage_lock:
        if _codex_usage_cache["data"] is not None and time.time() - _codex_usage_cache["ts"] < 60:
            return _codex_usage_cache["data"]
        try:
            raw = _codex_usage_raw()
            limits = raw.get("rateLimits") or {}
            credits = limits.get("credits") or {}
            data = {"fetched_at": time.time(),
                    "five_hour": _codex_window(raw, "primary"),
                    "seven_day": _codex_window(raw, "secondary"),
                    "credits": credits,
                    "available_resets": (raw.get("rateLimitResetCredits") or {}).get("availableCount", 0),
                    "plan_type": limits.get("planType")}
        except Exception as e:
            data = dict(_codex_usage_cache["data"] or {}, error=str(e))
            if data.get("fetched_at"):
                data["stale"] = True
        _codex_usage_cache.update(ts=time.time(), data=data)
        return data


def score(config_dir):
    """5h/週次/週次Opus の使用率の最大値。取得できなければ UNKNOWN_SCORE（中立）。"""
    data = usage(config_dir)
    if not isinstance(data, dict) or data.get("error"):
        return UNKNOWN_SCORE
    values = []
    for window in ("five_hour", "seven_day", "seven_day_opus"):
        w = data.get(window)
        if isinstance(w, dict) and w.get("utilization") is not None:
            values.append(float(w["utilization"]))
    return max(values) if values else UNKNOWN_SCORE


TIE_BAND = 5.0  # score差がこの範囲内なら「残量ほぼ同じ」とみなし resets 時刻でタイブレークする


def _soonest_reset(config_dir):
    """score() が見るウィンドウ（5h/週次/週次Opus）のうち、直近の resets_at。取得できなければ None。

    目的は「リセットされる前に週次クレジットを使い切る」こと（2026-08-13 起票のタスク対応）。
    score が僅差の時だけ、この時刻が近い方を先に使うタイブレーカーとして使う。
    """
    data = usage(config_dir)
    if not isinstance(data, dict) or data.get("error"):
        return None
    candidates = []
    for window in ("five_hour", "seven_day", "seven_day_opus"):
        w = data.get(window)
        if isinstance(w, dict) and w.get("resets_at"):
            try:
                candidates.append(datetime.fromisoformat(w["resets_at"]))
            except ValueError:
                pass
    return min(candidates) if candidates else None


def _sort_key(config_dir):
    """plan() のソートキー。score優先（低い方＝残量が多い方を先に試す）、
    score差が TIE_BAND 以内の僅差なら resets_at が近い方を先にする。
    差が大きい時は従来どおり score だけで決まる＝残量をゼロまで片方に寄せない性質は変わらない。"""
    s = score(config_dir)
    reset = _soonest_reset(config_dir)
    reset_order = reset.timestamp() if reset else float("inf")
    return (round(s / TIE_BAND), reset_order, s)


# ── state（上限中の記録・claude_launcher.ps1 と共有）──────────────

def _load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def mark_limited(config_dir, until):
    """このアカウントが上限に当たったことを記録する（PS1側もこの記録を見て避ける）。"""
    with STATE_LOCK:
        state = _load_state()
        if not isinstance(state, dict):
            state = {}
        state[str(config_dir)] = {"limited_until": until.isoformat()}
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                  encoding="utf-8-sig")
        except OSError:
            pass  # 記録できなくても選択自体は続行できる（次回は残量スコアで避ける）


def _limited_until(state, config_dir):
    entry = state.get(str(config_dir))
    if not isinstance(entry, dict):
        return None
    raw = entry.get("limited_until")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt  # ローカル時刻同士で比較する


def available():
    """limited_until を過ぎた（＝使えるはずの）候補だけを返す。全滅なら全候補を返す。"""
    state = _load_state()
    now = datetime.now()
    alive = []
    for c in CANDIDATES:
        until = _limited_until(state, c)
        if until is None or until < now:
            alive.append(c)
    return alive or list(CANDIDATES)


def _to_24h(hour, minute, ampm):
    hour, minute = int(hour), int(minute or 0)
    if ampm.lower() == "pm" and hour < 12:
        hour += 12
    if ampm.lower() == "am" and hour == 12:
        hour = 0
    return hour, minute


def parse_reset(text):
    """上限メッセージの resets 表記を datetime に変換する。読めなければ None。

    2026-05〜08 の agent-runs ログ実測では、実際に出る形式は次の2つだけ:
      "You've hit your session limit · resets 11pm (Asia/Tokyo)"        ← 時刻のみ（最多）
      "You've hit your weekly limit · resets Jul 31, 2pm (Asia/Tokyo)"  ← 月日つき
    claude_launcher.ps1 は前者に非対応で毎回6時間の固定待ちに落ちていたため、
    こちらは時刻のみの形式を先にカバーする（相対表記 "resets in 04h52m" も一応残す）。
    """
    now = datetime.now()
    m = re.search(r"resets\s+in\s+(?:(\d+)d,?)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?", text, re.I)
    if m and any(m.groups()):
        days, hours, mins = (int(g) if g else 0 for g in m.groups())
        if days or hours or mins:
            return now + timedelta(days=days, hours=hours, minutes=mins)

    m = re.search(r"resets\s+([A-Za-z]{3,9})\s+(\d{1,2}),?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
                  text, re.I)
    if m:
        month_name, day, hour, minute, ampm = m.groups()
        try:
            month = datetime.strptime(month_name[:3], "%b").month
        except ValueError:
            return None
        hour, minute = _to_24h(hour, minute, ampm)
        try:
            candidate = datetime(now.year, month, int(day), hour, minute)
        except ValueError:
            return None
        # 年またぎ（12月に "resets Jan 2" が来る）だけを翌年に送る。数日前の日付は
        # 「読み違い」とみなして None を返す（翌年扱いにするとそのアカウントを1年封印してしまう）。
        if candidate < now - timedelta(days=MAX_LIMIT_DAYS):
            candidate = candidate.replace(year=now.year + 1)
        elif candidate < now:
            return None
        return candidate

    # 時刻のみ（"resets 11pm" / "resets 6:20am"）。今日のその時刻、過ぎていれば翌日。
    m = re.search(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if m:
        hour, minute = _to_24h(m.group(1), m.group(2), m.group(3))
        try:
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None
        return candidate if candidate > now else candidate + timedelta(days=1)
    return None


def is_limit_error(text):
    return bool(text) and bool(LIMIT_RE.search(text))


def note_limit(config_dir, text):
    """上限メッセージから resets を読み取って記録する（読めなければ既定 UNKNOWN_RESET_HOURS）。
    戻り値は復帰予定時刻。"""
    now = datetime.now()
    until = parse_reset(text or "") or (now + timedelta(hours=UNKNOWN_RESET_HOURS))
    # パース誤りで何日も封印されるのを防ぐ安全弁（週次上限でも実測7日以内に復帰する）
    until = min(until, now + timedelta(days=MAX_LIMIT_DAYS))
    mark_limited(config_dir, until)
    return until


# ── セッションの所在 ─────────────────────────────────

def projects_dirs():
    """全候補の <config dir>/projects（履歴・トランスクリプト探索用）。"""
    return [c / "projects" for c in CANDIDATES]


def session_owners(session_id):
    """その session_id の jsonl が見える config dir を**すべて**返す。

    ユーザーの環境では `~/.claude-b/projects` が `~/.claude/projects` へのジャンクション
    （2026-07-31 に auto-memory 共有のために作成）＝セッション本体は全アカウントで共有されており、
    **A で始めた会話を B で --resume できる**（2026-08-10 実測: 文脈を正しく引き継いだ）。
    よって継続会話でもアカウントを切り替えられる。
    ジャンクションが無い環境（公開版など）では1つだけ返り、従来どおり所属アカウントに固定される。
    """
    if not session_id:
        return []
    found = []
    for c in CANDIDATES:
        if any((c / "projects").glob(f"*/{session_id}.jsonl")):
            found.append(c)
    return found


# ── 選択 ────────────────────────────────────────────

def plan(session_id=""):
    """試す順（使用率の低い順）に並べた config dir のリストを返す。

    継続会話（session_id あり）でも、そのセッションが見えるアカウントが複数あれば
    切り替えられる（projects がジャンクション共有のため・session_owners 参照）。
    セッションが見えないアカウントへは --resume できないので候補から外す。
    """
    pool = available()
    if session_id:
        owners = session_owners(session_id)
        if owners:
            usable = [c for c in pool if c in owners] or owners
            return sorted(usable, key=_sort_key)
        return [pool[0]]  # jsonl が見つからない（新しすぎる等）＝現状のまま試す
    return sorted(pool, key=_sort_key)
