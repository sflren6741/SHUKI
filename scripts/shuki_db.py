#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shuki_db.py — SHUKI 共通 SQLite（99_System/db/shuki.db・git管理下・2026-08-25 新設）

背景: agent-runs の .log（自由形式テキスト）・vault-scripts 直下の各種 .jsonl/.json/.csv に
イベント系データ（実行結果・タスク状態遷移・クイズ解答ログ等）が散らばり、集計のたびに
grep やアドホックなパーサーを書く必要があった。vault 本体（.md）は今まで通り Obsidian の
資産として一切触らず、「行が増え続けるデータ」だけをここに寄せる。

置き場を vault 内 99_System/db/ にしたのは、vault-scripts（git管理外）に置くと夜間の
bk-auto コミットで実行結果が残らないため。DB ファイルはバイナリだが、現状の行数
（イベント合計で数百行規模）ではコミットごとの増分は軽微。

使い方:
  import shuki_db
  with shuki_db.connect() as conn:
      shuki_db.record_run(conn, job="briefing", started_at=..., ended_at=..., result="success")
"""
import sqlite3
from pathlib import Path

import shuki_paths
from shuki_core import db as feature_db

# 2026-10-06: 機能ごとのDB分割で core の置き場は <data_dir>/core/core.db。移行（runtime_data_migrate）が
# 有効化するまでは旧 shuki.db が正。タスク変更は board.db へ移るので core 側には作らない。
CORE_KEY = "core/core.db"
_LEGACY_DB_PATH = shuki_paths.VAULT / "99_System" / "db" / "shuki.db"


def _resolve():
    path = feature_db.feature_db(CORE_KEY, (_LEGACY_DB_PATH,))
    return _LEGACY_DB_PATH if path is None else path


DB_PATH = _resolve()
_INITIAL_DB_PATH = DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    result TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_job_started ON runs(job, started_at);
"""

# 2026-10-08: 読み手のいない複製だった2表を外す（Ren の判断「クイズ移行時に整理」）。クイズ解答の正は
# plugins/quiz/store.py（quiz.db）、スキル起動の正は skill-runs.jsonl（skill_recs.py が読む）。
RETIRED_TABLES = ("quiz_answers", "skill_runs")

# runs に後から足した列（既存DBには存在しないので接続時に埋める）。
# source値: "runner"=runner.py がその場で記録 / "dashboard"=対話ドックのジョブ完了時に記録
#           / "log_import"=既存 .log からの一括取り込み
# review: 1 なら「done したがユーザーの判断待ち」（選択肢が出た・要確認の言及がある等）。
#   完了/要レビュー/未完のラベルは result と review の組み合わせで決まる（dashboard_history 側と同じ判定）。
RUNS_ADDED_COLUMNS = {"source": "TEXT", "review": "INTEGER NOT NULL DEFAULT 0"}


def connect():
    """WAL mode の接続を返す。runner.py（書き込み）と dashboard_server.py（読み取り）の
    同時アクセスを想定し、デフォルトのロールバックジャーナルではなく WAL にする。
    """
    db_path = _resolve() if DB_PATH == _INITIAL_DB_PATH else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """後から足した列を既存DBへ反映する（SQLite に ADD COLUMN IF NOT EXISTS が無いため自前）。"""
    have = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    for col, decl in RUNS_ADDED_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {decl}")
    # 一括インポートの冪等性を DB 側で担保する。重複が既にある場合は張れないので黙って諦める
    # （その場合は import 側の in-memory 重複チェックだけが効く）。
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_runs ON runs(job, started_at)")
    except sqlite3.IntegrityError:
        pass
    for table in RETIRED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


def record_run(conn, job, started_at, ended_at, result, exit_code, error="", source="runner",
              review=False):
    conn.execute(
        "INSERT OR IGNORE INTO runs (job, started_at, ended_at, result, exit_code, error, source, review) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (job, started_at, ended_at, result, exit_code, error or None, source, 1 if review else 0),
    )
    conn.commit()


def recent_runs(conn, limit=30, since=None, source=None):
    """直近の実行結果を新しい順で返す（対話履歴UIの無人便パートに使う）。

    since（ISO日時文字列）指定時はそれ以降の ended_at のみ。source 指定時はその値のみ
    （例: "runner" だけに絞ると、5分おきの paper_bot 等 claude 不使用の高頻度バッチ
    （source="runner_py"）がLIMIT枠を埋めてしまう問題を避けられる）。
    """
    q = "SELECT job, started_at, ended_at, result, exit_code, error, source, review FROM runs"
    conds, params = [], []
    if since:
        conds.append("ended_at >= ?")
        params.append(since)
    if source:
        conds.append("source = ?")
        params.append(source)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY ended_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [
        {"job": r[0], "started_at": r[1], "ended_at": r[2], "result": r[3],
         "exit_code": r[4], "error": r[5], "source": r[6], "review": bool(r[7])}
        for r in rows
    ]
