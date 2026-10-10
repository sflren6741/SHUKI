#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shuki_i18n.py — SHUKI の表示言語切り替え（2026-08-11新設・2026-09-13 設定メニュー連動化）。

背景：英語版を SHUKI-EN として別リポジトリにフォークし、日本語文字列を手で置換していたため、
片方だけが古くなる／同じ修正を2回する状態になっていた。表面の言語をコードから切り離し、
リポジトリを1本に戻すためのモジュール。

## 設計（日本語原文をキーにするオーバーレイ辞書）

`t("期限切れ")` は lang=ja ならそのまま "期限切れ" を返し、lang=en なら en.json の対訳を返す。
**辞書に無ければ原文をそのまま返す**＝未翻訳箇所は日本語のまま表示されるだけで壊れない。
これにより 1,100 超あるUI文字列を一度に訳す必要がなくなり、ページ単位で段階移行できる。

キーを別途設計しない（`board.col.overdue` のような命名をしない）のは意図的：
移行対象が多く、キー設計そのものが投資過剰になるため。原文を書き換えると辞書が切れるので、
`i18n_scan.py` で「辞書に無いUI文字列」を検出できるようにしてある。

## 2つの適用口

| 関数 | 対象 | 例 |
|---|---|---|
| `t(s)` | Python の文字列リテラルとして独立しているラベル | `t("期限切れ")` |
| `tt(template)` | 静的HTMLテンプレート（`\"\"\"...\"\"\"`）ごと | `HTML = tt(\"\"\"<title>タスクボード</title>...\"\"\")` |

`tt()` は辞書のキーを長い順に並べた1本の正規表現で置換する（`re.sub` は左から最長一致で進み、
置換済みの領域を再走査しないので二重置換が起きない）。**vault のデータ（タスク名など）を
差し込む前の静的な文字列にだけ使う**こと。データ混在後の出力に使うとタスク名の一部が
誤置換されうる。

⚠️ `tt()` は JavaScript を含むテンプレート（対話ドック等）にも適用される。JS の文字列は
`'...'` で書かれているため、**訳文にアポストロフィを入れるとその行が構文エラーになる**。
JS に載りうる語の訳では `don't` / `today's` のような表記を避ける（HTML 専用の語は影響なし）。

## 言語の指定（2026-09-13〜：設定メニューから切替）

`dashboard_settings.json` の `"lang": "en"`（GET/POST /settings・ダッシュボードの「設定」画面
の「表示言語」カードから編集）。未指定なら "ja"（＝辞書を一切読まず素通し）。

サーバーは1プロセスが常駐し続けるため、`dashboard_settings.json` の更新を毎回検知して
辞書を読み直す（`_refresh()`）。ただし更新チェックは `stat()` の mtime 比較のみで、
実際に lang の値が変わった時だけ JSON を読み直す＝毎リクエストの負荷はごく小さい。
"""
import html
import json
import re
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

import dashboard_settings

_DICT_DIR = Path(__file__).resolve().parent / "i18n"
_PAGE_CONTEXT = ContextVar("shuki_i18n_page_context", default=None)

# 翻訳を試みたが辞書に無かった文字列（i18n_scan.py / デバッグ用。lang=ja では記録しない）。
MISSING = set()

_state = {"mtime": object(), "lang": None, "dict": {}, "patterns": {}}


def _load_dict(lang):
    """<lang>.json を {原文: 訳} で返す。無い・壊れている場合は空 dict（＝全て素通し）。"""
    try:
        raw = json.loads((_DICT_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    # 値が空文字のエントリは「未翻訳の予約枠」とみなして無視する（原文のまま出す）。
    return {k: v for k, v in raw.items() if isinstance(v, str) and v}


def _refresh():
    """設定ファイルの更新を検知して現在の言語・辞書を最新化する（サーバー再起動不要）。"""
    try:
        mtime = dashboard_settings.SETTINGS_FILE.stat().st_mtime
    except OSError:
        mtime = None
    if mtime == _state["mtime"]:
        return
    _state["mtime"] = mtime
    lang = (dashboard_settings.load_settings().get("lang") or "ja").lower()
    if lang == _state["lang"]:
        return
    _state["lang"] = lang
    d = _load_dict(lang)
    _state["dict"] = d
    _state["protected"] = set(_protected_terms())
    _state["patterns"] = {}


def _protected_terms():
    """訳すと vault のデータと突き合わせられなくなる語（Area 名など）。
    profile.json が正。import 時に循環しないようここで遅延 import する。"""
    try:
        import shuki_profile
        return [a for a in shuki_profile.area_names(include_fallback=True) if _has_jp(a) or a]
    except Exception:  # noqa: BLE001 — 辞書が引けないだけで表示を止めない
        return []


def current_lang():
    _refresh()
    return _state["lang"]


def page_context(ctx):
    """Set the translation namespace for one page render and its nested helpers."""
    def decorate(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            token = _PAGE_CONTEXT.set(ctx)
            try:
                return func(*args, **kwargs)
            finally:
                _PAGE_CONTEXT.reset(token)
        return wrapped
    return decorate


def t(s, ctx=None):
    """UIラベル1つを訳す。辞書に無ければ原文をそのまま返す。

    ctx は同じ日本語を文脈で訳し分けたい時だけ使う（辞書側のキーは "ctx|原文"）。
    ほとんどの場合は不要＝指定しないのが既定。
    """
    _refresh()
    ctx = ctx or _PAGE_CONTEXT.get()
    d = _state["dict"]
    if not d:
        return s
    if ctx:
        hit = d.get(f"{ctx}|{s}")
        if hit:
            return hit
    hit = d.get(s)
    if hit:
        return hit
    if _has_jp(s):
        MISSING.add(s)
    return s


def _pattern_for(ctx):
    """静的テンプレート用の翻訳パターンを返す。ctx付き辞書は該当ページだけに適用する。"""
    cached = _state["patterns"].get(ctx)
    if cached:
        return cached
    all_entries = _state["dict"]
    entries = {k: v for k, v in all_entries.items() if "|" not in k}
    if ctx:
        prefix = f"{ctx}|"
        entries.update({k[len(prefix):]: v for k, v in all_entries.items()
                        if k.startswith(prefix) and v})
    protected = sorted(_state.get("protected") or (), key=len, reverse=True)
    keys = sorted(entries, key=len, reverse=True)
    alts = [re.escape(s) for s in protected] + [re.escape(k) for k in keys]
    result = (re.compile("|".join(alts)), entries) if alts else (False, entries)
    _state["patterns"][ctx] = result
    return result


def set_html_lang(markup):
    """Set the document's language attribute without touching page content or embedded user data."""
    lang = current_lang()
    return re.sub(r'(<html\b[^>]*\blang=)(["\'])[^"\']*\2',
                  lambda m: m.group(1) + m.group(2) + lang + m.group(2),
                  markup, count=1, flags=re.IGNORECASE)


def tt(template, ctx=None):
    """Translate registered phrases in a static template, optionally scoped to one page.

    Apply before inserting vault records or other user data. Scoped entries use ``ctx|Japanese``
    (or, for an English-source page, ``ctx|English``) and are considered only for that page.
    """
    _refresh()
    ctx = ctx or _PAGE_CONTEXT.get()
    if re.match(r"\s*(?:<!doctype[^>]*>\s*)?<html\b", template, flags=re.IGNORECASE):
        template = set_html_lang(template)
    pat, entries = _pattern_for(ctx)
    if not pat:
        return template
    protected = _state.get("protected") or set()
    return pat.sub(lambda m: m.group(0) if m.group(0) in protected else entries[m.group(0)], template)


_NON_HTML_BLOCK_RE = re.compile(r"(<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>)", re.I | re.S)
_HTML_TOKEN_RE = re.compile(r"(<!--.*?-->|<![^>]*>|<[^>]+>|[^<]+)", re.S)
_HTML_UI_ATTR_RE = re.compile(r"(\b(?:title|placeholder|alt|aria-label)\s*=\s*)([\"'])(.*?)\2", re.I | re.S)


def tt_html(template, ctx=None):
    """Translate static markup while leaving embedded scripts and styles to their own rules."""
    chunks = _NON_HTML_BLOCK_RE.split(template)
    out = []
    for chunk in chunks:
        if _NON_HTML_BLOCK_RE.fullmatch(chunk):
            match = re.match(r"(<script\b[^>]*>)(.*?)(</script\s*>)$", chunk, re.I | re.S)
            if match:
                out.append(match.group(1) + tt_js_ui(match.group(2), ctx=ctx) + match.group(3))
            else:
                out.append(chunk)
        else:
            out.append(_tt_html_fragment(chunk, ctx=ctx))
    return "".join(out)


def _tt_html_fragment(fragment, ctx=None):
    """Translate whole visible text nodes and UI attributes, never substrings in prose or data."""
    def translate_token(match):
        token = match.group(0)
        if token.startswith("<"):
            if token.startswith("<!--"):
                return token
            def translate_attr(attr):
                value = t(attr.group(3), ctx=ctx)
                escaped = html.escape(value, quote=True) if attr.group(2) == '"' else value.replace("'", "&#x27;")
                return attr.group(1) + attr.group(2) + escaped + attr.group(2)
            return _HTML_UI_ATTR_RE.sub(translate_attr, token)
        decoded = html.unescape(token)
        leading = re.match(r"\s*", decoded).group(0)
        trailing = re.search(r"\s*$", decoded).group(0)
        core = decoded[len(leading):len(decoded) - len(trailing) if trailing else len(decoded)]
        if not core:
            return token
        translated = t(core, ctx=ctx)
        if translated == core:
            return token
        return leading + html.escape(translated, quote=False) + trailing
    if re.match(r"\s*(?:<!doctype[^>]*>\s*)?<html\b", fragment, flags=re.I):
        fragment = set_html_lang(fragment)
    return _HTML_TOKEN_RE.sub(translate_token, fragment)


_JS_UI_TARGET_RE = re.compile(
    r"(?:\.(?:textContent|innerHTML|outerHTML|title|placeholder|alt|ariaLabel)\s*(?:=|\+=)\s*"
    r"|\b(?:alert|confirm|prompt)\s*\(\s*|\b(?:label|title|placeholder|ariaLabel|alt)\s*:\s*)$"
)
_HTML_IN_JS_RE = re.compile(r"<(?:[a-z][a-z0-9]*|/\s*[a-z][a-z0-9]*|!)\b", re.I)


def tt_js_ui(source, ctx=None):
    """Translate only JavaScript string literals that are visibly used as UI text.

    Data keys and action values in static app scripts remain byte-for-byte intact; user data
    arrives separately and never passes through this helper.
    """
    _refresh()
    ctx = ctx or _PAGE_CONTEXT.get()
    pat, entries = _pattern_for(ctx)
    if not pat:
        return source

    out = []
    last = 0
    i = 0
    n = len(source)
    while i < n:
        if source.startswith("//", i):
            end = source.find("\n", i + 2)
            i = n if end < 0 else end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        quote = source[i]
        if quote not in ("'", '"', "`"):
            i += 1
            continue

        start = i
        i += 1
        content_start = i
        escaped = False
        while i < n:
            ch = source[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == quote:
                break
            i += 1
        if i >= n:
            break
        content_end = i
        raw = source[content_start:content_end]
        prefix = source[max(0, start - 180):start]
        label_scope = source[max(0, start - 1200):start]
        in_label_map = (re.search(r"\b(?:const|let|var)\s+[\w$]*(?:_LABELS?|Labels?)\s*=\s*\{[^{}]*$",
                                  label_scope) is not None
                        and re.search(r"[\w$]+\s*:\s*$", prefix) is not None)
        icon_label = bool(re.search(r"\bshukiIcon\([^)]*\)\s*\+\s*$", prefix)
                          or re.search(r'''\bshukiSetIconLabel\(.*,[ ]*['"][a-z0-9-]+['"],[ ]*$''', prefix))
        ui_target = (bool(_JS_UI_TARGET_RE.search(prefix)) or bool(_HTML_IN_JS_RE.search(raw))
                     or in_label_map or icon_label)
        if ui_target:
            if _HTML_IN_JS_RE.search(raw):
                translated = tt_html(raw, ctx=ctx)
            elif icon_label:
                translated = raw[:len(raw) - len(raw.lstrip())] + t(raw.strip(), ctx=ctx)
                translated += raw[len(raw.rstrip()):]
            else:
                translated = t(raw, ctx=ctx)
            if translated != raw:
                if quote == "'":
                    translated = translated.replace("\\", "\\\\").replace("'", "\\'")
                elif quote == '"':
                    translated = translated.replace("\\", "\\\\").replace('"', '\\"')
                else:
                    translated = translated.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
                out.extend((source[last:content_start], translated))
                last = content_end
        i += 1
    if last == 0:
        return source
    out.append(source[last:])
    return "".join(out)


_JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠]")


def _has_jp(s):
    return bool(_JP_RE.search(s))


def is_ja():
    """日本語環境か。日本語圏固有の機能（ずんだもん読み上げ等）の出し分けに使う。

    「翻訳できないから隠す」ではなく「その言語圏に機能自体が無い」ものの判定。
    """
    return current_lang() == "ja"
