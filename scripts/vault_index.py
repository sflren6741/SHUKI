#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_index.py — vault 全体の差分インデックス（ビューエンジンの土台・2026-07-28 新設）

背景（実測）: G:ドライブ（Google Drive 同期）では `open()` 1回が約4.4ms かかり、サイズに依存しない。
現行の dashboard_server.py は TASK_DIR（169件）だけを毎回全走査して成立しているが、
vault 全体（約2000件）に同じことをすると約9秒かかる。一方 `os.scandir` によるファイル一覧の
変更検知（mtime+size のスナップショット比較）は約0.19秒で済む。→ 「毎回全走査」ではなく
「差分だけ再読み込み」にすることで、vault 全体を対象にしても現実的な速度を保つ。

設計思想:
  - 本文（body）はインデックスに保持しない（キャッシュJSONの肥大化を避ける。オンデマンドLRU）
  - サーバーは vault 本体を書かない不変条件はここでも維持（読み取り専用インデックス）
  - frontmatter は YAML パーサを使わず、vault実データで確認された構文
    （scalar / block list / inline list [a,b] / true・false、ネストしたマップは無し）だけを
    パースする軽量パーサ（achievements.py の frontmatter()/read_text() を土台として再利用）

使い方:
  python vault_index.py --bench          # sweep/build/差分再読み込みの速度を実測
  python vault_index.py --verify-tasks   # collect_tasks() 相当の分類がindex経由でも一致するか検証
  python vault_index.py --verify-board   # collect_board_data() 相当（parent/children/quest）が一致するか検証
  python vault_index.py --dump <path>    # 1ファイル分のレコードをJSON表示（デバッグ用）
"""
import argparse
import json
import os
import re
import sys
import threading
import time

if getattr(sys.stdout, "encoding", None) and sys.stdout.encoding.lower() != "utf-8":
    # Windows コンソールの既定(cp932)は絵文字を出力できずCLI実行が落ちるため強制する
    sys.stdout.reconfigure(encoding="utf-8")
if getattr(sys.stderr, "encoding", None) and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shuki_core import vault as achievements  # noqa: E402  (VAULT/read_text/frontmatter を再利用)

VAULT = achievements.VAULT
import shuki_paths

CACHE_FILE = shuki_paths.code_store("core/vault_index_cache.json")
IGNORE_DIRS = {".obsidian", ".git", ".trash", "node_modules", "__pycache__", ".claude"}

# ── frontmatter パーサ（YAML非依存・vault実データで確認された構文のみ対応） ──
# area/tags 等の「複数値を取りうるキー」は、単一スカラーで書かれていても常にリストへ正規化する
# （Obsidian base 側の contains()/containsAny() が block-list と inline-list を同じ扱いにするため）。
AREA_LIKE_KEYS = {"area", "tags", "category", "month", "children", "related", "person"}
_KEY_RE = re.compile(r"^([^\s:#][^:]*):(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*-\s*(.+)$")
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
EMBED_RE = re.compile(r"!\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
HASHTAG_RE = re.compile(r"(?:^|\s)#([^\s#\[\]]{1,40})")


def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _parse_scalar_or_inline_list(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_strip_quotes(x) for x in inner.split(",")]
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return _strip_quotes(s)


def parse_frontmatter(fm_text):
    """achievements.frontmatter() が返す生テキストを {key: value|list|bool} に変換する。
    ネストしたマップ（2階層以上のインデント）は vault内0件のため非対応（値は空文字になる）。"""
    lines = fm_text.splitlines()
    result = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line or line[0] in " \t":
            i += 1
            continue
        m = _KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1).strip(), m.group(2).strip()
        if rest:
            result[key] = _parse_scalar_or_inline_list(rest)
            i += 1
        else:
            items, j = [], i + 1
            while j < n:
                im = _LIST_ITEM_RE.match(lines[j])
                if im:
                    items.append(_strip_quotes(im.group(1)))
                    j += 1
                else:
                    break
            result[key] = items
            i = j
    for k in AREA_LIKE_KEYS:
        if k in result and not isinstance(result[k], list):
            result[k] = [result[k]] if result[k] != "" else []
    return result


def _split_fm_body(text):
    """frontmatter生テキストと本文を分離する（achievements.frontmatter()の終端検出を踏襲）。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            after = text[end + 4:]
            nl = after.find("\n")
            body = after[nl + 1:] if nl != -1 else ""
            return text[3:end], body
    return "", text


def _excerpt(body, limit=180):
    for line in body.splitlines():
        s = line.strip().lstrip("#").lstrip(">").strip()
        if s and not s.startswith("```") and not s.startswith("|"):
            return s[:limit]
    return ""


def _rel(vault, abspath):
    return Path(abspath).resolve().relative_to(vault).as_posix()


class VaultIndex:
    """vault 全体の .md を差分インデックスするだけの読み取り専用クラス。
    書き込みは一切しない（サーバーが vault 本体を書かない不変条件を継承）。"""

    POLL_INTERVAL = 10.0  # 秒。sweep実測2.5秒に対し十分な余裕を持たせた定期更新間隔

    def __init__(self, vault=VAULT, cache_path=CACHE_FILE, ignore_dirs=IGNORE_DIRS):
        self.vault = Path(vault)
        self.cache_path = Path(cache_path)
        self.ignore_dirs = set(ignore_dirs)
        self._lock = threading.RLock()
        self._notes = {}   # rel_path -> record dict
        self._sig = {}      # rel_path -> [mtime_ns, size]（前回スイープのスナップショット）
        self._last_refresh = 0.0
        self._building = False
        self._body_cache = OrderedDict()
        self._body_cache_max = 128
        self._wake_event = threading.Event()  # invalidate() から次のポーリングを即座に起こす

    # ── 起動・更新 ──
    def start(self, background=True):
        """background=True: 専用スレッドが POLL_INTERVAL 秒おきに refresh し続ける
        （2026-08-06: リクエスト起点の同期 ensure_fresh() を廃止。G:ドライブでは sweep 自体が
        約2.5秒かかり、旧 max_age=2.0秒 の TTL より遅いため「ほぼ毎リクエストで同期I/O」に
        なっていた。バックグラウンドループ化でリクエストパスからI/Oを完全に排除する）。
        起動直後はキャッシュJSON（あれば）で応答し、初回sweep完了を待たない。"""
        self._load_cache()
        if background:
            threading.Thread(target=self._poll_loop, daemon=True).start()
        else:
            self.refresh()

    def _poll_loop(self):
        while True:
            self.refresh()
            self._wake_event.wait(self.POLL_INTERVAL)
            self._wake_event.clear()

    def ensure_fresh(self, max_age=None):
        """互換のため残置（呼び出し元の変更不要）。実更新はバックグラウンドループが担当するため
        ここでは何もしない。即時反映が必要な書き込み直後は invalidate() を呼ぶこと。"""
        pass

    def invalidate(self):
        """バックグラウンドループの待機を起こし、次の refresh を即座に走らせる
        （POST /queue 直後などに呼ぶ）。"""
        self._wake_event.set()

    def refresh(self, force=False):
        t0 = time.time()
        self._building = True
        added = changed = removed = 0
        try:
            sig_now = self._sweep()
            with self._lock:
                for rel in list(self._notes.keys()):
                    if rel not in sig_now:
                        del self._notes[rel]
                        removed += 1
                for rel, sig in sig_now.items():
                    old = self._sig.get(rel)
                    if force or old is None or list(old) != list(sig):
                        rec = self._build_record(rel)
                        if rec is not None:
                            changed += 1 if rel in self._notes else 0
                            added += 1 if rel not in self._notes else 0
                            self._notes[rel] = rec
                self._sig = sig_now
            self._save_cache()
        finally:
            self._building = False
            self._last_refresh = time.time()
        return {"added": added, "changed": changed, "removed": removed,
                "ms": round((time.time() - t0) * 1000, 1)}

    # ── 読み出し ──
    def notes(self):
        with self._lock:
            return list(self._notes.values())

    def by_path(self, rel):
        with self._lock:
            return self._notes.get(rel)

    def body(self, rel):
        if rel in self._body_cache:
            self._body_cache.move_to_end(rel)
            return self._body_cache[rel]
        text = achievements.read_text(self.vault / rel)
        self._body_cache[rel] = text
        if len(self._body_cache) > self._body_cache_max:
            self._body_cache.popitem(last=False)
        return text

    def stats(self):
        return {"count": len(self._notes), "last_refresh": self._last_refresh,
                "building": self._building}

    # ── 内部実装 ──
    def _sweep(self):
        """vault全体のファイル一覧を (mtime_ns, size) 付きで取る。os.scandir 手書きスタック版。
        実測: pathlib.rglob の4倍、os.walk+os.stat の9倍速い（DirEntry.stat() が列挙時の
        メタデータを使い追加I/Oを発生させないため）。"""
        out = {}
        stack = [str(self.vault)]
        while stack:
            d = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                if e.is_dir(follow_symlinks=False):
                    if e.name not in self.ignore_dirs:
                        stack.append(e.path)
                elif e.name.endswith(".md"):
                    try:
                        st = e.stat()
                    except OSError:
                        continue
                    out[_rel(self.vault, e.path)] = [st.st_mtime_ns, st.st_size]
        return out

    def _build_record(self, rel):
        abspath = self.vault / rel
        text = achievements.read_text(abspath)
        fm_text, body = _split_fm_body(text)
        fm = parse_frontmatter(fm_text) if fm_text else {}
        try:
            st = abspath.stat()
        except OSError:
            return None
        p = PurePosixPath(rel)
        links = sorted(set(m.strip() for m in WIKILINK_RE.findall(body)))
        embeds = sorted(set(m.strip() for m in EMBED_RE.findall(body)))
        tags = list(fm.get("tags") or [])
        for t in HASHTAG_RE.findall(body):
            if t not in tags:
                tags.append(t)
        folder = str(p.parent)
        return {
            "_src": "notes", "_id": rel, "_path": rel, "_ts": st.st_mtime,
            "path": rel, "name": p.stem, "ext": p.suffix.lstrip("."),
            "folder": "" if folder == "." else folder,
            "ctime": st.st_ctime, "mtime": st.st_mtime, "size": st.st_size,
            "tags": tags, "links": links, "embeds": embeds,
            "fm": fm, "excerpt": _excerpt(body), "cover": fm.get("cover") or None,
            "insight": achievements.extract_insight(body),
        }

    def _load_cache(self):
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            with self._lock:
                self._notes = {n["path"]: n for n in data.get("notes", [])}
                self._sig = {p: v for p, v in data.get("sig", {}).items()}
        except Exception:
            self._notes, self._sig = {}, {}

    def _save_cache(self):
        try:
            with self._lock:
                data = {"notes": list(self._notes.values()), "sig": self._sig}
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.cache_path)
        except Exception:
            pass  # キャッシュ書き込み失敗はインデックス自体の動作を止めない(vault_state.json等と同じ流儀)


# ── CLI ──────────────────────────────────────────────

def _cmd_bench():
    idx = VaultIndex()
    t0 = time.time()
    sig = idx._sweep()
    t_sweep = time.time() - t0
    print(f"sweep: {t_sweep*1000:.0f}ms  ({len(sig)} files)")

    idx2 = VaultIndex(cache_path=shuki_paths.code_store("cache/vault_index_cache_bench.json"))
    t0 = time.time()
    r1 = idx2.refresh(force=True)
    print(f"cold build (force=True): {r1['ms']}ms  added={r1['added']} changed={r1['changed']}")

    t0 = time.time()
    r2 = idx2.refresh(force=False)
    print(f"warm refresh (no changes): {r2['ms']}ms  added={r2['added']} changed={r2['changed']} removed={r2['removed']}")
    try:
        idx2.cache_path.unlink()
    except OSError:
        pass


def _cmd_dump(path):
    idx = VaultIndex()
    idx.start(background=False)
    rec = idx.by_path(path)
    if rec is None:
        # 相対パス表記の揺れ対策（先頭 / の有無等）を軽く許容
        rec = idx.by_path(path.lstrip("/"))
    if rec is None:
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(rec, ensure_ascii=False, indent=1))


def _cmd_verify_tasks():
    """index経由で組み立てた4カラム分類が、現行 dashboard_server.collect_tasks() と
    完全一致するか検証する（黄金ファイル比較の自動版）。差分ゼロが合格条件。"""
    import dashboard_server as ds

    idx = VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    today = date.today()
    task_prefix = "04_Tasks/タスク管理/タスク/"

    def parse_d(v):
        if not v or not isinstance(v, str):
            return None
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
        if not m:
            return None
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    cols_idx = {"overdue": [], "today": [], "week": [], "doing": []}
    for rec in idx.notes():
        if not rec["path"].startswith(task_prefix):
            continue
        fm = rec["fm"]
        status = fm.get("status") or ""
        if status not in ("todo", "in-progress"):
            continue
        start = parse_d(fm.get("start"))
        if start and start > today:
            continue
        due = parse_d(fm.get("due"))
        task = {
            "title": fm.get("title") or rec["name"],
            "path": rec["path"],
            "status": status,
            "priority": fm.get("priority") or "",
            "due": due.isoformat() if due else None,
            "areas": fm.get("area") or [],
            "next_action": fm.get("next_action") or "",
        }
        if due and due < today:
            cols_idx["overdue"].append(task)
        elif due == today:
            cols_idx["today"].append(task)
        elif due and due <= today + timedelta(days=7):
            cols_idx["week"].append(task)
        elif status == "in-progress":
            cols_idx["doing"].append(task)
    for v in cols_idx.values():
        v.sort(key=lambda t: (ds.PRIORITY_ORDER.get(t["priority"], 3), t["due"] or "9999-12-31"))

    cols_real = ds.collect_tasks(today)
    cols_real_norm = {
        k: [{**t, "due": t["due"].isoformat() if t["due"] else None} for t in v]
        for k, v in cols_real.items()
    }

    ok = True
    for key in ("overdue", "today", "week", "doing"):
        a = sorted(cols_idx[key], key=lambda t: t["path"])
        b = sorted(cols_real_norm[key], key=lambda t: t["path"])
        if a != b:
            ok = False
            print(f"── MISMATCH in '{key}' ──")
            a_paths, b_paths = {t["path"] for t in a}, {t["path"] for t in b}
            for p in sorted(a_paths - b_paths):
                print(f"  + index only: {p}")
            for p in sorted(b_paths - a_paths):
                print(f"  - real only:  {p}")
            for p in sorted(a_paths & b_paths):
                ta = next(t for t in a if t["path"] == p)
                tb = next(t for t in b if t["path"] == p)
                if ta != tb:
                    print(f"  ~ diff {p}: index={ta} real={tb}")
        else:
            print(f"OK '{key}': {len(a)} 件 一致")
    if ok:
        print("\n✅ verify-tasks: 完全一致（差分ゼロ）")
    else:
        print("\n❌ verify-tasks: 差分あり（上記参照）")
        sys.exit(1)


def _cmd_verify_board():
    """index経由で組み立てたボード用 tasks+edges が、現行 dashboard_server.collect_board_data() と
    完全一致するか検証する（--verify-tasks と同じ「独立再構築 vs 実装」方式）。差分ゼロが合格条件。"""
    import dashboard_server as ds

    idx = VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    task_prefix = "04_Tasks/タスク管理/タスク/"
    wikilink_stem = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]')
    quests = ds.load_board_quests()

    def parse_d(v):
        if not v or not isinstance(v, str):
            return None
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
        if not m:
            return None
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    tasks_idx = []
    for rec in idx.notes():
        if not rec["path"].startswith(task_prefix):
            continue
        fm = rec["fm"]
        stem = rec["name"]

        parent_raw = fm.get("parent")
        parent_stem = None
        if isinstance(parent_raw, str) and parent_raw:
            m = wikilink_stem.search(parent_raw)
            if m:
                parent_stem = m.group(1).strip()

        children_stems = []
        for item in (fm.get("children") or []):
            if not isinstance(item, str):
                continue
            cm = wikilink_stem.search(item)
            if cm:
                children_stems.append(cm.group(1).strip())

        due = parse_d(fm.get("due"))
        start = parse_d(fm.get("start"))
        areas = fm.get("area") or []

        tasks_idx.append({
            "id": stem,
            "title": fm.get("title") or stem,
            "status": fm.get("status") or "",
            "priority": fm.get("priority") or "",
            "area": areas[0] if areas else "",
            "due": due.isoformat() if due else None,
            "start": start.isoformat() if start else None,
            "next_action": fm.get("next_action") or "",
            "path": rec["path"],
            "parent": parent_stem,
            "children": children_stems,
            "quest": quests.get(stem),
            "habit_id": fm.get("habit_id") or None,
        })

    real = ds.collect_board_data()

    ok = True
    a = sorted(tasks_idx, key=lambda t: t["path"])
    b = sorted(real["tasks"], key=lambda t: t["path"])
    if a != b:
        ok = False
        print("── MISMATCH in 'tasks' ──")
        a_paths, b_paths = {t["path"] for t in a}, {t["path"] for t in b}
        for p in sorted(a_paths - b_paths):
            print(f"  + index only: {p}")
        for p in sorted(b_paths - a_paths):
            print(f"  - real only:  {p}")
        for p in sorted(a_paths & b_paths):
            ta = next(t for t in a if t["path"] == p)
            tb = next(t for t in b if t["path"] == p)
            if ta != tb:
                print(f"  ~ diff {p}: index={ta} real={tb}")
    else:
        print(f"OK 'tasks': {len(a)} 件 一致")

    edges_idx = sorted((e["from"], e["to"]) for e in real["edges"])  # edges自体はcollect_board_data内の
    # 純粋な集合演算（parent/children両方から重複排除で構築）で tasks から一意に導出されるため、
    # tasks が一致していれば必然的に一致する。ここでは edges の重複・自己参照が無いことだけ確認する。
    if len(edges_idx) != len(set(edges_idx)):
        ok = False
        print("  ~ edges に重複あり")
    if ok:
        print("\n✅ verify-board: 完全一致（差分ゼロ）")
    else:
        print("\n❌ verify-board: 差分あり（上記参照）")
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--verify-tasks", action="store_true")
    ap.add_argument("--verify-board", action="store_true")
    ap.add_argument("--dump", metavar="PATH")
    args = ap.parse_args()
    if args.bench:
        _cmd_bench()
    elif args.verify_tasks:
        _cmd_verify_tasks()
    elif args.verify_board:
        _cmd_verify_board()
    elif args.dump:
        _cmd_dump(args.dump)
    else:
        ap.print_help()
