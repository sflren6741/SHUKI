#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
view_engine.py — base_yaml + base_expr を束ねてビューを実行するエンジン（ビューエンジン Step1・2026-07-28）

`BaseSpec`（base_yaml.parse_base の戻り値）と `VaultIndex.notes()` を受け取り、
filters を再帰評価→sort（複数キー）→order で列選択、まで行う。今回の対象は
年月/年テンプレ（table ビューのみ）。cards ビューの実HTML化・formulas評価は次ステップ以降。

検証: python view_engine.py --verify-templates
  06_Resources/Resources/年月/*.md・年/*.md の全ファイルについて、エンジン経由の結果と
  素朴な参照実装（fm.get("month"|"year") への部分一致 + status!=archived）を突き合わせ、
  行のパス集合とソート順が完全一致するか確認する（vault_index.py --verify-tasks/--verify-board と
  同じ「独立再構築 vs 実装」方式）。差分ゼロが合格条件。
"""
import argparse
import html
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base_expr  # noqa: E402
import base_yaml  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_WIKILINK_DISPLAY_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
_WIKILINK_TARGET_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def eval_filter_tree(node, record):
    """filters: の and/or 再帰ツリーを1件の Note レコードに対して評価する。node=None は「全件通過」。"""
    if node is None:
        return True
    if isinstance(node, str):
        return base_expr.eval_predicate(node, record)
    if isinstance(node, dict):
        if "and" in node:
            return all(eval_filter_tree(child, record) for child in node["and"])
        if "or" in node:
            return any(eval_filter_tree(child, record) for child in node["or"])
        raise ValueError(f"unsupported filter mapping (need and:/or:): {node!r}")
    raise ValueError(f"unsupported filter node: {node!r}")


def _sort_value(record, prop):
    return base_expr.resolve_property(prop.split("."), record)


def _sort_key(value):
    """None/list/strを比較可能な文字列に正規化する（ASC時に空値が先頭に来る）。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _display_value(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_display_value(v) for v in value)
    s = str(value)
    m = _WIKILINK_DISPLAY_RE.fullmatch(s)
    return m.group(1) if m else s


def _cover_path(value):
    """`cover:` frontmatterのwikilinkからリンク先（表示名でなくパス側）を取り出す。
    実データは大半が `[[IMG_xxx.jpg]]` のようなフォルダなし裸ファイル名（2026-07-28実測）で、
    実ファイルの解決（vault内探索）は dashboard_server.read_vault_image 側の責務とする。"""
    if not value:
        return None
    s = str(value)
    m = _WIKILINK_TARGET_RE.fullmatch(s)
    return m.group(1) if m else s


def run_view(base_spec, view, notes):
    """1つのviewを実行し、行データ（dictのリスト。各dictは order列 + _path/_name/_cover
    + groupBy指定時は _group）を返す。base直下の filters: と view自身の filters: はAND合成する
    （Areas10ブロックの実測：ほぼ全viewが `file.inFolder(...)` 等の追加絞り込みを持つ・2026-07-28）。
    groupBy はソートの最優先キーとして扱う（groupBy.property→view.sort の順。Obsidianの
    「グループはソート済み行を区切って見出しを挟むだけ」という挙動に合わせる）。
    base_spec.formulas がある場合（タスク管理.mdのみ・2026-07-28）、filters/order/sort が
    `formula.<名前>` を参照できるよう、各note に評価済み結果を event['formula'] としてマージした
    浅いコピーを使う（元の VaultIndex レコードは共有オブジェクトのため直接ミューテートしない＝
    他のbaseブロック・他リクエストへの汚染を避ける）。"""
    if base_spec.formulas:
        notes = [dict(n, formula={name: base_expr.eval_value_expr(expr, n)
                                    for name, expr in base_spec.formulas.items()})
                  for n in notes]
    view_filters = view.get("filters")
    if view_filters is None:
        combined = base_spec.filters
    elif base_spec.filters is None:
        combined = view_filters
    else:
        combined = {"and": [base_spec.filters, view_filters]}
    filtered = [n for n in notes if eval_filter_tree(combined, n)]

    group_by = view.get("groupBy")
    sort_specs = list(view.get("sort") or [])
    if group_by:
        sort_specs = [{"property": group_by["property"],
                        "direction": group_by.get("direction", "ASC")}] + sort_specs
    for spec in reversed(sort_specs):
        prop = spec["property"]
        reverse = str(spec.get("direction", "ASC")).upper() == "DESC"
        filtered.sort(key=lambda n, p=prop: _sort_key(_sort_value(n, p)), reverse=reverse)

    # order 省略時（例: 01_Inbox/インボックス.md の Area 別 view はfilters/order/sort
    # 全て未指定）。実データで初めて出現したパターン（Obsidian実機の既定列挙動は未確認のため、
    # 最小の安全策として file.name のみを表示する＝インボックス/Projectsステップの申し送り）。
    order = view.get("order") or ["file.name"]
    rows = []
    for n in filtered:
        row = {col: _display_value(_sort_value(n, col)) for col in order}
        row["_path"] = n["path"]
        row["_name"] = n.get("name") or n["path"].rsplit("/", 1)[-1]
        row["_cover"] = _cover_path(n.get("cover"))
        if group_by:
            row["_group"] = _display_value(_sort_value(n, group_by["property"]))
        rows.append(row)
    return rows


def render_table_html(rows, order):
    """table view描画。groupBy指定時（rowが `_group` を持つ時）は値が変わるたびに見出し行を挟む
    （行は run_view 側で既にgroupBy優先ソート済み前提。ここでは並べ替えない）。"""
    if not rows:
        return '<p class="sec-note">該当ノートなし</p>'
    grouped = "_group" in rows[0]
    colspan = max(len(order), 1)
    thead = "".join(f"<th>{html.escape(c)}</th>" for c in order)
    body = []
    last_group = object()  # 最初の行は必ず見出しを出すための番兵
    for r in rows:
        if grouped and r["_group"] != last_group:
            last_group = r["_group"]
            label = html.escape(last_group) if last_group else "（未設定）"
            body.append(f'<tr class="group-row"><th colspan="{colspan}">{label}</th></tr>')
        cells = "".join(f"<td>{html.escape(r.get(c, ''))}</td>" for c in order)
        body.append(f"<tr>{cells}</tr>")
    return (f'<table class="demo-table" style="max-width:none;width:100%;">'
            f'<thead><tr>{thead}</tr></thead><tbody>{"".join(body)}</tbody></table>')


def render_cards_html(rows, order):
    """cards view描画（簡易ギャラリー）。画像は record の `cover` frontmatter を既定の紐付け先とする
    （view側で `image:` 指定がある場合の対応は今回未実装＝Areas10ブロックには実例なし）。
    画像本体は `/vault-image?path=<相対パス>` 経由（dashboard_server.py 側の新設ルート）。"""
    if not rows:
        return '<p class="sec-note">該当ノートなし</p>'
    grouped = "_group" in rows[0]
    cards = []
    body_open = False

    def _open_gallery():
        nonlocal body_open
        if not body_open:
            cards.append('<div class="gallery">')
            body_open = True

    def _close_gallery():
        nonlocal body_open
        if body_open:
            cards.append('</div>')
            body_open = False

    last_group = object()
    for r in rows:
        if grouped and r["_group"] != last_group:
            last_group = r["_group"]
            _close_gallery()
            label = html.escape(last_group) if last_group else "（未設定）"
            cards.append(f'<h3 class="gallery-group">{label}</h3>')
        _open_gallery()
        img = (f'<img class="gcard-img" loading="lazy" '
               f'src="/vault-image?path={urllib.parse.quote(r["_cover"], safe="")}" alt="">'
               if r.get("_cover") else '<div class="gcard-img gcard-noimg">🖼</div>')
        meta = "".join(f'<div class="gcard-meta">{html.escape(r.get(c, ""))}</div>'
                       for c in order if r.get(c))
        cards.append(f'<div class="gcard">{img}'
                      f'<div class="gcard-title">{html.escape(r["_name"])}</div>{meta}</div>')
    _close_gallery()
    return "".join(cards)


# ── CLI ──────────────────────────────────────────────
def _cmd_verify_templates():
    from shuki_core import vault as achievements
    import vault_index

    idx = vault_index.VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    notes = idx.notes()

    targets = []
    for sub, prop in (("年月", "month"), ("年", "year")):
        d = idx.vault / "06_Resources" / "Resources" / sub
        for p in sorted(d.glob("*.md")):
            targets.append((p, prop))

    ok = True
    checked = skipped = 0
    for path, prop in targets:
        rel = path.relative_to(idx.vault).as_posix()
        text = achievements.read_text(path)
        blocks = base_yaml.find_base_blocks(text)
        if not blocks:
            skipped += 1
            continue
        checked += 1
        spec = base_yaml.parse_base(blocks[0])
        if not spec.views:
            print(f"── {rel}: views なし（スキップ） ──")
            continue
        view = spec.views[0]
        engine_paths = [r["_path"] for r in run_view(spec, view, notes)]

        stem = path.stem  # "2025-06" or "2025"
        ref = []
        for n in notes:
            val = n["fm"].get(prop)
            if (n["fm"].get("status") or "") == "archived":
                continue
            if isinstance(val, list):
                hit = any(stem in str(v) for v in val)
            elif val is not None:
                hit = stem in str(val)
            else:
                hit = False
            if hit:
                ref.append(n)
        sort_specs = view.get("sort") or []
        if sort_specs:
            ref.sort(key=lambda n: _sort_key(_sort_value(n, sort_specs[0]["property"])),
                      reverse=str(sort_specs[0].get("direction", "ASC")).upper() == "DESC")
        ref_paths = [n["path"] for n in ref]

        if engine_paths != ref_paths:
            ok = False
            print(f"── MISMATCH {rel} ──")
            ea, ra = set(engine_paths), set(ref_paths)
            for p2 in sorted(ea - ra):
                print(f"  + engine only: {p2}")
            for p2 in sorted(ra - ea):
                print(f"  - ref only:    {p2}")
            if ea == ra:
                print(f"  ~ order differs: engine={engine_paths} ref={ref_paths}")
        else:
            print(f"OK {rel}: {len(engine_paths)} 件 一致")

    print(f"\n{'✅' if ok else '❌'} verify-templates: {checked} ファイル検証（{skipped} 件 baseブロック無しでスキップ）")
    if not ok:
        sys.exit(1)


# ── verify-areas: 05_Areas/*.md の全view（Areas10ブロック・2026-07-28） ──
# 参照実装はエンジン（base_expr/eval_filter_tree・view.filtersとの合成・groupBy優先ソート）を
# 一切使わず、frontmatterに対する正規表現ベースの独立評価にする（--verify-templatesと同じ方式）。
_REF_LEAF_PATTERNS = [
    (re.compile(r'^file\.inFolder\("([^"]*)"\)$'),
     lambda m, fm, path: path == m.group(1).rstrip("/") or path.startswith(m.group(1).rstrip("/") + "/")),
    (re.compile(r'^file\.ext == "([^"]*)"$'),
     lambda m, fm, path: path.rsplit("/", 1)[-1].rsplit(".", 1)[-1] == m.group(1)),
    (re.compile(r'^(\w+)\.containsAny\((.*)\)$'),
     lambda m, fm, path: any(_ref_contains(fm.get(m.group(1)), a) for a in _ref_parse_args(m.group(2)))),
    (re.compile(r'^(\w+)\.contains\("([^"]*)"\)$'),
     lambda m, fm, path: _ref_contains(fm.get(m.group(1)), m.group(2))),
    (re.compile(r'^(\w+)\.isEmpty\(\)$'),
     lambda m, fm, path: _ref_is_empty(fm.get(m.group(1)))),
    (re.compile(r'^(\w+) (<=|>=|<|>) today\(\) \+ "(\d+)d"$'),
     lambda m, fm, path: _ref_today_cmp(fm.get(m.group(1)), m.group(2), int(m.group(3)))),
    (re.compile(r'^(\w+) (==|!=|<=|>=|<|>) today\(\)$'),
     lambda m, fm, path: _ref_today_cmp(fm.get(m.group(1)), m.group(2), 0)),
    (re.compile(r'^(\w+) == \["([^"]*)"\]$'),
     lambda m, fm, path: _ref_eq_list(fm.get(m.group(1)), m.group(2))),
    (re.compile(r'^(\w+) != "([^"]*)"$'),
     lambda m, fm, path: str(fm.get(m.group(1)) or "") != m.group(2)),
    (re.compile(r'^(\w+) == "([^"]*)"$'),
     lambda m, fm, path: str(fm.get(m.group(1)) or "") == m.group(2)),
    (re.compile(r'^(\w+) = "([^"]*)"$'),
     lambda m, fm, path: str(fm.get(m.group(1)) or "") == m.group(2)),
]

_REF_ARG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_REF_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")


def _ref_is_empty(value):
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _ref_parse_date(value):
    if not value or not isinstance(value, str):
        return None
    m = _REF_DATE_RE.match(value.strip())
    if not m:
        return None
    try:
        import datetime as _dt
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _ref_today_cmp(field_value, op, plus_days):
    """`due < today()` / `due <= today() + "Nd"` の独立参照実装（base_expr.py非依存）。"""
    import datetime as _dt
    d = _ref_parse_date(field_value)
    if d is None:
        raise ValueError(f"cannot parse date for ordering compare: {field_value!r}")
    t = _dt.date.today() + _dt.timedelta(days=plus_days)
    return {"==": d == t, "!=": d != t, "<": d < t, "<=": d <= t, ">": d > t, ">=": d >= t}[op]


def _ref_parse_args(arg_str):
    """`"📕本", "📖漫画"` のようなカンマ区切り引用文字列列を取り出す（containsAny用の参照実装。
    base_expr.tokenize とは独立に、単純な正規表現抽出のみで済ませる＝式が全て文字列引数のため）。"""
    return _REF_ARG_RE.findall(arg_str)


def _ref_contains(value, needle):
    if value is None:
        return False
    if isinstance(value, list):
        return any(needle in str(v) for v in value)
    return needle in str(value)


def _ref_eq_list(value, needle):
    vl = value if isinstance(value, list) else ([] if value is None else [value])
    return {str(v) for v in vl} == {needle}


def _ref_eval_leaf(leaf, fm, path):
    if leaf.startswith("!"):
        # `"!start.isEmpty()"` 形（YAMLではリーフ文字列全体が引用される）。
        # base_expr.py 側の BANG 前置と同じ意味（1個以上の前置`!`をネストしうる）。
        return not _ref_eval_leaf(leaf[1:], fm, path)
    for pattern, fn in _REF_LEAF_PATTERNS:
        m = pattern.match(leaf)
        if m:
            return fn(m, fm, path)
    raise ValueError(f"unrecognized leaf for reference eval: {leaf!r}")


def _ref_eval_tree(node, fm, path):
    if node is None:
        return True
    if isinstance(node, str):
        return _ref_eval_leaf(node, fm, path)
    if isinstance(node, dict):
        if "and" in node:
            return all(_ref_eval_tree(c, fm, path) for c in node["and"])
        if "or" in node:
            return any(_ref_eval_tree(c, fm, path) for c in node["or"])
    raise ValueError(f"bad filter node for reference eval: {node!r}")


def _ref_resolve(n, prop):
    parts = prop.split(".")
    if parts[0] == "file":
        return n.get(parts[1]) if len(parts) > 1 else n.get("path")
    return n["fm"].get(parts[0])


def _cmd_verify_areas():
    import vault_index

    idx = vault_index.VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    notes = idx.notes()

    areas_dir = idx.vault / "05_Areas"
    ok = True
    checked_views = skipped = 0
    for path in sorted(areas_dir.glob("*.md")):
        rel = path.relative_to(idx.vault).as_posix()
        text = path.read_text(encoding="utf-8")
        blocks = base_yaml.find_base_blocks(text)
        if not blocks:
            skipped += 1
            continue
        spec = base_yaml.parse_base(blocks[0])

        for view in spec.views:
            checked_views += 1
            vname = view.get("name") or view.get("type", "")
            engine_rows = run_view(spec, view, notes)
            engine_paths = [r["_path"] for r in engine_rows]

            view_filters = view.get("filters")
            ref_filtered = [n for n in notes
                             if _ref_eval_tree(spec.filters, n["fm"], n["path"])
                             and _ref_eval_tree(view_filters, n["fm"], n["path"])]
            sort_specs = list(view.get("sort") or [])
            group_by = view.get("groupBy")
            if group_by:
                sort_specs = [{"property": group_by["property"],
                               "direction": group_by.get("direction", "ASC")}] + sort_specs
            for s in reversed(sort_specs):
                prop = s["property"]
                reverse = str(s.get("direction", "ASC")).upper() == "DESC"
                ref_filtered.sort(key=lambda n, p=prop: _sort_key(_ref_resolve(n, p)), reverse=reverse)
            ref_paths = [n["path"] for n in ref_filtered]

            label = f"{rel} :: {vname}"
            if engine_paths != ref_paths:
                ok = False
                print(f"── MISMATCH {label} ──")
                ea, ra = set(engine_paths), set(ref_paths)
                for p2 in sorted(ea - ra):
                    print(f"  + engine only: {p2}")
                for p2 in sorted(ra - ea):
                    print(f"  - ref only:    {p2}")
                if ea == ra:
                    print(f"  ~ order differs: engine={engine_paths} ref={ref_paths}")
            else:
                print(f"OK {label}: {len(engine_paths)} 件 一致")

    print(f"\n{'✅' if ok else '❌'} verify-areas: {checked_views} view検証（{skipped} 件 baseブロック無しでスキップ）")
    if not ok:
        sys.exit(1)


# ── verify-logs-resources: 07_Logs/ログ.md + 06_Resources/Resources.md
#    （ログ/Resourcesステップ・2026-07-28）。Areasと違い1ファイルに複数 base ブロックが
#    並ぶケース（Resources.md=ナレッジDB+OCR保管庫）があるため全ブロックを対象にする。
_LOGS_RESOURCES_TARGETS = ["07_Logs/ログ.md", "06_Resources/Resources.md"]


def _cmd_verify_logs_resources():
    import vault_index

    idx = vault_index.VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    notes = idx.notes()

    ok = True
    checked_views = 0
    for rel in _LOGS_RESOURCES_TARGETS:
        path = idx.vault / rel
        text = path.read_text(encoding="utf-8")
        blocks = base_yaml.find_base_blocks(text)
        for block_idx, block_text in enumerate(blocks):
            spec = base_yaml.parse_base(block_text)
            for view in spec.views:
                checked_views += 1
                vname = view.get("name") or view.get("type", "")
                engine_rows = run_view(spec, view, notes)
                engine_paths = [r["_path"] for r in engine_rows]

                view_filters = view.get("filters")
                ref_filtered = [n for n in notes
                                 if _ref_eval_tree(spec.filters, n["fm"], n["path"])
                                 and _ref_eval_tree(view_filters, n["fm"], n["path"])]
                sort_specs = list(view.get("sort") or [])
                group_by = view.get("groupBy")
                if group_by:
                    sort_specs = [{"property": group_by["property"],
                                   "direction": group_by.get("direction", "ASC")}] + sort_specs
                for s in reversed(sort_specs):
                    prop = s["property"]
                    reverse = str(s.get("direction", "ASC")).upper() == "DESC"
                    ref_filtered.sort(key=lambda n, p=prop: _sort_key(_ref_resolve(n, p)), reverse=reverse)
                ref_paths = [n["path"] for n in ref_filtered]

                label = f"{rel} :: block{block_idx} :: {vname}"
                if engine_paths != ref_paths:
                    ok = False
                    print(f"── MISMATCH {label} ──")
                    ea, ra = set(engine_paths), set(ref_paths)
                    for p2 in sorted(ea - ra):
                        print(f"  + engine only: {p2}")
                    for p2 in sorted(ra - ea):
                        print(f"  - ref only:    {p2}")
                    if ea == ra:
                        print(f"  ~ order differs: engine={engine_paths} ref={ref_paths}")
                else:
                    print(f"OK {label}: {len(engine_paths)} 件 一致")

    print(f"\n{'✅' if ok else '❌'} verify-logs-resources: {checked_views} view検証（{len(_LOGS_RESOURCES_TARGETS)} ファイル・複数base対応）")
    if not ok:
        sys.exit(1)


# ── verify-inbox-projects: 01_Inbox/インボックス.md + 03_Projects/プロジェクト.md
#    （インボックス/Projectsステップ・2026-07-28）。新規述語構文は無し（file.inFolder/file.ext==/
#    status ==,!= は既存パターンで全てカバー）。唯一の新パターンは
#    インボックス.md の Area 別 view（filters/order/sort/groupBy 全て未指定の空view）。
_INBOX_PROJECTS_TARGETS = ["01_Inbox/インボックス.md", "03_Projects/プロジェクト.md"]


def _cmd_verify_inbox_projects():
    import vault_index

    idx = vault_index.VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    notes = idx.notes()

    ok = True
    checked_views = 0
    for rel in _INBOX_PROJECTS_TARGETS:
        path = idx.vault / rel
        text = path.read_text(encoding="utf-8")
        blocks = base_yaml.find_base_blocks(text)
        for block_idx, block_text in enumerate(blocks):
            spec = base_yaml.parse_base(block_text)
            for view in spec.views:
                checked_views += 1
                vname = view.get("name") or view.get("type", "")
                engine_rows = run_view(spec, view, notes)
                engine_paths = [r["_path"] for r in engine_rows]

                view_filters = view.get("filters")
                ref_filtered = [n for n in notes
                                 if _ref_eval_tree(spec.filters, n["fm"], n["path"])
                                 and _ref_eval_tree(view_filters, n["fm"], n["path"])]
                sort_specs = list(view.get("sort") or [])
                group_by = view.get("groupBy")
                if group_by:
                    sort_specs = [{"property": group_by["property"],
                                   "direction": group_by.get("direction", "ASC")}] + sort_specs
                for s in reversed(sort_specs):
                    prop = s["property"]
                    reverse = str(s.get("direction", "ASC")).upper() == "DESC"
                    ref_filtered.sort(key=lambda n, p=prop: _sort_key(_ref_resolve(n, p)), reverse=reverse)
                ref_paths = [n["path"] for n in ref_filtered]

                label = f"{rel} :: block{block_idx} :: {vname}"
                if engine_paths != ref_paths:
                    ok = False
                    print(f"── MISMATCH {label} ──")
                    ea, ra = set(engine_paths), set(ref_paths)
                    for p2 in sorted(ea - ra):
                        print(f"  + engine only: {p2}")
                    for p2 in sorted(ra - ea):
                        print(f"  - ref only:    {p2}")
                    if ea == ra:
                        print(f"  ~ order differs: engine={engine_paths} ref={ref_paths}")
                else:
                    print(f"OK {label}: {len(engine_paths)} 件 一致")

    print(f"\n{'✅' if ok else '❌'} verify-inbox-projects: {checked_views} view検証（{len(_INBOX_PROJECTS_TARGETS)} ファイル）")
    if not ok:
        sys.exit(1)


# ── verify-tasks-hub: 04_Tasks/タスク管理.md（タスク管理.mdステップ・2026-07-28） ──
# vault内で唯一 formulas: を使うファイル。today()・比較演算子(<,<=,>)・素の関数呼び出し(if())・
# 加算演算子(+)の実地検証が主目的。行集合+ソート順に加え、formula.期限バッジ の表示値そのものも
# 独立参照実装（base_expr.py非依存）と突き合わせる（他のverify-*と違い、評価結果自体が新機能）。
_TASKS_HUB_TARGET = "04_Tasks/タスク管理.md"


def _ref_due_badge(fm):
    """`期限バッジ` formula の独立参照実装。"""
    import datetime as _dt
    due = fm.get("due")
    if _ref_is_empty(due):
        return ""
    d = _ref_parse_date(due)
    if d is None:
        raise ValueError(f"cannot parse due for badge: {due!r}")
    t = _dt.date.today()
    if d < t:
        return "🔴 超過"
    if d == t:
        return "🟠 今日"
    if d <= t + _dt.timedelta(days=7):
        return "🟡 今週"
    return "⚪ 先"


def _cmd_verify_tasks_hub():
    import vault_index

    idx = vault_index.VaultIndex()
    print("building index (full sweep)...")
    idx.start(background=False)
    notes = idx.notes()
    by_path = {n["path"]: n for n in notes}

    path = idx.vault / _TASKS_HUB_TARGET
    text = path.read_text(encoding="utf-8")
    blocks = base_yaml.find_base_blocks(text)

    ok = True
    checked_views = 0
    for block_idx, block_text in enumerate(blocks):
        spec = base_yaml.parse_base(block_text)
        for view in spec.views:
            checked_views += 1
            vname = view.get("name") or view.get("type", "")
            engine_rows = run_view(spec, view, notes)
            engine_paths = [r["_path"] for r in engine_rows]

            view_filters = view.get("filters")
            ref_filtered = [n for n in notes
                             if _ref_eval_tree(spec.filters, n["fm"], n["path"])
                             and _ref_eval_tree(view_filters, n["fm"], n["path"])]
            sort_specs = list(view.get("sort") or [])
            group_by = view.get("groupBy")
            if group_by:
                sort_specs = [{"property": group_by["property"],
                               "direction": group_by.get("direction", "ASC")}] + sort_specs
            for s in reversed(sort_specs):
                prop = s["property"]
                reverse = str(s.get("direction", "ASC")).upper() == "DESC"
                ref_filtered.sort(key=lambda n, p=prop: _sort_key(_ref_resolve(n, p)), reverse=reverse)
            ref_paths = [n["path"] for n in ref_filtered]

            label = f"{_TASKS_HUB_TARGET} :: block{block_idx} :: {vname}"
            if engine_paths != ref_paths:
                ok = False
                print(f"── MISMATCH {label} ──")
                ea, ra = set(engine_paths), set(ref_paths)
                for p2 in sorted(ea - ra):
                    print(f"  + engine only: {p2}")
                for p2 in sorted(ra - ea):
                    print(f"  - ref only:    {p2}")
                if ea == ra:
                    print(f"  ~ order differs: engine={engine_paths} ref={ref_paths}")
            else:
                print(f"OK {label}: {len(engine_paths)} 件 一致")

            badge_col = "formula.期限バッジ"
            if badge_col in (view.get("order") or []):
                badge_ok = True
                for row in engine_rows:
                    fm = by_path[row["_path"]]["fm"]
                    ref_badge = _ref_due_badge(fm)
                    if row.get(badge_col, "") != ref_badge:
                        badge_ok = False
                        ok = False
                        print(f"  ~ badge mismatch {row['_path']}: engine={row.get(badge_col)!r} ref={ref_badge!r}")
                if badge_ok:
                    print(f"  OK badge({badge_col}): {len(engine_rows)} 件 一致")

    print(f"\n{'✅' if ok else '❌'} verify-tasks-hub: {checked_views} view検証（{_TASKS_HUB_TARGET}）")
    if not ok:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-templates", action="store_true")
    ap.add_argument("--verify-areas", action="store_true")
    ap.add_argument("--verify-logs-resources", action="store_true")
    ap.add_argument("--verify-inbox-projects", action="store_true")
    ap.add_argument("--verify-tasks-hub", action="store_true")
    args = ap.parse_args()
    if args.verify_templates:
        _cmd_verify_templates()
    elif args.verify_areas:
        _cmd_verify_areas()
    elif args.verify_logs_resources:
        _cmd_verify_logs_resources()
    elif args.verify_inbox_projects:
        _cmd_verify_inbox_projects()
    elif args.verify_tasks_hub:
        _cmd_verify_tasks_hub()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
