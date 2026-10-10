#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_base.py — Obsidian base codeblock の実行結果ページ（dashboard_server.py の /base ページ）

view_engine が計算した行データを受け取ってHTMLに整形するだけの表示専用モジュール
（vault本体への書き戻しはしない）。データ取得・エンジン実行は dashboard_server.collect_base_view()
が担当する（dashboard_board.py と同じ「ページシェルはデータに触れない」規約）。

開発・検証用ページのため NAV_PAGES（上部ナビ・下部タブバー）には載せない
（🖥 UIデザイン原則 §2「並べない」。/styleguide と同じ扱い）。年月/年ページを日常導線に
載せるかは次フェーズの「答え先出しUI設計」で判断する（2026-07-28 ビューエンジンStep1）。

Areas10ブロック対応（2026-07-28）で1ノート複数view（タスク/ログ/ログ（ギャラリー）等）・
cardsビュー・groupBy見出しに対応。複数viewは `?view=<index>` で切替るタブ表示。
"""
import html
import urllib.parse

import dashboard_ui  # noqa: E402  (nav_html/bottom_nav_html/PWA_HEAD/RESPONSIVE_CSS を再利用)
import dashboard_chat  # noqa: E402  (💬 全ページ共通の対話ドック)
import dashboard_icons
import view_engine  # noqa: E402  (render_table_html/render_cards_html)

# 🖥 UIデザイン原則 §7: 生hexを書かずトークン経由のみ。
# body/.hbtn/.sec-note/.demo-table は styleguide/web/style.css と同じ定義をこのページ用に複製
# （RESPONSIVE_CSS は nav/bottom-nav のみでbody基本スタイルを含まないため、ここで明示的に持つ必要がある）。
_TABLE_CSS = """
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--fg); font-family:var(--font-ui);
  padding:16px 20px 90px; min-height:100vh; }
/* header/.hbtn の基本形は dashboard_ui.RESPONSIVE_CSS が単一の正（2026-08-03 標準化）。
   base は開発・検証用ページのため nav は出さず🏠のみ（意図的、page_header は使わない）。 */
.sec-note { color:var(--muted); font-size:.8rem; margin-bottom:12px; }
table.demo-table { width:100%; border-collapse:collapse; font-size:.82rem; }
.demo-table th, .demo-table td { border:1px solid var(--line); padding:6px 10px; text-align:left; }
.demo-table th { color:var(--accent); }
.demo-table tr.group-row th { background:var(--accent-dim); color:var(--fg); text-align:left;
  font-size:.8rem; padding:5px 10px; }
.view-tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; padding:0 12px; }
.view-tab { border:1px solid var(--line); border-radius:8px; padding:4px 12px; font-size:.82rem;
  text-decoration:none; color:var(--muted); }
.view-tab:hover { color:var(--fg); border-color:var(--accent); }
.view-tab.active { color:var(--fg); border-color:var(--accent); background:var(--accent-dim); }
.gallery-group { margin:14px 0 6px; font-size:.9rem; color:var(--accent); }
.gallery { display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:12px; }
.gcard { background:var(--card); border:1px solid var(--line); border-radius:var(--radius, 12px);
  overflow:hidden; }
.gcard-img { width:100%; aspect-ratio:4/3; object-fit:cover; display:block; background:var(--bg); }
.gcard-noimg { display:flex; align-items:center; justify-content:center; font-size:1.6rem;
  color:var(--muted); }
.gcard-title { font-size:.8rem; padding:6px 8px 2px; }
.gcard-meta { font-size:.72rem; color:var(--muted); padding:0 8px 6px; }
"""


def render_base_html(rel_path, data):
    title = (rel_path.rsplit("/", 1)[-1] if rel_path else "base") or "base"
    if data.get("error"):
        body = f'<p class="sec-note">{dashboard_icons.ui_icon_svg("warn")} {html.escape(data["error"])}</p>'
        tabs = ""
    else:
        if data.get("view_type") == "cards":
            table_html = view_engine.render_cards_html(data["rows"], data["order"])
        else:
            table_html = view_engine.render_table_html(data["rows"], data["order"])
        body = (f'<p class="sec-note">{html.escape(data.get("view_name") or "")}'
                f'（{len(data["rows"])} 件）</p>' + table_html)
        views = data.get("views") or []
        blocks = data.get("blocks") or []
        path_q = urllib.parse.quote(rel_path, safe="")
        block_tabs = ""
        if len(blocks) > 1:
            active_block = data.get("block_index", 0)
            block_links = "".join(
                f'<a class="view-tab{" active" if i == active_block else ""}" '
                f'href="/base?path={path_q}&block={i}">'
                f'{html.escape(b["heading"])}</a>'
                for i, b in enumerate(blocks))
            block_tabs = f'<div class="view-tabs">{block_links}</div>'
        if len(views) > 1:
            active = data.get("view_index", 0)
            block_q = f'&block={data.get("block_index", 0)}' if len(blocks) > 1 else ""
            links = "".join(
                f'<a class="view-tab{" active" if i == active else ""}" '
                f'href="/base?path={path_q}{block_q}&view={i}">'
                f'{html.escape(v["name"])}</a>'
                for i, v in enumerate(views))
            tabs = block_tabs + f'<div class="view-tabs">{links}</div>'
        else:
            tabs = block_tabs
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{dashboard_ui.pwa_head()}{dashboard_chat.assets_head()}
<title>{html.escape(title)}</title>
<style>{dashboard_ui.RESPONSIVE_CSS}{_TABLE_CSS}</style>
</head>
<body>
<header>
  <a href="/" class="hbtn" aria-label="Home">{dashboard_icons.nav_icon_svg("home", 16)}</a>
  <h1>{html.escape(title)}</h1>
</header>
<p class="sec-note" style="padding:0 12px;">{html.escape(rel_path)}</p>
{tabs}
<main style="padding:12px;overflow-x:auto;">
{body}
</main>
{dashboard_ui.bottom_nav_html("base")}{dashboard_chat.dock_html()}
</body></html>"""
