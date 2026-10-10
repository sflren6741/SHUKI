#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_search.py — BM25 によるvault内ファイル検索（試作・2026-08-16）

設計の正: 04_Tasks/タスク管理/タスク/BM25でファイル検索のトークン消費を抑える.md
手法解説: 06_Resources/Resources/ナレッジ/BM25（Okapi BM25）.md

現状: トークナイザ（手順#1）＋索引ビルダ（手順#2）まで実装。BM25Fスコアラ・CLI検索は未着手。

使い方:
  python vault_search.py                # トークナイザのデモ（5例）
  python vault_search.py --build         # フルビルド(force)して索引を保存
  python vault_search.py --refresh       # 差分更新
  python vault_search.py --bench         # cold/warm/1ファイル更新の速度を実測
  （--all を付けると 99_System/08_Archive も索引対象に含める）
"""
import argparse
import re
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pickle
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shuki_core import vault as achievements  # noqa: E402  (read_text を再利用)
import shuki_paths  # noqa: E402
import vault_index  # noqa: E402  (VaultIndex._sweep / frontmatterパーサ を再利用)

# ── トークナイザ（手順#1） ──────────────────────────

_TOKEN_SCAN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]+")
_ASCII_WORD_RE = re.compile(r"^[A-Za-z0-9_]+$")
# camelCase境界: 小文字/数字→大文字の直前、および連続大文字→大文字+小文字の直前（例: HTTPServer）
_CAMEL_BOUNDARY_RE = [
    (re.compile(r"(?<=[a-z0-9])(?=[A-Z])"), " "),
    (re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])"), " "),
]


def _split_camel(word):
    s = word
    for pattern, repl in _CAMEL_BOUNDARY_RE:
        s = pattern.sub(repl, s)
    return s.split()


def _tokenize_ascii(word):
    lw = word.lower()
    parts = [p for p in word.split("_") if p]
    if len(parts) == 1:
        parts = [word]
    subs = []
    for p in parts:
        subs.extend(_split_camel(p))
    subs_lower = [s.lower() for s in subs if s]
    if subs_lower == [lw]:
        return [lw]
    return [lw] + subs_lower


def _cjk_bigrams(run):
    if len(run) <= 1:
        return [run] if run else []
    return [run[i:i + 2] for i in range(len(run) - 1)]


def tokenize(text):
    """テキストをBM25索引用トークン列に分割する。
    ASCII語は小文字化＋camelCase/snake_caseを全体＋構成語で登録、CJKは文字bi-gram。"""
    tokens = []
    for m in _TOKEN_SCAN_RE.finditer(text):
        word = m.group()
        if _ASCII_WORD_RE.match(word):
            tokens.extend(_tokenize_ascii(word))
        else:
            tokens.extend(_cjk_bigrams(word))
    return tokens


# ── 索引ビルダ（手順#2） ────────────────────────────

INDEX_FILE = shuki_paths.code_store("cache/vault_search_index.pkl")
DEFAULT_EXCLUDE_DIRS = {"99_System", "08_Archive"}  # 設計判断3: 機械ゾーン・物理アーカイブは既定除外
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


class SearchIndex:
    """BM25用の転置索引。フィールド別(path/title/tags/body)にトークン頻度を保持する。
    差分更新は vault_index.VaultIndex._sweep()（mtime+sizeスナップショット比較）をそのまま流用する。"""

    def __init__(self, vault=None, index_path=None, all_files=False):
        self.vault = Path(vault) if vault else vault_index.VAULT
        self.index_path = Path(index_path) if index_path else INDEX_FILE
        ignore_dirs = set(vault_index.IGNORE_DIRS)
        if not all_files:
            ignore_dirs |= DEFAULT_EXCLUDE_DIRS
        self._vidx = vault_index.VaultIndex(vault=self.vault, ignore_dirs=ignore_dirs)
        self.postings = {}   # token -> {path: {field: freq}}
        self.doc_meta = {}   # path -> {"field_tf": {field: Counter}, "field_len": {field: int}}
        self._sig = {}       # path -> [mtime_ns, size]（前回ビルド時のスナップショット）
        self._load()

    def refresh(self, force=False):
        t0 = time.time()
        sig_now = self._vidx._sweep()
        added = changed = removed = 0
        for rel in list(self.doc_meta.keys()):
            if rel not in sig_now:
                self._remove_doc(rel)
                removed += 1
        for rel, sig in sig_now.items():
            old = self._sig.get(rel)
            if force or old is None or list(old) != list(sig):
                existed = rel in self.doc_meta
                if self._index_doc(rel):
                    changed += 1 if existed else 0
                    added += 1 if not existed else 0
        self._sig = sig_now
        if force or added or changed or removed:
            self._save()
        return {"added": added, "changed": changed, "removed": removed,
                "docs": len(self.doc_meta), "ms": round((time.time() - t0) * 1000, 1)}

    def _index_doc(self, rel):
        self._remove_doc(rel)  # 既存があれば先に外してから再構築（idempotent）
        abspath = self.vault / rel
        text = achievements.read_text(abspath)
        fm_text, body = vault_index._split_fm_body(text)
        fm = vault_index.parse_frontmatter(fm_text) if fm_text else {}
        try:
            abspath.stat()
        except OSError:
            return False

        tag_values = list(fm.get("tags") or []) + list(fm.get("area") or [])
        if fm.get("category"):
            tag_values.append(str(fm["category"]))
        stem = rel[:-3] if rel.endswith(".md") else rel
        field_text = {
            "path": stem.replace("/", " "),
            "title": str(fm.get("title") or "") + " " + " ".join(_HEADING_RE.findall(body)),
            "tags": " ".join(str(v) for v in tag_values),
            "body": body,
        }
        field_tf, field_len = {}, {}
        for field, text_val in field_text.items():
            toks = tokenize(text_val)
            field_tf[field] = Counter(toks)
            field_len[field] = len(toks)

        self.doc_meta[rel] = {"field_tf": field_tf, "field_len": field_len}
        for field, tf in field_tf.items():
            for tok, freq in tf.items():
                self.postings.setdefault(tok, {}).setdefault(rel, {})[field] = freq
        return True

    def _remove_doc(self, rel):
        meta = self.doc_meta.pop(rel, None)
        if not meta:
            return
        for field, tf in meta["field_tf"].items():
            for tok in tf:
                docs = self.postings.get(tok)
                if docs and rel in docs:
                    del docs[rel]
                    if not docs:
                        del self.postings[tok]

    def _load(self):
        try:
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
            self.postings = data["postings"]
            self.doc_meta = data["doc_meta"]
            self._sig = data["sig"]
        except Exception:
            self.postings, self.doc_meta, self._sig = {}, {}, {}

    def _save(self):
        try:
            data = {"postings": self.postings, "doc_meta": self.doc_meta, "sig": self._sig}
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(self.index_path)
        except Exception:
            pass  # 索引書き込み失敗はプロセス自体を止めない（vault_index.pyと同じ流儀）


# ── BM25Fスコアラ（手順#3） ──────────────────────────
# 設計: 06_Resources/Resources/ナレッジ/BM25（Okapi BM25）.md §1,3②
# フィールド重みは「重み付きTFを合算してから飽和させる」＝スコア加算にしない（罠②）

K1 = 1.2
B = 0.75
FIELD_WEIGHTS = {"path": 3.0, "title": 2.5, "tags": 2.0, "body": 1.0}


def _avg_field_lens(doc_meta):
    sums = Counter()
    for meta in doc_meta.values():
        for field, length in meta["field_len"].items():
            sums[field] += length
    n = max(1, len(doc_meta))
    return {field: (sums[field] / n) or 1.0 for field in FIELD_WEIGHTS}


def bm25f_search(index, query_tokens, k=8):
    """クエリトークン列に対しBM25Fスコアで文書をランキングして返す。
    戻り値: [(rel_path, score), ...] score降順。"""
    doc_meta = index.doc_meta
    postings = index.postings
    n_docs = len(doc_meta)
    if n_docs == 0 or not query_tokens:
        return []
    avg_len = _avg_field_lens(doc_meta)

    # 対象文書を候補に絞る（クエリ語をどれか1つでも含む文書のみ）
    candidates = set()
    for tok in query_tokens:
        candidates |= set(postings.get(tok, {}).keys())
    if not candidates:
        return []

    scores = {}
    q_counts = Counter(query_tokens)
    for q_tok, q_freq in q_counts.items():
        docs_with_tok = postings.get(q_tok, {})
        n_q = len(docs_with_tok)
        if n_q == 0:
            continue
        # 罠①: IDFが負にならないよう非負版を使う
        idf = __import__("math").log(1 + (n_docs - n_q + 0.5) / (n_q + 0.5))
        for rel in candidates:
            field_freqs = docs_with_tok.get(rel)
            if not field_freqs:
                continue
            meta = doc_meta[rel]
            # 罠②: フィールド毎に別スコアを出して足すのではなく、
            # 重み付きTF（各フィールドの長さ正規化込み）を先に合算してから飽和させる
            f_combined = 0.0
            for field, freq in field_freqs.items():
                w = FIELD_WEIGHTS.get(field, 1.0)
                dlen = meta["field_len"].get(field, 0)
                norm = (1 - B + B * (dlen / avg_len[field])) if avg_len[field] else 1.0
                f_combined += w * freq / norm
            saturated = (f_combined * (K1 + 1)) / (f_combined + K1)
            scores[rel] = scores.get(rel, 0.0) + idf * saturated * q_freq

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:k]


# ── CLI ──────────────────────────────────────────────

def _cmd_bench(all_files=False):
    bench_path = shuki_paths.code_store("cache/vault_search_index_bench.pkl")
    idx = SearchIndex(index_path=bench_path, all_files=all_files)
    r1 = idx.refresh(force=True)
    print(f"cold build: {r1['ms']}ms  docs={r1['docs']}")

    r2 = idx.refresh(force=False)
    print(f"warm (no changes): {r2['ms']}ms")

    if idx.doc_meta:
        any_path = next(iter(idx.doc_meta))
        # 実ファイルのmtimeには触れず、sigだけ古い値にして「1ファイル変更」をシミュレートする
        idx._sig[any_path] = [0, 0]
        r3 = idx.refresh(force=False)
        print(f"1-file update (simulated): {r3['ms']}ms  changed={r3['changed']}")

    try:
        bench_path.unlink()
    except OSError:
        pass


SNIPPET_CHARS = 160
DEFAULT_TOPK = 8
OUTPUT_BYTE_CAP = 2048
LOG_FILE = shuki_paths.system_dir_for(vault_index.VAULT) / "agent-runs" / "vault_search_calls.log"


def _make_snippet(vault, rel, query_tokens):
    try:
        text = achievements.read_text(vault / rel)
    except Exception:
        return ""
    _, body = vault_index._split_fm_body(text)
    lower = body.lower()
    pos = -1
    for tok in query_tokens:
        if len(tok) < 2:
            continue
        p = lower.find(tok)
        if p != -1:
            pos = p
            break
    if pos == -1:
        snippet = body[:SNIPPET_CHARS]
    else:
        start = max(0, pos - SNIPPET_CHARS // 3)
        snippet = body[start:start + SNIPPET_CHARS]
    return " ".join(snippet.split())


def _log_call(query, area, n_results):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts}\tvault_search\tquery={query!r}\tarea={area}\tresults={n_results}\n")
    except Exception:
        pass  # ログ失敗で検索そのものを止めない


def _cmd_query(query, k=DEFAULT_TOPK, area=None, all_files=False, as_json=False):
    idx = SearchIndex(all_files=all_files)
    idx.refresh(force=False)  # 差分更新してから検索（索引が古いままヒットしないのを防ぐ）
    query_tokens = tokenize(query)

    candidates = idx.doc_meta
    if area:
        filtered = {}
        for rel, meta in idx.doc_meta.items():
            tag_tf = meta["field_tf"].get("tags", {})
            if any(area.lower() in tok for tok in tag_tf):
                filtered[rel] = meta
        # フィルタ済みの一時インデックスで検索（postingsは共有、doc_metaだけ絞る）
        idx2 = SearchIndex.__new__(SearchIndex)
        idx2.doc_meta = filtered
        idx2.postings = idx.postings
        candidates = filtered
        ranked = bm25f_search(idx2, query_tokens, k=k)
    else:
        ranked = bm25f_search(idx, query_tokens, k=k)

    results = []
    for rel, score in ranked:
        results.append({
            "path": rel,
            "score": round(score, 4),
            "snippet": _make_snippet(idx.vault, rel, query_tokens),
        })

    _log_call(query, area or "-", len(results))

    if as_json:
        import json
        # 構造を壊さないよう、バイト上限を超える間は末尾の結果を1件ずつ落とす（生文字列の途中切りはしない）
        trimmed = list(results)
        out = json.dumps(trimmed, ensure_ascii=False)
        while len(out.encode("utf-8")) > OUTPUT_BYTE_CAP and len(trimmed) > 1:
            trimmed.pop()
            out = json.dumps(trimmed, ensure_ascii=False)
        print(out)
        return

    lines = [f"[{r['score']:.3f}] {r['path']}\n    {r['snippet']}" for r in results]
    out = "\n".join(lines) if lines else "(該当なし)"
    out_bytes = out.encode("utf-8")
    if len(out_bytes) > OUTPUT_BYTE_CAP:
        out = out_bytes[:OUTPUT_BYTE_CAP].decode("utf-8", errors="ignore") + "\n...(出力上限2KBで切り詰め)"
    print(out)


def _cmd_tokenize_demo():
    samples = [
        "getUserProfile",
        "時間管理の工夫",
        "BM25",
        "getUserProfile 時間管理の工夫を調べる",
        "あ",
    ]
    for s in samples:
        print(f"{s!r} -> {tokenize(s)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="フルビルド(force)して索引を保存")
    ap.add_argument("--refresh", action="store_true", help="差分更新")
    ap.add_argument("--bench", action="store_true", help="cold/warm/1ファイル更新の速度を実測")
    ap.add_argument("--all", action="store_true", help="99_System/08_Archiveも索引対象に含める")
    ap.add_argument("query", nargs="?", help="検索クエリ（指定するとBM25F検索を実行）")
    ap.add_argument("-k", type=int, default=DEFAULT_TOPK, help="上位何件を返すか（既定8）")
    ap.add_argument("--area", help="areaタグで絞り込み")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON形式で出力")
    args = ap.parse_args()

    if args.build:
        idx = SearchIndex(all_files=args.all)
        print(idx.refresh(force=True))
    elif args.refresh:
        idx = SearchIndex(all_files=args.all)
        print(idx.refresh(force=False))
    elif args.bench:
        _cmd_bench(all_files=args.all)
    elif args.query:
        _cmd_query(args.query, k=args.k, area=args.area, all_files=args.all, as_json=args.as_json)
    else:
        _cmd_tokenize_demo()
