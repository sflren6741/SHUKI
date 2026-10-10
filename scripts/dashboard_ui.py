#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_ui.py — 全ページ共通のシェル部品（ナビ・PWA・レスポンシブ土台）

dashboard_server.py（/）・dashboard_journal.py（/journal）・dashboard_trading.py（/trading）・
finance_game/（/finance 静的配信）・dashboard_board.py（/board）の各ページが共有する:
  ① 上部ナビ（デスクトップ・.navlink）
  ② 下部固定タブバー（スマホ ≤700px・.bottom-nav）
  ③ PWA メタ/マニフェスト（<head> に埋め込む PWA_HEAD）

色・フォント等の CSS custom properties は dashboard_theme.py が単一の正（GET /theme.css）。
各ページは <head> に <link rel="stylesheet" href="/theme.css"> を1行足すだけで揃う
（2026-07-28 UI基盤整備。以前は PALETTE をここに個別ハードコードしており、
dashboard_server.PALETTE と値が違う＝下部タブバーだけ色がズレる不具合の原因だった）。
"""
import json
import re

import dashboard_chat
import dashboard_icons
import dashboard_mascot
import dashboard_settings
import dashboard_theme
import shuki_core
import shuki_i18n  # noqa: E402
from shuki_i18n import t, tt

# 後方互換のためのエイリアス（MANIFEST/ICON_SVG の初期値生成にのみ使う静的フォールバック。
# 実際の配色は dashboard_theme.theme_css() が settings から都度組み立てる方が正）。
PALETTE = dashboard_settings.THEMES[dashboard_settings.DEFAULT_THEME][1]

# (key, label, href, children) — 下部タブバー・上部ナビ共通の並び順。
# アイコンは絵文字でなく dashboard_icons.nav_icon_svg(key) の線アイコンSVG（2026-08-03 デザイン刷新）。
# children が None でない項目は「グループ」＝押すとその場にポップオーバーが開き、
# 子ページを選ぶと通常の遷移をする（href は使わないので None）。子は (key, label, href) の3タプル。
NAV_PAGES = [
    ("home", "ホーム", "/", None),
    # トップレベルは利用目的で束ねる。子ページのキーとURLは既存のまま維持する。
    ("do", "やる", None, [
        ("board", "タスク", "/board"),
        ("calendar", "カレンダー", "/calendar"),
        ("decisions", "決裁カード", "/decisions"),
    ]),
    ("reflect", "振り返る", None, [
    ]),
    ("library", "ライブラリ", None, [
        ("files", "ファイル", "/files"),
        ("news", "ニュース", "/news"),
    ]),
    ("life", "生活", None, [
    ]),
]



def add_nav_child(group, key, label, href, after=None, before=None):
    """Insert before/after a named sibling, otherwise append; preserve existing entries."""
    for gkey, _label, _href, children in NAV_PAGES:
        if gkey == group and children is not None:
            if any(k == key for k, _l, _h in children):
                return
            keys = [k for k, _l, _h in children]
            pos = (keys.index(before) if before in keys else
                   keys.index(after) + 1 if after in keys else len(children))
            children.insert(pos, (key, label, href))
            return
    raise ValueError(f"unknown nav group {group!r}")


def order_nav_children(entries):
    """Resolve sibling anchors after every enabled plugin has registered its pages."""
    for group, _label, _href, children in NAV_PAGES:
        if children is None:
            continue
        keys = [key for key, _label, _href in children]
        relevant = [item for item in entries if item["group"] == group and item["key"] in keys]
        anchors = [item[name] for item in relevant for name in ("before", "after") if item.get(name)]
        all_keys = list(dict.fromkeys(keys + anchors))
        edges = {key: set() for key in all_keys}
        for item in relevant:
            key = item["key"]
            if item.get("before") in edges:
                edges[key].add(item["before"])
            if item.get("after") in edges:
                edges[item["after"]].add(key)
        ordered = []
        remaining = list(all_keys)
        while remaining:
            ready = next((key for key in remaining
                          if not any(key in edges[parent] for parent in remaining)), None)
            if ready is None:
                raise ValueError(f"cyclic navigation anchors in {group!r}")
            ordered.append(ready)
            remaining.remove(ready)
        positions = {key: index for index, key in enumerate(ordered)}
        children.sort(key=lambda item: positions[item[0]])


MANIFEST = {
    "name": "SHUKI",
    "short_name": "SHUKI",
    "start_url": "/",
    "id": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": PALETTE["bg"],
    "theme_color": PALETTE["bg"],
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}
MANIFEST_JSON = json.dumps(MANIFEST, ensure_ascii=False)

# ロゴ（2026-08-04 刷新）: 「S」の筆記体がそのまま万年筆のペン先へ流れ込む線画マーク。
# Gemini画像生成→dashboard_assets/icon-*.png に複数サイズ書き出し済み（生成元は
# 06_Resources/Resources/raw/generated/2026-08-04_SHUKIロゴ_確定版v2.png）。
# 以前の ICON_SVG（📊絵文字埋め込み）は完全に置き換え。PNGのため /icon.svg ルートは廃止。

def pwa_head():
    """<head> 共通部品。theme-color は都度 settings を読んで現在のテーマ背景色に合わせる
    （2026-08-24: 以前はモジュールロード時の DEFAULT_THEME 固定値で、テーマ切替後もブラウザの
    アドレスバー/タスクスイッチャー色だけ古いままだった）。
    """
    bg = dashboard_theme.effective_bg(dashboard_settings.load_settings())
    return f'''<meta name="theme-color" content="{bg}">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon-32.png" type="image/png">
<link rel="apple-touch-icon" href="/icon-180.png">
<link rel="stylesheet" href="/theme.css">
<script src="/profile.js"></script>
<script src="/sfx.js" defer></script>
<script src="/push/client.js" defer></script>'''
# ↑ 全ページが pwa_head() を <head> に埋め込むため、/theme.css・/sfx.js の配線もここ1箇所で
# 全ページに伝播する（dashboard_server.py の render_html/render_settings_html・
# dashboard_board/files/progress/trading.py）。/sfx.js は合成音のSE（2026-08-21・
# dashboard_sfx.py が正）。window.SFX として各ページの操作ハンドラから呼ぶ。
# /profile.js は個人の Area 定義（2026-09-27・shuki_profile.py が正）。window.SHUKI_PROFILE
# として静的Webapp の app.js が読む。**defer を付けない**（app.js より先に定義が要るため）。


def _group_has(children, active):
    """グループの子ページのどれかを今開いているか（＝親をカレント表示にするか）。"""
    return any(k == active for k, _label, _href in children)


_NAV_GROUP_ICON_KEYS = {"do": "board", "reflect": "progress", "library": "files", "life": "control"}


def _nav_icon_key(key):
    """新しい目的別グループは、既存ページの線アイコンを代表アイコンとして使う。"""
    return _NAV_GROUP_ICON_KEYS.get(key, key)


def _visible_nav_pages(active):
    """設定で非表示にした項目をナビから間引く（論点2・メニュー表示/非表示カスタマイズ・2026-08-30）。

    home は常時表示（アンカー）。それ以外は dashboard_settings の nav 設定に厳密に従う。
    以前は「今まさに開いているページ自身は隠さない（or is_current）」という現在地優先の例外が
    あったが、ホーム以外の全ページで「そのページ分」が毎回復活し、隠したページを順に開くと
    設定が丸ごと効いていないように見える不具合の原因になっていた（2026-09-01 方針A：隠した
    項目は現在地でも隠す）。現在地はページ見出し（page_header の h1）で分かるため、ナビから
    消えても迷子にはならない。グループ（children持ち）は子を個別トグルせず親単位で開閉する。
    """
    nav = dashboard_settings.load_settings().get("nav", {})
    out = []
    for key, label, href, children in NAV_PAGES:
        if children is not None:
            children = [(k, label_, url) for k, label_, url in children if shuki_core.route_enabled(url)]
            if not children:
                continue
        elif href and not shuki_core.route_enabled(href):
            continue
        if key == "home":
            out.append((key, label, href, children))
            continue
        if nav.get(key, True):
            out.append((key, label, href, children))
    return out


def _navpop_html(children, active, icon_size, sheet=False):
    """グループのポップオーバー中身。子はただのリンク＝押せば通常の遷移をする
    （iframe も履歴の細工もしない。ここが2026-08-21 の再設計の要点）。

    sheet=True は下部タブバー用（モバイル・タブの真上に全幅で開く）。
    """
    items = []
    for key, label, href in children:
        icon = dashboard_icons.nav_icon_svg(key, icon_size)
        lb = t(label, ctx="nav")
        if key == active:
            items.append(f'<span class="navpop-item is-current" tabindex="-1">{icon}<span>{lb}</span></span>')
        else:
            items.append(f'<a class="navpop-item" href="{href}" tabindex="-1">{icon}<span>{lb}</span></a>')
    cls = "navpop navpop-sheet" if sheet else "navpop"
    return f'<div class="{cls}">{"".join(items)}</div>'


def nav_html(active):
    """デスクトップ用の上部ナビ（呼び出し側の <style> に .navlink を定義しておく前提）。

    全項目を常に固定表示し、現在地だけ <span class="navlink is-current"> にしてリンクを外す
    （2026-08-03: 「押しても何も起きないボタン」を無効の見た目にする方が、押せるボタンが
    並ぶより誤操作が起きない、というユーザーのフィードバック。以前は active を配列から除外していたが、
    それだと各ページが個別に持つ🏠戻るボタンと二重になるナビ構成が横行していた）。

    children を持つ項目（管制室）だけはリンクでなくボタンで、押すと直下にポップオーバーが開く。
    グループ内のページを開いている間は親もカレント色にする（現在地がナビから消えないため）。
    """
    items = []
    for key, label, href, children in _visible_nav_pages(active):
        icon = dashboard_icons.nav_icon_svg(_nav_icon_key(key), 15)
        label = t(label, ctx="nav")  # ナビは短い語が多く別文脈と訳が割れるので ctx を付ける
        if children:
            cur = " is-current" if _group_has(children, active) else ""
            chev = dashboard_icons.ui_icon_svg("chevron-down", 12, cls="navgrp-chev")
            items.append(
                f'<span class="navgrp">'
                f'<button type="button" class="navlink navgrp-btn{cur}" aria-haspopup="true"'
                f' aria-expanded="false" onclick="shukiNavPop(this, event)">{icon} {label}{chev}</button>'
                f'{_navpop_html(children, active, 15)}</span>')
        elif key == active:
            items.append(f'<span class="navlink is-current">{icon} {label}</span>')
        else:
            items.append(f'<a class="navlink" href="{href}">{icon} {label}</a>')
    return "".join(items)


def page_header(active, title, extra_html=""):
    """全ページ共通の <header> マークアップ（デスクトップ）。

    タイトル行とナビ行を構造的に分離した2段固定レイアウト（2026-08-03）。
    以前は <header> 1行に h1・nav・追加ボタンを詰めて flex-wrap で折り返していたため、
    ページごとの追加ボタン数やタイトルの長さで折り返しタイミングが変わり、
    「タイトルとメニューの配置がページごとに縦横バラバラ・タイトルの上にメニューが出る」
    不安定さの原因になっていた（ユーザーのフィードバック）。加えて home 画面・設定ページだけが
    この関数を使わず独自の <header> 構造を持っていたことも不統一の一因だった。
    ナビ行は折り返さず横スクロールにする（項目数が増減しても縦位置が動かない）。
    独立した🏠ボタンは持たない＝nav_html が home を常に含むため不要。
    設定への導線は共通サイドバーに集約する。再読み込みはブラウザーの操作を使う。
    extra_html: ページ固有の追加コントロール（タイトル行の右に並べる）。

    末尾にクイックアクセス・サイドバー（sidebar_trigger_html/sidebar_panel_html）も付随させる。
    home・settings は直接 page_header() を呼び、他ページは inject_shell/hydrate_shell 経由で
    呼ぶ＝ここ1箇所に足すだけで全ページに配られる（2026-09-26新設）。
    """
    if active != "home":  # Home title carries the user's configured display name.
        title = shuki_i18n.tt_html(title, ctx=active)
        title = shuki_i18n.tt_html(title, ctx="nav")
    logo = dashboard_mascot.button_html("page") or '<img class="hd-logo" src="/icon-32.png" alt="">'
    return (f'<header class="shuki-header">'
            f'<div class="hd-top"><h1>{logo}<span class="hd-title">{title}</span></h1>'
            f'<div class="hd-extra">{extra_html}{sidebar_trigger_html()}</div></div>'
            f'<nav class="hd-nav">{nav_html(active)}</nav>'
            f'</header>{sidebar_panel_html()}')


# ── クイックアクセス・サイドバー（2026-09-26 新設） ──────────────────────────────
# 通知(/notifications)・ニュース(/news)・決裁カード(/decisions)・実行履歴・設定は
# NAV_PAGES（ページ間移動用の上部ナビ・下部タブバー）に載らない横断的なユーティリティで、
# 従来はホーム画面の外から辿り着けなかった（ユーザーのフィードバック：スマホでいちいちホームに
# 戻るのが不便・読み込みも待たされる）。ページ移動用の nav_html/bottom_nav_html とは
# 役割が違うので独立した開閉の器として持つ（下部フッターと共存する設計）。
# バッジ件数・履歴リストはここに静的に埋め込まず GET /sidebar/data から都度フェッチする
# （このモジュールは dashboard_server.py にimportされる側＝集計ロジックへ逆依存できないため）。
_SIDEBAR_LINKS = [
    ("review", "通知", "/notifications", "notifications"),
    ("newspaper", "ニュース", "/news", "news"),
    ("decisions", "決裁カード", "/decisions", "decisions"),
    ("settings", "設定", "/settings", None),
]


def _sidebar_icon(key, size=18):
    if key in dashboard_icons.NAV_PATHS:
        return dashboard_icons.nav_icon_svg(key, size)
    return dashboard_icons.ui_icon_svg(key, size)


def sidebar_trigger_html():
    """ハンバーガー開閉ボタン。バッジ合計数は JS が /sidebar/data を読んで後から埋める。"""
    return (f'<button type="button" id="sb-trigger" class="sb-trigger" aria-haspopup="true" '
            f'aria-expanded="false" aria-controls="sb-panel" title="{t("メニュー", ctx="sidebar")}" '
            f'onclick="shukiSidebarOpen()">{dashboard_icons.ui_icon_svg("menu", 20)}'
            f'<span class="nav-badge" id="sb-trigger-badge" hidden></span></button>')


def sidebar_panel_html():
    """オーバーレイ＋右スライドパネル本体。中身（バッジ数・実行履歴）は開いた瞬間に1回だけフェッチする。"""
    links = []
    for icon_key, label, href, count_key in _SIDEBAR_LINKS:
        if not shuki_core.route_enabled(href):
            continue
        count_attr = f' data-sb-count="{count_key}"' if count_key else ""
        links.append(
            f'<a class="sb-link" href="{href}"{count_attr}>'
            f'<span class="sb-ico">{_sidebar_icon(icon_key)}</span>{t(label, ctx="sidebar")}'
            f'<span class="nav-badge" hidden></span></a>')
    sidebar_js = _SIDEBAR_JS_TMPL.replace(
        "__NO_HISTORY__", t("実行履歴は、まだありません", ctx="sidebar")).replace("__TURN_LABEL__", t("ターン", ctx="sidebar"))
    sidebar_js = shuki_i18n.tt_js_ui(sidebar_js, ctx="sidebar")
    panel = (f'<div id="sb-overlay" class="sb-overlay" onclick="shukiSidebarClose()"></div>'
            f'<aside id="sb-panel" class="sb-panel" aria-hidden="true">'
            f'<div class="sb-head"><span>{t("メニュー", ctx="sidebar")}</span>'
            f'<button type="button" class="sb-close" onclick="shukiSidebarClose()" '
            f'title="{t("閉じる", ctx="sidebar")}">{dashboard_icons.ui_icon_svg("cross", 16)}</button></div>'
            f'<nav class="sb-links">{"".join(links)}</nav>'
            f'<section class="sb-sessions" aria-label="Sessions">'
            f'<div id="sb-sessions-head" class="sb-hist-head">{dashboard_icons.ui_icon_svg("clock", 14)} Sessions</div>'
            f'<button id="sb-session-review" class="sb-session-control" type="button" onclick="shukiSessionsReview()">Review with AI</button>'
            f'<p class="sb-session-help">Track work separately from reply results. AI suggests what to resume; you set the status.</p>'
            f'<label class="sb-session-label" for="sb-session-filter">Show sessions</label>'
            f'<select id="sb-session-filter" class="sb-session-control" onchange="shukiSessionsFilter()">'
            f'<option value="attention">Needs attention</option><option value="unfinished">Unfinished</option>'
            f'<option value="unreviewed">Unreviewed</option><option value="waiting">Waiting for you</option>'
            f'<option value="done">Completed</option><option value="closed">Closed</option><option value="all">All sessions</option></select>'
            f'<input id="sb-session-search" class="sb-session-control" type="search" aria-label="Search sessions" '
            f'placeholder="Search sessions" maxlength="200" oninput="shukiSessionsSearch()">'
            f'<p id="sb-session-message" class="sb-session-help" role="status" aria-live="polite"></p>'
            f'<ul id="sb-hist" class="hist-list"><li class="muted empty">…</li></ul>'
            f'<button id="sb-session-more" class="sb-session-control" type="button" onclick="shukiSessionsMore()" hidden>Show more</button>'
            f'</section><details class="sb-runs"><summary>Recent execution results</summary>'
            f'<ul id="sb-run-hist" class="hist-list"><li class="muted empty">…</li></ul></details>'
            f'</aside>{sidebar_js}')
    return shuki_i18n.tt_html(panel, ctx="sidebar")


# 履歴の <li> は dashboard_chat.py が全ページへ配る委譲クリックリスナー（[data-resume-session] を
# closest() で拾う）にそのまま乗る＝再開ロジックをここで複製する必要がない（2026-08-11導入の
# 仕組みをそのまま流用）。t() を含む文字列は import 時でなく sidebar_panel_html() 呼び出し時
# （＝リクエスト毎）に差し込む。以前ここを module-level 定数にすると、シェルの他部分と同じく
# 言語設定を変えてもテキストが古いまま凍結する不具合になる（hydrate_shell 導入の教訓と同型）。
_SIDEBAR_JS_TMPL = """<script>
var shukiSidebarLoaded = false;
var shukiSessionRefreshTimer;
function shukiSidebarOpen() {
  document.getElementById('sb-overlay').classList.add('on');
  document.getElementById('sb-panel').classList.add('on');
  document.getElementById('sb-panel').setAttribute('aria-hidden', 'false');
  document.getElementById('sb-trigger').setAttribute('aria-expanded', 'true');
  shukiSidebarLoaded = true;
  shukiSidebarLoad();
  shukiSessionsLoad();
  clearInterval(shukiSessionRefreshTimer);
  shukiSessionRefreshTimer = setInterval(function() {
    if (!document.hidden && !document.activeElement.closest('#sb-hist')) {
      shukiSessionsLoad(true);
      shukiSidebarLoad();
    }
  }, 4000);
}
function shukiSidebarClose() {
  clearInterval(shukiSessionRefreshTimer);
  document.getElementById('sb-overlay').classList.remove('on');
  document.getElementById('sb-panel').classList.remove('on');
  document.getElementById('sb-panel').setAttribute('aria-hidden', 'true');
  document.getElementById('sb-trigger').setAttribute('aria-expanded', 'false');
}
function shukiSidebarLoad() {
  fetch('/sidebar/data').then(function(r) { return r.json(); }).then(function(d) {
    var total = 0;
    document.querySelectorAll('[data-sb-count]').forEach(function(a) {
      var n = (d.counts && d.counts[a.dataset.sbCount]) || 0;
      var b = a.querySelector('.nav-badge');
      if (n) { b.textContent = n; b.hidden = false; total += n; } else { b.hidden = true; }
    });
    var tb = document.getElementById('sb-trigger-badge');
    if (total) { tb.textContent = total > 99 ? '99+' : total; tb.hidden = false; }
    else { tb.hidden = true; }
    var hist = document.getElementById('sb-run-hist');
    hist.innerHTML = '';
    if (!d.history || !d.history.length) {
      var li = document.createElement('li');
      li.className = 'muted empty';
      li.textContent = '__NO_HISTORY__';
      hist.appendChild(li);
      return;
    }
    d.history.forEach(function(h) {
      var li = document.createElement('li');
      li.className = 'hist-item' + (h.session ? '' : ' no-resume');
      li.dataset.resumeSession = h.session || '';
      li.dataset.resumeLabel = h.label || '';
      li.dataset.resumeModel = h.model || '';
      [['hist-when', h.updated || ''],
       ['hist-skill', h.label || ''],
       ['hist-outcome hist-outcome-' + h.outcome, h.outcome_label || ''],
       ['hist-summary', h.summary || ''],
       ['hist-turns', (h.turns == null ? 1 : h.turns) + '__TURN_LABEL__']].forEach(function(p) {
        var span = document.createElement('span');
        span.className = p[0]; span.textContent = p[1];
        li.appendChild(span);
      });
      hist.appendChild(li);
    });
  }).catch(function() {});
}
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') shukiSidebarClose(); });
var shukiSessionData = {items: [], states: {}};
var shukiSessionLimit = 8;
var shukiSessionSequence = 0;
var shukiSessionLoading = false;
var shukiSessionSearchTimer;
try {
  var savedSessionFilter = localStorage.getItem('shuki-session-filter-v1');
  if (['attention','unfinished','unreviewed','waiting','done','closed','all'].includes(savedSessionFilter))
    document.getElementById('sb-session-filter').value = savedSessionFilter;
} catch (_) {}
function shukiSessionQuery() {
  return '?filter=' + encodeURIComponent(document.getElementById('sb-session-filter').value)
    + '&q=' + encodeURIComponent(document.getElementById('sb-session-search').value);
}
function shukiSessionsFilter() {
  try { localStorage.setItem('shuki-session-filter-v1', document.getElementById('sb-session-filter').value); } catch (_) {}
  shukiSessionsLoad();
}
function shukiSessionsSearch() {
  clearTimeout(shukiSessionSearchTimer);
  shukiSessionSearchTimer = setTimeout(shukiSessionsLoad, 200);
}
async function shukiSessionsLoad(refresh) {
  if (refresh === true && shukiSessionLoading) return;
  var sequence = ++shukiSessionSequence;
  shukiSessionLoading = true;
  if (refresh !== true) shukiSessionLimit = 8;
  var message = document.getElementById('sb-session-message');
  if (refresh !== true) message.textContent = 'Loading sessions…';
  try {
    var response = await fetch('/sessions/data' + shukiSessionQuery());
    if (!response.ok) throw new Error('Sessions could not be loaded. Reopen the menu to retry.');
    var data = await response.json();
    if (sequence !== shukiSessionSequence) return;
    if (refresh === true && JSON.stringify(data) === JSON.stringify(shukiSessionData)) return;
    shukiSessionData = data;
    shukiSessionsRender();
  } catch (error) { if (sequence === shukiSessionSequence) message.textContent = error.message; }
  finally { if (sequence === shukiSessionSequence) shukiSessionLoading = false; }
}
function shukiSessionsRender() {
  var hist = document.getElementById('sb-hist');
  hist.replaceChildren();
  var items = shukiSessionData.items || [];
  items.slice(0, shukiSessionLimit).forEach(function(item) {
    var row = document.createElement('li'); row.className = 'hist-item sb-session-item';
    var title = document.createElement(item.session ? 'button' : 'span');
    title.className = 'sb-session-title'; title.textContent = item.label;
    if (item.session) {
      title.type = 'button'; title.dataset.resumeSession = item.session;
      title.dataset.resumeLabel = item.label; title.dataset.resumeModel = item.model;
      title.title = 'Resume ' + item.label;
    }
    row.appendChild(title);
    [['hist-when', item.updated], ['hist-turns', item.turns + ' turns'],
     ['hist-outcome hist-outcome-' + item.outcome, ({running:'Running',ok:'Reply finished',review:'Decision requested',incomplete:'Reply interrupted'})[item.outcome] || 'Reply status unknown'],
     ['hist-request', item.last_request ? 'Last request: ' + item.last_request : ''],
     ['hist-summary', item.summary || 'No saved summary. Open the session for its context.']].forEach(function(part) {
      if (!part[1]) return;
      var span = document.createElement('span'); span.className = part[0]; span.textContent = part[1]; row.appendChild(span);
    });
    var select = document.createElement('select'); select.className = 'sb-session-control';
    select.setAttribute('aria-label', 'Work status for ' + item.label);
    Object.entries(shukiSessionData.states).forEach(function(pair) {
      var option = document.createElement('option'); option.value = pair[0]; option.textContent = pair[1]; select.appendChild(option);
    });
    select.value = item.work_status;
    select.disabled = !!item.running;
    if (item.running) select.title = 'Wait for the current reply before changing work status.';
    select.addEventListener('change', function() { shukiSessionsSave(item, select); });
    row.appendChild(select); hist.appendChild(row);
  });
  if (!items.length) {
    var empty = document.createElement('li'); empty.className = 'muted empty';
    empty.textContent = 'No sessions match this filter.'; hist.appendChild(empty);
  }
  document.getElementById('sb-session-more').hidden = items.length <= shukiSessionLimit;
  document.getElementById('sb-session-message').textContent = 'Showing ' + Math.min(items.length, shukiSessionLimit) + ' of ' + items.length
    + '. Unreviewed sessions may already be finished.';
}
function shukiSessionsMore() { shukiSessionLimit += 8; shukiSessionsRender(); }
async function shukiSessionsSave(item, select) {
  var previous = item.work_status;
  select.disabled = true;
  try {
    var response = await fetch('/sessions/status', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({key:item.key, work_status:select.value})});
    var data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Session status was not saved.');
    await shukiSessionsLoad();
    document.getElementById('sb-session-message').textContent = 'Status saved. ' + document.getElementById('sb-session-message').textContent;
  } catch (error) {
    select.value = previous;
    document.getElementById('sb-session-message').textContent = error.message + ' Your previous status is unchanged.';
  } finally { select.disabled = false; }
}
async function shukiSessionsReview() {
  var button = document.getElementById('sb-session-review'); button.disabled = true;
  try {
    var response = await fetch('/sessions/review' + shukiSessionQuery());
    if (!response.ok) throw new Error('Session review could not be prepared. Try again.');
    var data = await response.json();
    if (!data.count) throw new Error('No resumable sessions match this filter.');
    shukiSidebarClose();
    pickModelThen('Session review (' + data.count + ' of ' + data.total + ')', function() {
      if (shukiPrepareSessionTab()) doExec('', encodeURIComponent(data.prompt), 'Session review');
    });
  } catch (error) { document.getElementById('sb-session-message').textContent = error.message; }
  finally { button.disabled = false; }
}
</script>"""


def _bgm_widget_html():
    """概念図鑑（/game）専用BGMの再生ボタン＋<audio>。既定は停止（自動再生制限のため
    ページ読み込み時は鳴らせない）。押すたびにトグルし、状態はページ内だけで保持する
    （設定への書き戻しは不要・ページを閉じれば止まる想定でよい・2026-08-21）。"""
    return """<audio id="shuki-bgm" src="/bgm/dreambyte_loop.mp3" loop preload="none"></audio>
<button type="button" id="shuki-bgm-btn" class="shuki-bgm-btn" title="__BGM_TITLE__" aria-pressed="false"
  style="position:fixed;right:14px;bottom:76px;z-index:40;width:44px;height:44px;border-radius:50%;
  border:1px solid var(--line);background:var(--card);color:var(--fg);font-size:18px;cursor:pointer;
  box-shadow:0 2px 8px rgba(0,0,0,.25);">🎵</button>
<style>
  .shuki-bgm-btn.on { background:var(--accent); color:#fff; }
  @media (min-width: 701px) { .shuki-bgm-btn { bottom:14px; } }
</style>
<script>
(function(){
  var a = document.getElementById('shuki-bgm');
  var b = document.getElementById('shuki-bgm-btn');
  if (!a || !b) return;
  var playing = false;
  function setState(on) {
    playing = on;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.textContent = on ? '\U0001F50A' : '\U0001F3B5';
  }
  b.addEventListener('click', function() {
    if (playing) { a.pause(); setState(false); return; }
    a.volume = 0.35;
    a.play().then(function() { setState(true); }).catch(function() {});
  });
})();
</script>""".replace("__BGM_TITLE__", t("BGMを再生/停止", ctx="audio"))


def inject_shell(html_text, active, title):
    """静的HTML（/habit・/game・/achievements・/finance の index.html）に
    共通ヘッダー・PWAメタ・テーマCSSを埋め込む。

    対象ページは進捗・草・タスク等と違い、Pythonが動的組み立てせず素の index.html を
    そのまま配信していたため、共通ナビ（PC上部リンク・スマホ下部固定タブ）が一切なく
    ページ間で表示が消えたり出たりする不整合があった（2026-08-03 発見・修正）。
    さらに各ページが独自の装飾ヘッダー（.ach-head 等・中央寄せ・明朝1.7rem）に <h1> を
    持っていたため、動的ページ（左寄せ 1.15rem・ヘッダー高79px）と高さもタイトル位置も
    揃わなかった（実測: 称号ページのヘッダー182px vs 進捗79px。2026-08-06 修正）。

    現在は <!--SHUKI_PAGE_HEADER--> に page_header() をそのまま埋める＝動的ページと
    同一の関数が骨格を作る。各ページの装飾ヘッダーは <h1> を持たない「世界観バンド」
    （サブ説明文・スコアカード・ヘルプボタン）に降格し、本文冒頭の一要素として残す。
    仕様の正は `🖥 UIデザイン原則（画面編）.md` §2.5.1。
    """
    html_text = shuki_i18n.tt_html(html_text, ctx=active)
    head = pwa_head() + f"<style>{RESPONSIVE_CSS}</style>" + dashboard_chat.assets_head()
    html_text = html_text.replace("<!--SHUKI_NAV_HEAD-->", head)
    html_text = html_text.replace("<!--SHUKI_PAGE_HEADER-->", page_header(active, title))
    # 対話ドックも下部ナビと同じ場所で配る（2026-08-11）。ページごとに完全なHTMLを返す
    # 構造上、ドックは各ページが自分で持たないと遷移のたびに消えてしまう。
    html_text = html_text.replace("<!--SHUKI_BOTTOM_NAV-->",
                                  bottom_nav_html(active) + dashboard_chat.dock_html())
    # 🎵 概念図鑑（/game）専用BGM（2026-08-21）。マーカーが無いページ（habit/achievements/finance）
    # では置換対象が無く no-op。ブラウザの自動再生制限で、実際の再生は必ずボタン押下（ジェスチャ）
    # 後になる＝設定OFF時はボタン自体を出さない設計にして「押しても鳴らない」を作らない。
    if "<!--SHUKI_BGM-->" in html_text:
        bgm_on = dashboard_settings.load_settings().get("bgm_enabled", True)
        html_text = html_text.replace("<!--SHUKI_BGM-->", _bgm_widget_html() if bgm_on else "")
    # <!--SHUKI_ICO:filter--> / <!--SHUKI_ICO:sort:16--> を線アイコンSVGに差し替える
    # （2026-08-08 追加）。静的ページは Python を呼べないため、放っておくと各 index.html が
    # SVGパスを自前で持ち＝同じ意味のアイコンが複数箇所に散る（UIデザイン原則 §9 が禁じている）。
    html_text = re.sub(
        r"<!--SHUKI_ICO:([a-z0-9-]+)(?::(\d+))?-->",
        lambda m: dashboard_icons.ui_icon_svg(m.group(1), int(m.group(2) or 14)),
        html_text)
    return html_text


def hydrate_shell(page_html, active, title, extra_html="", inflow=False):
    """モジュール読み込み時に固定された PAGE 文字列から、リクエストごとに変わるシェル
    （上部ナビ・下部タブバー・対話ドック）を差し替えて返す。

    /files・/board・/progress 等は HTML を `PAGE = ... + page_header(...) + ...` の形で
    **import 時に一度だけ**組み立て、`render_*_html()` はそれを返すだけだった。そのため
    サーバー起動後にナビ表示設定（設定ページのメニュー表示/非表示）やドックのモデル選択を
    変えても、これらのページだけ古いシェルのまま凍結する（home・settings はリクエスト毎に
    組むので反映される）不整合があった（2026-09-01 修正）。
    プレースホルダは inject_shell と共通（<!--SHUKI_PAGE_HEADER--> / <!--SHUKI_BOTTOM_NAV-->）。
    """
    page_html = shuki_i18n.tt_html(page_html, ctx=active)
    page_html = page_html.replace("<!--SHUKI_PAGE_HEADER-->",
                                  page_header(active, title, extra_html))
    page_html = page_html.replace("<!--SHUKI_BOTTOM_NAV-->",
                                  bottom_nav_html(active, inflow=inflow) + dashboard_chat.dock_html())
    return page_html


# ナビのグループ（管制室）を開閉する最小スクリプト。bottom_nav_html() が出力する＝全ページに
# 1回だけ配られる（上部ナビ・下部タブバーの両方が同じ .navpop / 同じ関数を使う）。
NAVPOP_JS = """<script>
var shukiNavPopLastBtn = null;
function shukiNavPopClose(restoreFocus) {
  document.querySelectorAll(".navpop.on").forEach(p => p.classList.remove("on"));
  document.querySelectorAll('[aria-haspopup="true"]').forEach(b => b.setAttribute("aria-expanded", "false"));
  if (restoreFocus && shukiNavPopLastBtn) shukiNavPopLastBtn.focus();
  shukiNavPopLastBtn = null;
}
function shukiNavPop(btn, ev) {
  ev.stopPropagation();  // 直後の document クリックで自分が閉じられるのを防ぐ
  const pop = btn._navpop || (btn._navpop = btn.nextElementSibling);
  const wasOpen = pop.classList.contains("on");
  shukiNavPopClose();
  if (wasOpen) return;
  shukiNavPopLastBtn = btn;
  // body 直下へ移して position:fixed で開く。ヘッダーのナビ行は overflow-x:auto（項目が増えても
  // 折り返さず横スクロールする設計）なので、その中に absolute で置くとクリップされて
  // まったく見えない（2026-08-21 実測）。
  if (pop.parentElement !== document.body) document.body.appendChild(pop);
  pop.classList.add("on");
  btn.setAttribute("aria-expanded", "true");
  const r = btn.getBoundingClientRect();
  if (pop.classList.contains("navpop-sheet")) {
    // 下部タブバー: タブの真上に全幅シート
    pop.style.cssText += ";left:8px;right:8px;top:auto;bottom:" + (innerHeight - r.top + 8) + "px";
  } else {
    // 上部ナビ: ボタンの直下。右端をはみ出す時だけ画面内へ寄せる
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.style.top = (r.bottom + 6) + "px";
    pop.style.left = Math.max(8, Math.min(r.left, innerWidth - pop.offsetWidth - 8)) + "px";
  }
  const firstItem = pop.querySelector(".navpop-item");
  if (firstItem) firstItem.focus();
}
document.addEventListener("click", shukiNavPopClose);
document.addEventListener("keydown", e => { if (e.key === "Escape") shukiNavPopClose(true); });
// 座標を固定で持つため、ページが動いたら閉じる（ずれた位置に浮いたまま残さない）
addEventListener("scroll", shukiNavPopClose, true);
addEventListener("resize", shukiNavPopClose);
</script>"""


def bottom_nav_html(active, inflow=False):
    """スマホ用の画面下タブバー。

    inflow=True（board.py 用）: position:static でフレックス内の通常フローに置く
    （board は body 自体が height:100vh; overflow:hidden の固定レイアウトのため、
    fixed オーバーレイにすると表示領域が重なってしまう）。
    inflow=False（他3ページ）: position:fixed でスクロールする通常ページの下に張り付ける。
    """
    parts = []
    for key, label, href, children in _visible_nav_pages(active):
        icon = f'<span class="bn-icon">{dashboard_icons.nav_icon_svg(_nav_icon_key(key), 20)}</span>'
        label_html = f'<span class="bn-label">{t(label, ctx="nav")}</span>'
        if children:
            # ポップオーバーはタブの真上に出す（全幅シート）。タブ幅が狭く、指で押した位置に
            # 小さなメニューを出すと親指自身で隠れるため（2026-08-21）。
            cur = " active" if _group_has(children, active) else ""
            parts.append(
                f'<button type="button" class="bn-item bn-grp{cur}" aria-haspopup="true"'
                f' aria-expanded="false" onclick="shukiNavPop(this, event)">{icon}{label_html}</button>'
                f'{_navpop_html(children, active, 18, sheet=True)}')
        elif key == active:
            parts.append(f'<span class="bn-item active">{icon}{label_html}</span>')
        else:
            parts.append(f'<a class="bn-item" href="{href}">{icon}{label_html}</a>')
    cls = "bottom-nav inflow" if inflow else "bottom-nav"
    return f'<nav class="{cls}">{"".join(parts)}</nav>{NAVPOP_JS}'


# var(--xxx) 参照のみ（/theme.css を <link> した先頭の :root{} が値を供給する）。
# 以前は {PALETTE['card']} 等の直接埋め込みが混在し、下部タブバーだけ配色がズレていた
# （dashboard_ui.PALETTE がホームと別パレットだったため。2026-07-28 解消）。
#
# header/.hbtn は元々各ページが個別に <style> で定義しており、padding・gap・font-sizeが
# ページごとに微妙に違っていた（ユーザーのフィードバック「メニューやタイトルの配置が標準化されていない」
# 2026-08-03）。以後はここが単一の正。page_header() を使うページはページ固有 <style> に
# header/.hbtn を重複定義しないこと。
RESPONSIVE_CSS = """
  /* タイトル行(.hd-top)とナビ行(.hd-nav)を構造的に分離した2段固定。ナビは折り返さず横スクロール
     にすることで、追加ボタンの数やタイトルの長さに関わらず縦位置が動かない（2026-08-03 標準化）。
     スクロール追従（2026-08-06）: 下までスクロールしてもナビが届く＝「戻るために一番上まで
     戻る」操作を消す。body に padding を持つページは --page-pad-x/y を宣言し、ヘッダーが
     その分を負マージンで食って画面端まで背景を伸ばす（左右に本文が透けて流れる隙間を作らない）。
     背景を半透明+blur にしているのは、図鑑・称号の背景グラデーションを不透明色で
     塗り潰さないため。 */
  header { position:sticky; top:0; z-index:900;
    background:var(--card);
    border-bottom:1px solid var(--line);
    margin:calc(var(--page-pad-y, 0px) * -1) calc(var(--page-pad-x, 0px) * -1) 14px;
    padding:10px max(var(--page-pad-x, 0px), 16px) 8px; }
  /* min-height は、追加操作を .hd-extra に持つページ(30px)と持たないページ(h1 の 24.5px)で
     ヘッダー総高が変わらないようにするため（2026-08-06 実測して統一）。 */
  .hd-top { display:flex; align-items:center; gap:12px; margin-bottom:8px; min-height:44px; }
  /* margin:0 は必須。静的4ページは動的ページと違い `* { margin:0 }` リセットを持たないため、
     指定しないとUA既定の h1 マージン(0.67em≒24.7px)だけヘッダーが高くなる（2026-08-06 実測）。 */
  .hd-top h1 { font-size:1.15rem; margin:0; white-space:nowrap; display:flex; align-items:center; gap:8px; }
  .hd-top h1 { min-width:0; }
  .hd-title { min-width:0; overflow:hidden; text-overflow:ellipsis; }
  .hd-title > svg { vertical-align:middle; }
  .hd-logo { width:24px; height:24px; border-radius:7px; flex-shrink:0; }
  .hd-extra { margin-left:auto; display:flex; gap:6px; align-items:center; flex-shrink:0; }
  .hd-nav { display:flex; gap:6px; overflow-x:auto; scrollbar-width:thin; padding-bottom:2px; }
  .hd-nav::-webkit-scrollbar { height:4px; }
  .hd-nav::-webkit-scrollbar-thumb { background:var(--line); border-radius:4px; }
  .hbtn { background:none; border:1px solid var(--line); color:var(--muted);
    border-radius:8px; padding:4px 12px; cursor:pointer; font-size:.85rem; text-decoration:none;
    display:inline-flex; align-items:center; gap:4px; }
  .hbtn:hover { color:var(--fg); border-color:var(--accent); }
  .navlink { color:var(--muted); text-decoration:none; font-size:.875rem; padding:8px 14px;
    min-height:44px; border:1px solid transparent; border-radius:8px; white-space:nowrap; flex-shrink:0;
    display:inline-flex; align-items:center; gap:5px; }
  .navlink svg { flex-shrink:0; }
  .navlink:hover { color:var(--fg); background:var(--surface-control); }
  .navlink.is-current { color:var(--accent); border-color:var(--accent); cursor:default;
    background:color-mix(in srgb, var(--accent) 12%, transparent); }
  /* ── ナビのグループ（管制室 → 生活/家計/トレード）。2026-08-21 ──
     3ページを1ページのタブに集約していた構成をやめ、「まとまり」はナビのメニューだけで表現する。
     各ページは単独表示に戻る＝iframe の高さ同期も幅の二重 max-width も要らない。 */
  .navgrp { position:relative; display:inline-flex; flex-shrink:0; }
  .navgrp-btn { background:none; font-family:inherit; cursor:pointer; }
  .navgrp-btn.is-current { cursor:pointer; }  /* .navlink.is-current の cursor:default を戻す（押せるボタンなので） */
  .navgrp-chev { margin-left:1px; opacity:.65; transition:transform .15s ease; }
  .navgrp-btn[aria-expanded="true"] .navgrp-chev { transform:rotate(180deg); }
  /* position:fixed ＋ body直下への移設（shukiNavPop が行う）。absolute のままヘッダー内に
     置くと .hd-nav の overflow-x:auto にクリップされて一切見えない（2026-08-21 実測）。
     座標はボタンの実位置からJSが入れる＝ヘッダー高さやタブ幅を決め打ちしない。 */
  .navpop { display:none; position:fixed; z-index:1200;
    background:var(--card); border:1px solid var(--line); border-radius:10px; padding:5px;
    min-width:170px; box-shadow:0 10px 28px rgba(0,0,0,.38); }
  .navpop.on { display:block; }
  /* 上部ナビ用と下部タブバー用の2つが同時にDOMにあるので、その幅でだけ使う方を出す
     （body直下へ移すと .hd-nav/.bottom-nav の display:none を継承しなくなるため明示する）。 */
  @media (max-width: 700px) { .navpop:not(.navpop-sheet) { display:none !important; } }
  @media (min-width: 701px) { .navpop.navpop-sheet { display:none !important; } }
  .navpop-sheet .navpop-item { padding:12px 13px; font-size:.92rem; }  /* タッチ到達域（§6） */
  .navpop-item { display:flex; align-items:center; gap:9px; padding:8px 11px; min-height:44px; border-radius:7px;
    color:var(--muted); text-decoration:none; font-size:.85rem; white-space:nowrap; }
  .navpop-item svg { flex-shrink:0; }
  .navpop-item:hover { color:var(--fg); background:color-mix(in srgb, var(--fg) 8%, transparent); }
  .navpop-item.is-current { color:var(--accent); cursor:default;
    background:color-mix(in srgb, var(--accent) 12%, transparent); }
  .bottom-nav { display:none; }
  /* ── ツールバーの役割記号（2026-08-08 追加・UIデザイン原則 §2.4） ──
     絞り込み／並べ替え／束ね方が同じ見た目のセレクトで横並びになると、押すまで
     どれが何なのか分からない。各ブロックの先頭に役割アイコンを置いて見分ける。
     .tb-grp は「アイコン＋その操作」を1かたまりとして折り返すためのもの（バラで並べると
     狭い画面でアイコンだけが前の行の端に取り残される。400px幅の実機で確認）。
     /board で作った様式をここへ引き上げ、図鑑・習慣・進捗・称号も同じ記号を使う。 */
  .tb-grp { display:flex; align-items:center; gap:7px; flex-wrap:wrap; }
  .tb-ico { display:inline-flex; color:var(--muted); flex-shrink:0; }
  .tb-sep { width:1px; height:17px; background:var(--line); flex-shrink:0; margin:0 2px; }
  /* ── 表示方式の切替（セグメント・2026-09-15 に /board から引き上げ） ──
     「同じ対象を別の見せ方で出す」切替は全ページ共通の器にする（UIデザイン原則 §8.4
     「グリッドは1枚・指標は切替で入れ替える」）。/board の表示方式トグルと
     /visualize のセクション切替が同じ形になるよう、CSSはここが単一の正。 */
  .mode-toggle { display:flex; gap:4px; }
  .mode-btn { display:inline-flex; align-items:center; gap:5px; background:none;
    border:1px solid var(--line); color:var(--muted); border-radius:2px; padding:4px 10px;
    font-size:.78rem; font-family:inherit; cursor:pointer; }
  .mode-btn:hover { color:var(--fg); border-color:var(--accent); }
  .mode-btn.active { color:var(--accent); border-color:var(--accent);
    background:color-mix(in srgb, var(--accent) 10%, transparent); }
  @media (max-width: 700px) {
    body { font-size:1rem; }
    body:not(.no-bn-pad) { padding-bottom:70px !important; }
    .hd-nav { display:none; }  /* 下部タブバーと重複するため非表示（ページ固有操作は .hd-extra に残る） */
    .hbtn { min-height:44px; min-width:44px; justify-content:center; }
    .bottom-nav { display:flex; z-index:1000; background:var(--card);
      border-top:1px solid var(--line); padding:6px 4px calc(6px + env(safe-area-inset-bottom));
      gap:2px; flex-shrink:0; }
    .bottom-nav:not(.inflow) { position:fixed; left:0; right:0; bottom:0; }
    .bottom-nav.inflow { position:relative; }  /* グループのポップオーバーの位置基準（board は fixed でないため） */
    .bn-item { flex:1; display:flex; flex-direction:column; align-items:center; gap:2px;
      color:var(--muted); text-decoration:none; padding:4px 2px; border-radius:8px;
      min-height:44px; justify-content:center; }
    .bn-item.active { color:var(--accent); cursor:default; }
    /* グループはタブの真上に全幅シートで開く（位置は shukiNavPop が算出）。タブ幅が狭いうえ、
       押した指の位置に小さなメニューを出すと親指自身で選択肢が隠れるため（2026-08-21）。 */
    .bn-grp { background:none; border:none; font:inherit; cursor:pointer; }
    .bn-icon svg { display:block; }
    .bn-label { font-size:.7rem; }
  }
  .muted { color:var(--muted); }
  .empty { font-size:.8rem; padding:4px; }
  /* バッジの赤ピル。以前は dashboard_server.py の HOME_CSS だけが持ち、ホーム画面の外では
     使えなかった（2026-09-26 サイドバー新設にあわせてここへ昇格・単一の正にする）。 */
  .nav-badge { display:inline-block; margin-left:5px; background:var(--red); color:#fff; font-weight:900;
    font-size:.68rem; border-radius:999px; padding:0 6px; min-width:15px; text-align:center;
    vertical-align:2px; }
  /* 実行履歴リスト。ホーム画面の折りたたみ欄と、後述サイドバーの両方が同じマークアップ
     （.hist-list > li.hist-item）を使う共通部品として昇格した（2026-09-26。以前は HOME_CSS 内に
     ホーム専用として定義されており、他ページでは同じマークアップを出しても無装飾だった）。 */
  .hist-list { list-style:none; margin:8px 0 0; padding:0; display:flex; flex-direction:column; gap:6px; }
  .hist-item { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 10px;
    font-size:.82rem; cursor:pointer; display:flex; gap:8px; flex-wrap:wrap; align-items:baseline; }
  .hist-item:hover { border-color:var(--accent); }
  .hist-item.no-resume { cursor:default; }
  .hist-item.no-resume:hover { border-color:var(--line); }
  .hist-when { color:var(--muted); font-variant-numeric:tabular-nums; flex:0 0 auto; }
  .hist-skill { color:var(--accent); font-weight:bold; flex:1 1 100%; min-width:0; overflow-wrap:break-word; }
  .hist-summary { color:var(--fg); opacity:.85; flex:1 1 100%; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .hist-turns { color:var(--muted); font-size:.72rem; flex:0 0 auto; }
  .hist-outcome { font-size:.72rem; font-weight:bold; flex:0 0 auto; white-space:nowrap; }
  .hist-outcome-ok { color:var(--ok); }
  .hist-outcome-review { color:var(--warn); }
  .hist-outcome-incomplete { color:var(--danger); }
  .hist-outcome-running { color:var(--info); }
  /* ── クイックアクセス・サイドバー（2026-09-26）: 通知/ニュース/決裁/履歴/設定への横断的な
     入口。hd-nav・bottom-nav（ページ間移動）とは別軸なので、その2つとは独立に開閉する。
     navpop と同じ z-index 帯より上に置き、下部タブバーの上からでも確実に開く。 */
  .sb-trigger { background:none; border:1px solid var(--line); color:var(--muted); border-radius:8px;
    width:36px; height:36px; min-width:36px; display:inline-flex; align-items:center; justify-content:center;
    position:relative; cursor:pointer; flex-shrink:0; }
  .sb-trigger:hover { color:var(--fg); border-color:var(--accent); }
  .sb-trigger .nav-badge { position:absolute; top:-4px; right:-4px; margin-left:0; }
  .sb-overlay { display:none; position:fixed; inset:0; z-index:1300; background:rgba(0,0,0,.4); }
  .sb-overlay.on { display:block; }
  /* トリガー（ハンバーガー）がヘッダー右端（hd-extra）にあるので、パネルも右からスライドさせる
     （開く場所とトリガーの位置を揃える・2026-09-26）。 */
  .sb-panel { position:fixed; top:0; right:0; bottom:0; z-index:1301; width:min(300px, 84vw);
    background:var(--card); border-left:1px solid var(--line); box-shadow:-6px 0 24px rgba(0,0,0,.3);
    transform:translateX(100%); transition:transform .2s ease; padding:14px; overflow-y:auto;
    display:flex; flex-direction:column; gap:12px; }
  .sb-panel.on { transform:translateX(0); }
  .sb-head { display:flex; align-items:center; justify-content:space-between; font-weight:bold; }
  .sb-close { background:none; border:none; color:var(--muted); cursor:pointer; padding:4px;
    display:inline-flex; }
  .sb-close:hover { color:var(--fg); }
  .sb-links { display:flex; flex-direction:column; gap:2px; }
  .sb-link { display:flex; align-items:center; gap:10px; padding:9px 8px; border-radius:8px;
    color:var(--fg); text-decoration:none; font-size:.9rem; min-height:44px; }
  .sb-link:hover { background:var(--surface-control); }
  .sb-link .nav-badge { margin-left:auto; }
  .sb-ico { display:inline-flex; color:var(--muted); flex-shrink:0; }
  .sb-hist-head { display:flex; align-items:center; gap:5px; color:var(--muted); font-size:.85rem;
    border-top:1px solid var(--line); padding-top:10px; }
  .sb-sessions { display:flex; flex-direction:column; gap:8px; min-width:0; }
  .sb-session-help { color:var(--muted); font-size:.76rem; line-height:1.5; margin:0; overflow-wrap:anywhere; }
  .sb-session-label { font-size:.8rem; }
  .sb-session-control { width:100%; min-height:44px; box-sizing:border-box; border:1px solid var(--line);
    border-radius:8px; padding:8px; background:var(--surface-control); color:var(--fg); font:inherit; font-size:.82rem; }
  button.sb-session-control { cursor:pointer; }
  .sb-session-control:disabled { opacity:.65; }
  .sb-session-item { cursor:default; }
  .sb-session-title { flex:1 1 100%; min-width:0; min-height:44px; padding:4px 0; border:0;
    background:none; color:var(--accent); font:inherit; font-weight:bold; text-align:left; overflow-wrap:anywhere; }
  button.sb-session-title { cursor:pointer; }
  .sb-session-item .hist-summary, .sb-session-item .hist-request { flex:1 1 100%; min-width:0;
    white-space:normal; overflow-wrap:anywhere; display:-webkit-box; -webkit-box-orient:vertical;
    -webkit-line-clamp:3; overflow:hidden; line-height:1.5; }
  .sb-session-item .hist-request { color:var(--muted); font-size:.76rem; -webkit-line-clamp:2; }
  .sb-runs { font-size:.82rem; color:var(--muted); }
  .sb-runs summary { min-height:44px; display:flex; align-items:center; cursor:pointer; }
  @media (max-width: 700px) { .sb-panel { width:min(280px, 82vw); } }
  :is(a,button,input,select,textarea,summary,[tabindex]):focus-visible {
    outline:3px solid var(--accent); outline-offset:3px;
  }
  @media(prefers-reduced-motion:reduce) {
    *,*::before,*::after { animation-duration:.01ms !important;
      animation-iteration-count:1 !important; transition-duration:.01ms !important;
      scroll-behavior:auto !important; }
  }
"""
