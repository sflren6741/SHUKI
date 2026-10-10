# -*- coding: utf-8 -*-
"""ChatGPT / Claude のエクスポート（zip か json）から「自分の発言」だけを読む。

- AI の返答は読まない。ネットワークにも AI にも触れない（標準ライブラリのみ）。
- 数百MBの conversations.json を丸ごとは読み込まない（トップレベル配列を1件ずつ読む）。
- 圧縮爆弾対策: zip は展開せず、実際に読んだバイト数で上限をかける。
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

MAX_DOCS = 4000
MAX_CHARS_PER_DOC = 30_000
MAX_TOTAL_CHARS = 12_000_000
MAX_MSG_CHARS = 8_000
MAX_JSON_BYTES = 250 * 1024 * 1024
MAX_ITEM_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 40
CHUNK = 1 << 20

_MEMBER = re.compile(r"^conversations(?:-\d+)?\.json$", re.I)
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+")
_SPACES = re.compile(r"[ \t　]+")
_BLANKS = re.compile(r"\n{3,}")
_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_SAFE_NAME = re.compile(r"[^0-9A-Za-z._\-ぁ-んァ-ヶー一-龠 ]")


class ExportError(Exception):
    """読めないファイル。メッセージは画面にそのまま出せる日本語。"""


class _Capped(io.RawIOBase):
    def __init__(self, src, limit):
        super().__init__()
        self._src, self._limit, self.count = src, limit, 0

    def readable(self):
        return True

    def readinto(self, b):
        data = self._src.read(len(b))
        if not data:
            return 0
        self.count += len(data)
        if self.count > self._limit:
            raise ExportError("ファイルが大きすぎます（展開後 %dMB 超）。" % (self._limit >> 20))
        b[: len(data)] = data
        return len(data)


def iter_json_array(fp, chunk=CHUNK, max_item=MAX_ITEM_BYTES, limit=MAX_JSON_BYTES):
    """バイナリの file-like からトップレベル配列の要素を1件ずつ返す。

    先頭が { なら全体を1要素として返す。要素が chunk を超えるときは読み足しを倍々にして、
    再パースの回数を対数に抑える。
    """
    dec = json.JSONDecoder()
    raw = _Capped(fp, limit)
    rd = io.TextIOWrapper(io.BufferedReader(raw), encoding="utf-8-sig", errors="replace", newline="")
    st = {"buf": "", "pos": 0, "eof": False}

    def fill(n):
        if st["eof"]:
            return False
        data = rd.read(n)
        if not data:
            st["eof"] = True
            return False
        st["buf"] = st["buf"][st["pos"]:] + data
        st["pos"] = 0
        return True

    def skip(chars):
        while True:
            b, p = st["buf"], st["pos"]
            while p < len(b) and (b[p].isspace() or b[p] in chars):
                p += 1
            st["pos"] = p
            if p < len(b):
                return True
            if not fill(chunk):
                return False

    if not skip(""):
        raise ExportError("空のファイルです。")
    if st["buf"][st["pos"]] == "{":
        while True:
            try:
                obj, _ = dec.raw_decode(st["buf"], st["pos"])
                yield obj
                return
            except json.JSONDecodeError:
                if not fill(max(chunk, len(st["buf"]))):
                    raise ExportError("JSON として読めませんでした。")
    if st["buf"][st["pos"]] != "[":
        raise ExportError("JSON の配列として読めませんでした。")
    st["pos"] += 1
    while True:
        if not skip(","):
            raise ExportError("JSON が途中で終わっています。")
        if st["buf"][st["pos"]] == "]":
            return
        while True:
            try:
                obj, end = dec.raw_decode(st["buf"], st["pos"])
                break
            except json.JSONDecodeError:
                if len(st["buf"]) - st["pos"] > max_item:
                    raise ExportError("1件が大きすぎるか、JSON が壊れています。")
                if not fill(max(chunk, len(st["buf"]) - st["pos"])):
                    raise ExportError("JSON が途中で終わっているか、壊れています。")
        st["pos"] = end
        yield obj


def clean(text):
    """マイニング用の本文: NFKC正規化、コード・URLを除く。"""
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = _FENCE.sub(" ", t)
    t = _INLINE_CODE.sub(" ", t)
    t = _URL.sub(" ", t)
    t = _SPACES.sub(" ", t)
    t = "\n".join(line.strip() for line in t.split("\n"))
    return _BLANKS.sub("\n\n", t).strip()


def _epoch_date(v):
    try:
        return datetime.fromtimestamp(float(v)).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _iso_date(v):
    s = str(v or "")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        m = _ISO_DATE.match(s)
        return m.group(1) if m else ""


def _chatgpt_texts(conv):
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return []
    order, seen = [], set()
    node = conv.get("current_node")
    while isinstance(node, str) and node in mapping and node not in seen and len(seen) < 100_000:
        seen.add(node)
        order.append(node)
        node = (mapping[node] or {}).get("parent")
    if order:
        order.reverse()
    else:
        order = list(mapping)
    out = []
    for nid in order:
        msg = (mapping.get(nid) or {}).get("message")
        if not isinstance(msg, dict) or (msg.get("author") or {}).get("role") != "user":
            continue
        meta = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
        if meta.get("is_user_system_message") or meta.get("is_visually_hidden_from_conversation"):
            continue
        content = msg.get("content") if isinstance(msg.get("content"), dict) else {}
        if content.get("content_type") not in ("text", "multimodal_text"):
            continue
        parts = content.get("parts")
        if isinstance(parts, list):
            out.append("\n".join(p for p in parts if isinstance(p, str)))
    return out


def _claude_texts(conv):
    out = []
    for m in conv.get("chat_messages") or []:
        if not isinstance(m, dict) or m.get("sender") != "human":
            continue
        blocks = m.get("content")
        texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("type") == "text"] if isinstance(blocks, list) else []
        texts = [t for t in texts if isinstance(t, str)]
        out.append("\n".join(texts) if texts else (m.get("text") if isinstance(m.get("text"), str) else ""))
    return out


def conversation_doc(conv):
    """1会話 → {"id","title","date","text","source"}。読めない/空なら None。"""
    if not isinstance(conv, dict):
        return None
    if "mapping" in conv:
        source, raws = "chatgpt", _chatgpt_texts(conv)
        cid = conv.get("conversation_id") or conv.get("id") or ""
        title, date = conv.get("title"), _epoch_date(conv.get("create_time"))
    elif "chat_messages" in conv:
        source, raws = "claude", _claude_texts(conv)
        cid = conv.get("uuid") or ""
        title, date = conv.get("name"), _iso_date(conv.get("created_at"))
    else:
        return None
    kept = [t for t in (clean(r) for r in raws if len(r) <= MAX_MSG_CHARS) if t]
    if not kept:
        return None
    text = "\n\n".join(kept)[:MAX_CHARS_PER_DOC]
    return {"id": str(cid), "title": clean(title or "")[:80], "date": date, "text": text, "source": source,
            "skipped_long": sum(1 for r in raws if len(r) > MAX_MSG_CHARS)}


def _members(zf):
    infos = [i for i in zf.infolist() if not i.is_dir() and _MEMBER.match(Path(i.filename).name)]
    if not infos:
        raise ExportError("zip の中に conversations.json が見つかりません（ChatGPT / Claude のエクスポートを選んでください）。")
    if len(infos) > MAX_MEMBERS:
        raise ExportError("conversations ファイルが多すぎます。")
    for i in infos:
        if i.file_size > MAX_JSON_BYTES:
            raise ExportError("%s が大きすぎます。" % Path(i.filename).name)
    return infos


def _open_sources(path):
    """(名前, 開く関数) の列。zip でも json でも同じ形で返す。"""
    p = Path(path)
    if p.suffix.lower() == ".zip":
        try:
            zf = zipfile.ZipFile(p)
        except (zipfile.BadZipFile, OSError):
            raise ExportError("zip として読めませんでした。")
        try:
            members = _members(zf)
        except BaseException:
            zf.close()
            raise
        return zf, [(Path(i.filename).name, (lambda i=i: zf.open(i))) for i in members]
    if p.suffix.lower() == ".json":
        return None, [(p.name, lambda: open(p, "rb"))]
    raise ExportError("zip か json を選んでください。")


def read_export(path, progress=None):
    """→ {"docs": [...], "stats": {...}}。progress(n_docs) は任意。

    docs は date 昇順（日付なしは先頭）。上限に達したら stats["truncated"]=True。
    """
    zf, sources = _open_sources(path)
    docs, seen, total = [], set(), 0
    stats = {"conversations": 0, "kept": 0, "skipped_long": 0, "sources": {}, "truncated": False}
    try:
        for name, opener in sources:
            with opener() as fp:
                for conv in iter_json_array(fp):
                    stats["conversations"] += 1
                    d = conversation_doc(conv)
                    if not d:
                        continue
                    key = d["source"] + ":" + d["id"] if d["id"] else None
                    if key and key in seen:
                        continue
                    seen.add(key)
                    stats["skipped_long"] += d.pop("skipped_long")
                    stats["sources"][d["source"]] = stats["sources"].get(d["source"], 0) + 1
                    docs.append(d)
                    total += len(d["text"])
                    if progress:
                        progress(len(docs))
                    if len(docs) >= MAX_DOCS or total >= MAX_TOTAL_CHARS:
                        stats["truncated"] = True
                        break
            if stats["truncated"]:
                break
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError, OSError):
        raise ExportError("ファイルを読み出せませんでした（壊れているか、パスワード付きの可能性があります）。")
    finally:
        if zf:
            zf.close()
    if not docs:
        raise ExportError("ChatGPT / Claude のエクスポートとして読めませんでした（自分の発言が見つかりません）。")
    docs.sort(key=lambda d: (d["date"], d["id"]))
    stats["kept"] = len(docs)
    return {"docs": docs, "stats": stats}


def safe_name(name, default="export"):
    """アップロード名を安全な basename にする。拡張子は zip/json のみ残す。"""
    base = re.split(r"[\\/]", str(name or ""))[-1]
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = _SAFE_NAME.sub("_", stem).strip(" ._")[:60] or default
    ext = ext.lower() if ext.lower() in ("zip", "json") else ""
    return stem + ("." + ext if ext else "")
