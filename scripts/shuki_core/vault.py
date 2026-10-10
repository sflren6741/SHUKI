"""Generic vault paths and lightweight readers shared by core and plugins.

These compatibility helpers preserve the existing parsing behavior. Privacy checks
remain with each caller; this module never discovers or reads notes by itself.
"""
import re
from datetime import date, timedelta, timezone

import shuki_paths

JST = timezone(timedelta(hours=9))
VAULT = shuki_paths.VAULT
LOG_DIR = VAULT / "07_Logs" / "ログ"
TASK_DIR = VAULT / "04_Tasks" / "タスク管理" / "タスク"
KNOWLEDGE_DIR = VAULT / "06_Resources" / "Resources" / "ナレッジ"
CONCEPT_DIR = VAULT / "06_Resources" / "Resources" / "概念"

FM_DATE = re.compile(r"^(date|created):\s*(\d{4})-(\d{1,2})-(\d{1,2})", re.M)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""


def frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end]
    return text[:2048]


def pick_date(fm):
    """created を優先、なければ date。date オブジェクトか None。"""
    chosen = None
    for key, y, mo, d in FM_DATE.findall(fm):
        try:
            dt = date(int(y), int(mo), int(d))
        except ValueError:
            continue
        if key == "created":
            return dt
        if chosen is None:
            chosen = dt
    return chosen


def parse_areas(fm):
    lines = fm.splitlines()
    found = []
    for i, ln in enumerate(lines):
        m = re.match(r"^area:\s*(.*)$", ln)
        if not m:
            continue
        val = m.group(1).strip().strip("\"'")
        if val:
            found.append(val)
        else:
            for ln2 in lines[i + 1:]:
                m2 = re.match(r"^\s*-\s*(.+)$", ln2)
                if m2:
                    found.append(m2.group(1).strip().strip("\"'[]"))
                elif re.match(r"^\S", ln2):
                    break
        break
    return [a.strip().strip("\"'").strip("[]") for a in found if a.strip()]


def extract_insight(text, limit=160):
    """本文の「## 気づき」セクションから最初の意味のある行を1行抜き出す（無ければ空文字）。

    実データは「散文の後に概念リンクの箇条書き」「箇条書きのみ」の両方があるため、
    見出し/コードフェンス/空行を飛ばして最初の非空行を採用する。
    vault_index._build_record() が使い、カレンダーの Results 表示がログの抜粋として表示する共通ユーティリティ
    （2026-07-28 dashboard_server.py から移設。ログ本文はvault_indexに保持しないため、indexビルド時点で
    事前計算しキャッシュする＝毎リクエストの本文再読み込みを避ける）。
    """
    m = re.search(r"^## 気づき\s*\n(.*?)(?=\n## |\Z)", text, re.M | re.S)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("```"):
            continue
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"[*`_]", "", s)
        s = re.sub(r'\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]', r"\1", s)  # wikilinkは表示名だけ残す
        if s:
            return s[:limit] + ("…" if len(s) > limit else "")
    return ""
