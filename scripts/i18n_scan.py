#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n_scan.py — 翻訳辞書（i18n/<lang>.json）に載っていない日本語UI文字列を洗い出す（2026-08-11新設）。

`shuki_i18n.py` は日本語の原文をそのまま辞書キーにする方式なので、原文を書き換えると
辞書が静かに切れる。その取りこぼしを機械的に見つけるための検査ツール。

    python i18n_scan.py                    # dashboard_*.py の未翻訳を集計
    python i18n_scan.py --lang en dashboard_server.py
    python i18n_scan.py --verify http://127.0.0.1:8765/   # 描画結果に残った日本語を見る

## 何を「UI文字列」とみなすか

ast で**文字列リテラルだけ**を取る（コメントは ast に現れない）。docstring は除外。
f-string の断片は `t()` では包めない（実行時に結合されるため）ので `[f]` 印をつけて区別する。
この印がついたものは `tt()` でテンプレートごと訳すか、f-string の外へ出す必要がある。
"""
import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠]")
# 翻訳対象でない日本語（vault のデータ構造・ファイルパス・frontmatter のキー名など）。
# ここを訳すと vault のファイルが読めなくなるので、辞書ではなくデータ側の設計で扱う。
SKIP_PREFIX = ("06_Resources/", "04_Tasks/", "07_Logs/", "01_Inbox/", "05_Areas/", "99_System/")

# Page-scoped overlay dictionaries use ``context|source`` keys so a UI label cannot
# rewrite a matching status, API value or other page's data literal.
SCAN_CONTEXTS = {
    "dashboard_server.py": ("home", "settings", "skill", "skilldesc", "skillbadge", "skillgroup"),
    "dashboard_ui.py": ("nav", "sidebar", "audio"),
    "dashboard_chat.py": ("chat",),
    "dashboard_board.py": ("board",),
    "dashboard_control.py": ("control",),
    "dashboard_review.py": ("review",),
    "dashboard_styleguide.py": ("styleguide",),
    "dashboard_trading.py": ("trading",),
    "dashboard_files.py": ("files",),
    "dashboard_calendar.py": ("calendar",),
    "dashboard_journal.py": ("journal",),
    "dashboard_visualize.py": ("visualize",),
    "dashboard_decisions.py": ("decisions",),
    "dashboard_gaps.py": ("gaps",),
    "dashboard_settings.py": ("settings",),
    "dashboard_auto_model.py": ("settings",),
    "dashboard_facets.py": ("files", "visualize"),
}


def has_jp(s):
    return bool(JP_RE.search(s))


def collect_literals(path):
    """(文字列, f-string内か) の集合を返す。docstring は除外する。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        print(f"  ! {path.name}: 解析できません（{e}）", file=sys.stderr)
        return set()
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    in_fstring = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in ast.walk(node):
                if isinstance(part, ast.Constant):
                    in_fstring.add(id(part))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            s = node.value
            if not has_jp(s):
                continue
            for frag in fragments(s):
                if not frag.startswith(SKIP_PREFIX):
                    out.add((frag, id(node) in in_fstring))
    return out


# HTML テンプレート内で「表示される日本語」が現れる場所：タグの外のテキストと、いくつかの属性値。
_TEXT_RE = re.compile(r">([^<>]*[ぁ-んァ-ヶ一-龠][^<>]*)<")
_ATTR_RE = re.compile(r"(?:title|placeholder|alt|aria-label|value|label)=\"([^\"]*[ぁ-んァ-ヶ一-龠][^\"]*)\"")
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_JS_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_JS_STR_RE = re.compile(r"'([^'\\\n]*)'|\"([^\"\\\n]*)\"|`([^`\\]*)`")


def fragments(s):
    """文字列リテラルから、辞書キーになりうる日本語の断片を取り出す。

    短いリテラル（ラベル）はそのまま1件。三重引用符の HTML テンプレートは1リテラルとして
    渡ってくるので、タグの外のテキストと表示系の属性値に切り分ける（切らないと
    「テンプレート全体が1つの未翻訳文字列」になって一覧の役に立たない）。
    """
    s = s.strip()
    if not s:
        return []
    if "<" not in s and "\n" not in s and len(s) <= 80:
        return [s]
    # <style> は表示文字列を持たないので丸ごと捨てる。<script> は開発者コメントを落とした上で
    # 文字列リテラルだけ拾う（JS のコメントに書かれた日本語は翻訳対象ではない）。
    script_strings = []
    for m in _SCRIPT_RE.finditer(s):
        code = _JS_COMMENT_RE.sub("", m.group(1))
        for sm in _JS_STR_RE.finditer(code):
            g = next((x for x in sm.groups() if x), "")
            if has_jp(g):
                script_strings.append(g.strip())
    body = _SCRIPT_RE.sub(" ", _STYLE_RE.sub(" ", s))
    body = _HTML_COMMENT_RE.sub(" ", body)
    out = list(script_strings)
    for m in _TEXT_RE.finditer(body):
        out.extend(_split_lines(m.group(1)))
    for m in _ATTR_RE.finditer(body):
        out.extend(_split_lines(m.group(1)))
    if not out and "<" not in s:  # タグを含まない長文（説明文・プロンプト等）は行単位で
        out = _split_lines(s)
    return out


def _split_lines(text):
    return [ln.strip() for ln in text.splitlines()
            if has_jp(ln) and ln.strip() and not _is_code_comment(ln)]


def _is_code_comment(line):
    """開発者向けコメント（翻訳対象外）か。

    f-string の断片は ast で切り刻まれて <script> の構造が失われるため、タグ単位の除去が
    効かない。コメントマーカーで拾い直す。
    """
    st = line.strip()
    return st.startswith("//") or st.startswith("*") or "/*" in st or "*/" in st


def load_dict(lang):
    try:
        return json.loads((HERE / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def scan(files, lang):
    d = load_dict(lang)
    total_missing, total_seen = 0, 0
    per_file = {}
    for f in files:
        missing = defaultdict(bool)  # 文字列 -> f-string内か
        for s, is_f in collect_literals(f):
            if not s:
                continue
            total_seen += 1
            contexts = SCAN_CONTEXTS.get(f.name, ())
            if s not in d and not any(f"{ctx}|{s}" in d for ctx in contexts):
                missing[s] = missing[s] or is_f
        if missing:
            per_file[f] = missing
            total_missing += len(missing)
    for f, missing in sorted(per_file.items(), key=lambda kv: -len(kv[1])):
        print(f"\n── {f.name}  未翻訳 {len(missing)} 件")
        for s in sorted(missing, key=len, reverse=True)[:400]:
            mark = "[f] " if missing[s] else "    "
            print(f"  {mark}{s[:110]}")
    covered = total_seen - total_missing
    print(f"\n合計: UI日本語 {total_seen} 箇所 / 辞書済み {covered} / 未翻訳 {total_missing}"
          f"（辞書 {len(d)} エントリ・lang={lang}）")
    return total_missing


def verify(url):
    """描画結果に残った日本語を見る（Phase 2 の目視検証の補助）。

    vault のデータ（タスク名など）由来の日本語は残っていて当然なので、
    合否を機械判定はしない。UI ラベルが混じっていないかを人が見るための出力。
    """
    import urllib.request
    with urllib.request.urlopen(url, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    frags = defaultdict(int)
    for m in re.finditer(r"[ぁ-んァ-ヶ一-龠][^<>\"'\n]{0,40}", html):
        frags[m.group(0).strip()] += 1
    print(f"{url} に残る日本語断片 {len(frags)} 種（多い順）:")
    for s, n in sorted(frags.items(), key=lambda kv: -kv[1])[:80]:
        print(f"  {n:4d}  {s}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="対象 .py（省略時は dashboard_*.py）")
    ap.add_argument("--lang", default="en", help="照合する辞書の言語（既定: en）")
    ap.add_argument("--verify", metavar="URL", help="描画結果に残る日本語を見る")
    args = ap.parse_args()
    if args.verify:
        verify(args.verify)
        return 0
    files = [Path(f) for f in args.files] if args.files else sorted(HERE.glob("dashboard_*.py"))
    return 0 if scan(files, args.lang) == 0 else 0  # 検出は失敗ではないので常に 0


if __name__ == "__main__":
    sys.exit(main())
