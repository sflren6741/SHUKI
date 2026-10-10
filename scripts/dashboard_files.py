#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_files.py — 📁 ファイル（dashboard_server.py の /files ページ・2026-08-18 新設）

vault全体の.md（タスク・プロジェクト・ログ・リソース・インボックス等すべて）を、
Obsidianを開かずに一覧・検索・絞り込み・並べ替え・束ねて閲覧するためのページ
（タスク: SHUKIダッシュボードからvault全ファイルを閲覧・検索できるようにする）。

既存機能の使い回し（ハードコードしない・ユーザーの要望どおり）:
  - フィルタ・ソート・グルーピングのエンジンは dashboard_facets.py（/board から2026-08-18切り出し）
  - 一覧取得は VAULT_INDEX（vault_index.py）が既に全件バックグラウンドインデックス済み
  - プレビューは read_preview_md()（frontmatter除去 + md_to_html）を使う
  - wikilinkのその場展開（1段だけ潜れる）ロジックを旧レビュー画面から引き継ぐ

データは /files/data から取得（軽量メタデータのみ・本文は含まない。実測: 2149件で約700KB→
gzip前提なしでも一括ロードが現実的なサイズ。フィールドを増やすと肥大化するため、絞り込み・
表示に使わない値は積まない）。プレビューは /files/preview?p=<vault相対パス>（GET）。
サーバーは vault 本体を書かない不変条件は他ページと同じ（このページに書き込み操作は無い）。
"""
import dashboard_ui  # noqa: E402  (nav_html/bottom_nav_html/PWA_HEAD/RESPONSIVE_CSS を再利用)
import dashboard_chat  # noqa: E402  (💬 全ページ共通の対話ドック)
import dashboard_icons  # noqa: E402  (線アイコンSVG)
import dashboard_facets  # noqa: E402  (🔎 絞り込み・グルーピング・ソートの共有エンジン)
import json  # noqa: E402  (非公開ログフォルダの差し込み)
import shuki_profile  # noqa: E402  (非公開パスの単一情報源。2026-09-27)

# 非公開ログフォルダは個人の設定（profile.json の private_path_prefixes）。
# ここに具体的なフォルダ名を書かない＝コードを見ても誰の運用か分からない状態を保つ。
_PRIVATE_LOG_KINDS = {pre.rstrip('/'): '日記'
                      for pre in shuki_profile.private_path_prefixes()
                      if pre.startswith('07_Logs/')}

_ICON_CHECK_S = dashboard_icons.ui_icon_svg("check", 11)
_ICON_CROSS_S = dashboard_icons.ui_icon_svg("cross", 11)
_ICON_GEAR_S = dashboard_icons.nav_icon_svg("settings", 13)
_ICON_DOC = dashboard_icons.ui_icon_svg("doc", 16)

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title>📁 ファイル</title>
<style>
  * { box-sizing:border-box; margin:0; }
  /* デザイントークンは /theme.css が単一の正（共通ページと同じ流儀）。 */
  body { background:var(--bg); color:var(--fg);
    font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  header { flex-shrink:0; }
  .filter-bar { display:flex; align-items:center; gap:8px; padding:6px 16px;
    border-bottom:1px solid var(--line); flex-shrink:0; flex-wrap:wrap; }
  .filter-bar select, .filter-bar input[type=search] { background:var(--card); border:1px solid var(--line);
    color:var(--fg); border-radius:2px; padding:4px 9px; font-size:.8rem; font-family:inherit; }
  .filter-bar select:focus, .filter-bar input[type=search]:focus { outline:none; border-color:var(--accent); }
  .filter-bar input[type=search] { width:170px; }
""" + dashboard_facets.engine_css() + dashboard_facets.views_css() + """
  #rq-sentinel { padding:14px; text-align:center; color:var(--muted); font-size:.76rem; }
  #loading, #empty-state { display:flex; align-items:center; justify-content:center;
    color:var(--muted); gap:10px; font-size:.9rem; padding:60px 20px; text-align:center; flex-direction:column; }
  .spin { animation:spin 1.2s linear infinite; display:inline-block; }
  @keyframes spin { to { transform:rotate(360deg); } }
  main { flex:1; padding:14px 16px 24px; max-width:820px; width:100%; margin:0 auto; }
  .group-heading { font-size:.76rem; color:var(--muted); font-weight:bold; margin:14px 0 6px; padding-left:2px;
    display:flex; align-items:center; gap:6px; }
  .group-heading:first-child { margin-top:0; }
  .group-heading .gh-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
  .group-heading .gh-n { margin-left:auto; color:var(--muted); font-weight:normal; }
  .item { background:var(--card); border:1px solid var(--line); border-radius:12px;
    margin-bottom:8px; overflow:hidden; }
  .item-hd { display:flex; align-items:flex-start; gap:10px; padding:11px 14px; cursor:pointer; }
  .item-emoji { color:var(--muted); flex-shrink:0; line-height:1.3; margin-top:1px; }
  .item-body { flex:1; min-width:0; }
  .item-title { font-size:.88rem; font-weight:bold; line-height:1.4; word-break:break-word; }
  .item-summary { font-size:.74rem; color:var(--muted); margin-top:2px; line-height:1.4; }
  .item-task { font-size:.7rem; color:var(--muted); margin-top:4px; line-height:1.35; }
  .item-task a { color:var(--accent); text-decoration:none; border-bottom:1px dashed var(--accent); }
  .fm-badges { display:flex; gap:4px; flex-wrap:wrap; margin-top:5px; }
  /* コンパクト表示（2026-08-20）: タイトル行だけを詰めて出す。folder/バッジは隠す
     （画像を持たないMarkdownが大半のvaultで「ギャラリー」より実用的な密度切替として採用）。
     board.py の f-density（標準/最小/詳細）と同じ発想を /files に横展開。 */
  #list.compact .item { border-radius:2px; margin-bottom:2px; }
  #list.compact .item-hd { padding:6px 14px; align-items:center; }
  #list.compact .item-title { font-size:.82rem; font-weight:normal; }
  #list.compact .item-summary, #list.compact .fm-badges { display:none; }
  #list.compact .item-emoji { display:none; }
  .fm-badge { font-size:.66rem; border-radius:4px; padding:1px 6px; background:var(--line); color:var(--muted); }
  .fm-badge.s-in-progress { background:color-mix(in srgb, var(--teal) 18%, transparent); color:var(--teal); }
  .fm-badge.s-on-hold, .fm-badge.s-pending { background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); }
  .fm-badge.s-done { background:color-mix(in srgb, var(--teal) 24%, transparent); color:var(--teal); }
  .fm-badge.s-cancelled, .fm-badge.s-archived, .fm-badge.s-rejected { background:color-mix(in srgb, var(--muted) 16%, transparent); color:var(--muted); }
  .fm-badge.a-review { background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); }
  /* 更新バッジ行: ビューチップ(v-row)とは質が異なる更新通知のため
     別行・別スタイルで分離する。0件時は行ごと非表示（JS側で display:none を切り替える）。 */
  .u-row { display:none; align-items:center; gap:8px; padding:8px 16px; flex-shrink:0; }
  .u-badge { display:inline-flex; align-items:center; gap:5px; border-radius:8px;
    padding:6px 14px; font-size:.8rem; font-weight:bold; cursor:pointer; border:1px solid transparent; }
  .u-badge:hover { filter:brightness(1.08); }
  .u-badge.u-task { background:color-mix(in srgb, var(--teal) 16%, transparent); color:var(--teal); border-color:color-mix(in srgb, var(--teal) 35%, transparent); }
  .u-badge.u-file { background:color-mix(in srgb, var(--blue) 16%, transparent); color:var(--blue); border-color:color-mix(in srgb, var(--blue) 35%, transparent); }
  .item-caret { color:var(--muted); font-size:.75rem; flex-shrink:0; margin-top:3px; transition:transform .15s; }
  .item.open .item-caret { transform:rotate(90deg); }
  .item-preview { display:none; position:relative; border-top:1px solid var(--line); }
  .item.open .item-preview { display:flex; flex-direction:column; }
  .item-acts { display:flex; gap:6px; flex-wrap:wrap; padding:0 16px 14px; }
  .act-btn { background:none; border:1px solid var(--line); color:var(--muted);
    border-radius:2px; padding:6px 12px; cursor:pointer; font-size:.78rem; font-family:inherit;
    min-height:44px; }
  .act-btn:hover { border-color:var(--accent); color:var(--fg); }
  .act-btn.ok { border-color:var(--teal); color:var(--teal); }
  .act-btn.warn { border-color:var(--warn); color:var(--warn); }
  .act-btn.danger { border-color:var(--danger); color:var(--danger); }
  .act-btn.errflash { border-color:var(--danger); color:var(--danger); }
  #files-toast { position:fixed; left:50%; bottom:24px; z-index:1600; max-width:calc(100vw - 32px);
    transform:translate(-50%, 8px); opacity:0; pointer-events:none; transition:opacity .15s, transform .15s;
    background:var(--card); border:1px solid var(--line); color:var(--fg); border-radius:6px;
    padding:9px 14px; font-size:.8rem; box-shadow:0 4px 18px color-mix(in srgb, var(--bg) 45%, transparent); }
  #files-toast.show { transform:translate(-50%, 0); opacity:1; }
  #files-toast.err { border-color:var(--danger); color:var(--danger); }
  .note-box { display:none; padding:0 16px 14px; gap:6px; }
  .note-box.open { display:flex; flex-direction:column; }
  .note-box textarea { background:var(--bg); border:1px solid var(--line); color:var(--fg);
    border-radius:2px; padding:8px 10px; font-size:.82rem; font-family:inherit; resize:vertical;
    min-height:60px; }
  .update-preview { padding:12px 16px 14px; font-size:.84rem; line-height:1.65; }
  .update-preview h3 { color:var(--accent); font-size:.9rem; margin:0 0 6px; }
  .update-preview p { margin:5px 0; }
  .update-context { color:var(--muted); }
  .update-choice { margin-top:8px; padding-top:8px; border-top:1px solid var(--line); }
  .update-task { font-size:.74rem; color:var(--muted); margin-top:8px; }
  /* 最大化（2026-09-03、ユーザーの指摘で2度修正）: 開いたドキュメントを画面いっぱい
     （inset:0・角丸なし）に広げて読める状態にする。ドックより手前に出す（z-index比較）。
     ボタンは「固定ツールバー(.pv-toolbar) + スクロール本体(.pv-body)」という構造にして
     スクロール領域の外に出す — 通常時・最大化時のどちらも本文と一緒に流れて
     見えなくなることがないようにする（絶対配置のままだとスクロールコンテナ内で
     本文と一緒に流れる／固定配置に頼るのは最大化時しか効かず、通常時のスクロールでは
     再現する。ボタンをスクロール対象の外に置くのが根本対処）。 */
  .pv-toolbar { display:flex; justify-content:flex-end; padding:8px 14px 0; flex-shrink:0; }
  .pv-body { padding:6px 16px 14px; font-size:.85rem; line-height:1.75;
    max-height:60vh; overflow-y:auto; overflow-x:auto; }
  .pv-maxi-btn { background:var(--card); border:1px solid var(--line); color:var(--muted);
    border-radius:6px; padding:2px 9px; font-size:.72rem; cursor:pointer; font-family:inherit; }
  .pv-maxi-btn:hover { color:var(--fg); border-color:var(--accent); }
  .item-preview.maxi { position:fixed; inset:0; z-index:1400;
    background:var(--card); border:none; border-radius:0; }
  .item-preview.maxi .pv-toolbar { padding:14px 18px 8px; }
  .item-preview.maxi .pv-body { max-height:none; flex:1; padding:8px 20px 20px; }
  .item-preview h2, .item-preview h3, .item-preview h4 { margin:12px 0 6px; color:var(--accent); font-size:.95rem; }
  .item-preview h2:first-child, .item-preview h3:first-child, .item-preview h4:first-child { margin-top:0; }
  .item-preview p { margin:6px 0; }
  .item-preview ul, .item-preview ol { padding-left:1.3em; margin:6px 0; }
  .item-preview li { margin:2px 0; }
  .item-preview code { background:var(--line); border-radius:4px; padding:0 4px; font-size:.8rem; }
  .item-preview blockquote { border-left:3px solid var(--line); margin:8px 0; padding:2px 0 2px 10px; color:var(--muted); }
  .item-preview .callout { border-radius:8px; padding:8px 10px; margin:8px 0; font-size:.82rem; }
  .item-preview .callout.warning { background:color-mix(in srgb, var(--warn) 8%, transparent); border:1px solid color-mix(in srgb, var(--warn) 27%, transparent); }
  .item-preview .callout.danger  { background:color-mix(in srgb, var(--danger) 8%, transparent); border:1px solid color-mix(in srgb, var(--danger) 27%, transparent); }
  .item-preview .co-title { font-weight:bold; margin-bottom:4px; }
  .item-preview .pv-loading, .item-preview .pv-err { color:var(--muted); font-size:.8rem; }
  .item-preview img, .item-preview svg { max-width:100%; border-radius:8px; margin:8px 0; display:block; }
  .item-preview table { border-collapse:collapse; margin:8px 0; font-size:.8rem; max-width:100%; }
  .item-preview th, .item-preview td { border:1px solid var(--line); padding:4px 8px; text-align:left; }
  .item-preview th { color:var(--accent); }
  .item-preview hr { border:0; border-top:1px solid var(--line); margin:14px 0; }
  .item-preview a { color:var(--accent); }
  .item-preview a.wl { text-decoration:none; border-bottom:1px dashed var(--accent); cursor:pointer; }
  .item-preview .wl-missing { color:var(--muted); border-bottom:1px dotted var(--muted); }
  .item-preview pre.mermaid { background:none; margin:10px 0; text-align:center; overflow-x:auto; }
  .preview-diff { margin:12px 0 4px; border:1px solid color-mix(in srgb, var(--accent) 30%, var(--line)); border-radius:8px; overflow:hidden; }
  .preview-diff summary { cursor:pointer; padding:7px 10px; color:var(--accent); font-size:.75rem; font-weight:bold; background:color-mix(in srgb, var(--accent) 7%, transparent); }
  .preview-diff-code { padding:6px 0; background:color-mix(in srgb, var(--line) 32%, var(--card)); font: .75rem/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; overflow-x:auto; }
  .preview-diff-line { padding:0 10px; white-space:pre; }
  .preview-diff-line.added { background:color-mix(in srgb, var(--teal) 16%, transparent); color:var(--teal); }
  .preview-diff-line.removed { background:color-mix(in srgb, var(--danger) 14%, transparent); color:var(--danger); }
  .preview-diff-mark { display:inline-block; width:1.2em; color:var(--muted); user-select:none; }
  .preview-diff-hunk { padding:3px 10px; color:var(--accent); background:color-mix(in srgb, var(--accent) 8%, transparent); }
  .wl-nest { border-left:2px solid var(--accent); margin:8px 0 8px 4px; padding-left:12px; }
  /* 埋め込みを下までスクロールしても閉じる操作（もう一度クリック）にすぐ手が届くよう、
     タイトル行を画面上部に固定表示する（ユーザーの要望・2026-09-03）。 */
  .wl-nest-hd { font-size:.72rem; color:var(--muted); margin-bottom:4px;
    position:sticky; top:0; background:var(--card); z-index:2; padding:2px 0; cursor:pointer; }
  .wl-nest-hd:hover { color:var(--fg); }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head>
<body>

<!--SHUKI_PAGE_HEADER-->

<div id="u-row" class="u-row"></div>
<div id="v-row" class="v-row"></div>
<div class="filter-bar">
  <div class="tb-grp">
    <span class="tb-ico" title="タイトル・パスで検索">""" + dashboard_icons.ui_icon_svg("search", 14) + """</span>
    <input type="search" id="f-search" placeholder="ファイル検索…" oninput="applyFilters()">
  </div>

  <span class="tb-sep"></span>
  <div class="tb-grp">
    <span class="tb-ico" title="絞り込み">""" + dashboard_icons.ui_icon_svg("filter", 14) + """</span>
    <div id="f-chips" class="f-chips"></div>
    <button id="f-add" class="f-add" title="絞り込む条件を追加">""" + dashboard_icons.ui_icon_svg("plus", 13) + """ 条件</button>
  </div>

  <span class="tb-sep"></span>
  <div class="tb-grp">
    <span class="tb-ico" title="並べ替え">""" + dashboard_icons.ui_icon_svg("sort", 14) + """</span>
    <select id="f-sort" onchange="onSortMetricChange()" title="並べ替え">
      <option value="created">作成日</option>
      <option value="mtime">更新順</option>
      <option value="title">タイトル</option>
    </select>
    <select id="f-sort-dir" onchange="applyFilters(); savePrefs();" title="並べ替えの向き">
      <option value="desc">▼降順</option>
      <option value="asc">▲昇順</option>
    </select>
  </div>

  <span class="tb-sep"></span>
  <div class="tb-grp">
    <span class="tb-ico" title="束ね方（グルーピング）">""" + dashboard_icons.ui_icon_svg("layers", 14) + """</span>
    <select id="f-group" onchange="applyFilters()" title="束ね方（グルーピング）">
      <option value="folder">フォルダ別</option>
      <option value="kind">日記/作業別</option>
      <option value="type">種別別</option>
      <option value="area">Area別</option>
      <option value="status">ステータス別</option>
      <option value="month">作成月別</option>
      <option value="none">束ねない</option>
    </select>
  </div>

  <span class="tb-sep"></span>
  <div class="tb-grp">
    <span class="tb-ico" title="表示方式">""" + dashboard_icons.ui_icon_svg("eye", 14) + """</span>
    <select id="f-density" onchange="onDensityChange()" title="表示方式">
      <option value="list">リスト</option>
      <option value="compact">コンパクト</option>
    </select>
  </div>

  <span id="file-count" style="font-size:.76rem;color:var(--muted);margin-left:4px;"></span>
</div>
<div id="f-pop"></div>
<div id="files-toast" role="status" aria-live="polite"></div>

<main>
  <div id="loading"><span class="spin">""" + dashboard_icons.ui_icon_svg("loading", 15) + """</span> 読み込み中…</div>
  <div id="empty-state" style="display:none;">""" + dashboard_icons.ui_icon_svg("search", 15) + """ 条件に一致するファイルがありません</div>
  <div id="list"></div>
</main>
<!--SHUKI_BOTTOM_NAV-->

<script src="/assets/mermaid.min.js"></script>
<script>
let ALL = [], MAP = {};

const _cs = getComputedStyle(document.documentElement);
const _cv = name => _cs.getPropertyValue(name).trim();
if (window.mermaid) {
  mermaid.initialize({
    startOnLoad: false, theme: 'base',
    themeVariables: {
      background: _cv('--bg'), primaryColor: _cv('--card'), primaryTextColor: _cv('--fg'),
      primaryBorderColor: _cv('--line'), lineColor: _cv('--muted'),
      secondaryColor: _cv('--card'), tertiaryColor: _cv('--bg'),
      fontFamily: _cv('--font-ui')
    }
  });
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ===== 軸（AXES）— vaultファイル向け。値は固定列挙せず ALL から動的に組み立てる
   （固定割り当てより動的選択＝実績の多い順に並べる。board.py の areaDefs/createdDefs と同じ流儀）。 */
const AXIS_COLORS = ['var(--accent)', 'var(--blue)', 'var(--teal)', 'var(--warn)', 'var(--danger)', 'var(--muted)'];
function countBy(keyFn) {
  const n = {};
  ALL.forEach(t => { const k = keyFn(t); n[k] = (n[k] || 0) + 1; });
  return n;
}
function dynDefs(keyFn) {
  const n = countBy(keyFn);
  return Object.keys(n).sort((a, b) => n[b] - n[a])   /* 件数の多い方から（動的選択） */
    .map((k, i) => ({ key:k, label:k, color:AXIS_COLORS[i % AXIS_COLORS.length] }));
}
function monthDefs() {
  const n = countBy(t => t.month || '(不明)');
  return Object.keys(n).sort((a, b) => (a === '(不明)') - (b === '(不明)') || b.localeCompare(a))
    .map(k => ({ key:k, label: k === '(不明)' ? '不明' : k.slice(0, 4) + '年' + (+k.slice(5, 7)) + '月',
                 color: k === '(不明)' ? 'var(--muted)' : 'var(--blue)' }));
}
/* トップフォルダ（07_Logs 等）だけの一覧。組み込みビューのショートカット生成に使う。 */
function topFolderDefs() { return dynDefs(t => t.top || '(直下)'); }
/* フォルダ軸はサブフォルダまでの全階層（フルパス）を対象にする（2026-08-19、ユーザーの要望）。
   値はハードコードせず vault_index が返す folder のユニーク値から動的に組み立て、
   親フォルダ配下をインデント付きツリーとして表示する（色はトップフォルダ単位で揃える）。 */
/* フォルダに子孫がある場合、「そのフォルダ直下のみ（子孫を含まない）」を選べる特殊キーを
   兄弟として追加する（2026-08-19、ユーザーの要望：ログ直下だけを見たいのに配下も混ざる問題）。
   キーは folder値 + LEAF_SUFFIX。matches() 側でサフィックスを見て完全一致に倒す。 */
const LEAF_SUFFIX = '␟leaf';
function folderDefs() {
  const n = countBy(t => t.folder || '(直下)');
  const topColor = {};
  topFolderDefs().forEach(d => { topColor[d.key] = d.color; });
  const keys = Object.keys(n);
  const hasChildren = new Set();
  keys.forEach(k => { if (k !== '(直下)') keys.forEach(k2 => { if (k2 !== k && k2.startsWith(k + '/')) hasChildren.add(k); }); });
  const defs = [];
  keys.sort((a, b) => a.localeCompare(b, 'ja')).forEach(k => {
    const parts = k === '(直下)' ? [] : k.split('/');
    const depth = parts.length ? parts.length - 1 : 0;
    const name = parts.length ? parts[parts.length - 1] : '(直下)';
    const top = parts.length ? parts[0] : '(直下)';
    const indent = depth ? '　'.repeat(depth) + '└ ' : '';
    const color = topColor[top] || 'var(--muted)';
    defs.push({ key:k, label: indent + name, color });
    if (hasChildren.has(k)) {
      defs.push({ key: k + LEAF_SUFFIX, label: indent + '　└ ' + name + '（直下のみ）', color });
    }
  });
  return defs;
}
/* 日記/作業ログ の大分類（kind軸）。07_Logs/ログ直下は frontmatter の type（日記/作業/雑記・
   2026-08-19導入）をそのまま使う。サブフォルダ（_private・関係の振り返り・家計等）は既に
   具体的な type（CBT思考記録・家計レポート等）が入っていて上書きすると情報が失われるため、
   vault側は変更せずフォルダ名からのマッピングで大分類だけをこのページ側で合成する。 */
const LOG_FOLDER_KIND = {
  ...""" + json.dumps(_PRIVATE_LOG_KINDS, ensure_ascii=False) + """,
  '07_Logs/ログ/人から言われたことは１回で直す': '日記', '07_Logs/ログ/原動力地図': '日記',
  '07_Logs/ログ/家計': '作業', '07_Logs/ログ/栄養': '作業',
  '07_Logs/ログ/購買リコメンド': '作業', '07_Logs/ログ/週次レビュー': '作業',
  '07_Logs/ログ/示唆型分析': '作業',
};
function kindOf(t) {
  if (t.type === '日記' || t.type === '作業' || t.type === '雑記') return t.type;
  const f = t.folder || '';
  for (const prefix in LOG_FOLDER_KIND) {
    if (f === prefix || f.startsWith(prefix + '/')) return LOG_FOLDER_KIND[prefix];
  }
  return '(未設定)';
}
const AXES = {
  record_kind: { label:'対象', keyOf:t => t.record_kind || 'file',
    defs:() => [{ key:'file', label:'ファイル', color:'var(--muted)' },
                { key:'update', label:'更新', color:'var(--accent)' }] },
  folder: { label:'フォルダ', keyOf:t => t.folder || '(直下)', defs:folderDefs,
    /* 選んだフォルダそのもの、またはその配下（前方一致）を対象にする＝子フォルダも一括で選べる。
       LEAF_SUFFIX 付きキーは直下のみ（子孫を含まない）完全一致。 */
    matches: (t, sel) => {
      const f = t.folder || '(直下)';
      return sel.some(s => s.endsWith(LEAF_SUFFIX) ? f === s.slice(0, -LEAF_SUFFIX.length)
                                                     : (f === s || f.startsWith(s + '/')));
    } },
  kind:   { label:'日記/作業',    keyOf:kindOf, defs:() => dynDefs(kindOf) },
  type:   { label:'種別',         keyOf:t => t.type || '(未設定)', defs:() => dynDefs(t => t.type || '(未設定)') },
  area:   { label:'Area',         keyOf:t => t.area || '(未設定)', defs:() => dynDefs(t => t.area || '(未設定)') },
  status: { label:'ステータス',   keyOf:t => t.status || '(未設定)', defs:() => dynDefs(t => t.status || '(未設定)') },
  month:  { label:'作成月',       keyOf:t => t.month || '(不明)',  defs:monthDefs },
  attention: { label:'対応', keyOf:t => (t.attention || [])[0] || '(対象外)',
    defs:() => [{ key:'review', label:'要確認', color:'var(--accent)' }],
    matches:(t, sel) => sel.some(s => (t.attention || []).includes(s)) },
  update_kind: { label:'更新', keyOf:t => (t.update_kinds || [])[0] || '(対象外)',
    defs:() => [{ key:'task', label:'更新タスク', color:'var(--teal)' },
                { key:'file', label:'更新ファイル', color:'var(--blue)' }],
    matches:(t, sel) => sel.some(s => (t.update_kinds || []).includes(s)) },
};
let FILTERS = {};   /* 既定は絞り込みなし＝「vault全部を見れたほうがいい」という要望に合わせる */
""" + dashboard_facets.engine_js(_ICON_CHECK_S, _ICON_CROSS_S) + """

/* ファイル固有の検索対象。共有エンジンの既定関数をページ側で上書きする。
   t.path（フルパス）も含める: openTargetFromQuery() が /files?p=<フルパス> で
   検索ボックスにフルパスをそのまま入れて絞り込むため、ここに無いと
   folder（末尾のファイル名を含まない）とtitle（先頭のフォルダを含まない）の
   どちらとも部分一致せず、該当ファイルが実在してもヒット0件で静かに何も表示されない
   （2026-09-26 修正: /files で直接パス指定した時に「見つからない」バグの原因）。 */
function searchText(t) { return [t.title, t.folder, t.summary, t.task_title, t.task_path, t.path].filter(Boolean).join(' '); }

/* ===== 保存済みビュー（フォルダ別ショートカット＋カスタム保存。dashboard_facets.py 共有部品） =====
   組み込みビューは folder軸のdefs()（件数の多い順・動的）から自動生成＝フォルダ名をハードコードしない。 */
let DEFAULT_VIEWS = [];
function buildDefaultViews() {
  /* 組み込みビューはトップフォルダ単位のまま（folder軸自体は子フォルダまで前方一致で
     絞れるので、トップフォルダのキーを渡すだけで配下も含めて選択される）。 */
  const folders = topFolderDefs().slice(0, 8);
  const fileOnly = extra => Object.assign({ record_kind:['file'] }, extra || {});
  DEFAULT_VIEWS = [
    { id:'v-all', name:'すべて', builtin:true,
      state:{ filters:fileOnly(), group:'folder', sort:'created', sortDir:'desc' } },
    { id:'v-diary', name:'日記', builtin:true,
      state:{ filters:fileOnly({ kind:['日記'] }), group:'folder', sort:'created', sortDir:'desc' } },
    { id:'v-work', name:'作業ログ', builtin:true,
      state:{ filters:fileOnly({ kind:['作業'] }), group:'folder', sort:'created', sortDir:'desc' } },
  ].concat(folders.map(d => ({
    id:'v-folder-' + d.key, name:d.label, builtin:true,
    state:{ filters:fileOnly({ folder:[d.key] }), group:'none', sort:'created', sortDir:'desc' },
  })));
}
""" + dashboard_facets.views_js("shuki_files_custom_views", _ICON_CROSS_S, _ICON_CHECK_S, _ICON_GEAR_S) + """

/* ===== 更新バッジ行 =====
   ビューチップ(v-row)は「同じファイル集合を別の軸で見る分類タブ」、
   こちらは更新通知のため別行に分離する。更新タスクと更新ファイルだけを表示し、
   0件なら行ごと非表示にする。クリック時は既存の attention フィルタと同じ
   絞り込み（group:none, sort:mtime desc）を適用する。 */
function renderUpdateBadges() {
  const row = document.getElementById('u-row');
  if (!row) return;
  const count = ALL.filter(t => (t.attention || []).includes('review')).length;
  row.style.display = 'flex';
  row.innerHTML = '<a class="u-badge" href="/notifications">Notifications (' + count + ')</a>'
    + ' <a class="u-badge" href="/notifications?history=1">Recent activity</a>';
}
document.addEventListener('click', e => {
  const kind = e.target.closest('[data-update-kind]');
  if (kind) {
    applyViewState({ filters:{ attention:['review'], update_kind:[kind.dataset.updateKind] },
                     group:'none', sort:'mtime', sortDir:'desc' });
    return;
  }
});

/* ===== 並び順 ===== */
const SORT_METRICS = {
  created: { label:'作成日', defaultDir:'desc',
    cmp: (x, y, dir) => dirSign(dir) * (x.date || '0000').localeCompare(y.date || '0000') || x.title.localeCompare(y.title, 'ja') },
  mtime:   { label:'更新順', defaultDir:'desc',
    cmp: (x, y, dir) => dirSign(dir) * (x.mtime - y.mtime) },
  title:   { label:'タイトル', defaultDir:'asc',
    cmp: (x, y, dir) => dirSign(dir) * x.title.localeCompare(y.title, 'ja') },
};
function onSortMetricChange() {
  const m = SORT_METRICS[document.getElementById('f-sort').value];
  if (m) document.getElementById('f-sort-dir').value = m.defaultDir;
  applyFilters();
  savePrefs();
}

/* ===== 表示方式（リスト/コンパクト・2026-08-20） =====
   board.py の f-density と同じ発想。CSSクラストグルのみで完結し再描画は不要。 */
function applyDensity() {
  const v = document.getElementById('f-density').value;
  document.getElementById('list').classList.toggle('compact', v === 'compact');
}
function onDensityChange() {
  applyDensity();
  savePrefs();
}

/* ===== ビュー設定の永続化（端末ごと。vault本体は書かない。board.py と同じ流儀） ===== */
const PREF_KEY = 'shuki_files_view';
const PREF_IDS = ['f-group', 'f-sort', 'f-sort-dir', 'f-density'];
function loadPrefs() {
  let p = {};
  try { p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch(e) { p = {}; }
  PREF_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el && p[id] != null && [...el.options].some(o => o.value === p[id])) el.value = p[id];
  });
  applyDensity();
  if (p.filters && typeof p.filters === 'object') {
    const f = {};
    Object.keys(p.filters).forEach(k => { if (AXES[k] && Array.isArray(p.filters[k])) f[k] = p.filters[k]; });
    FILTERS = f;
  }
}
function savePrefs() {
  const p = { filters:FILTERS };
  PREF_IDS.forEach(id => { p[id] = document.getElementById(id).value; });
  try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch(e) {}
}

function applyFilters() {
  savePrefs();
  renderChips();
  renderViews();
  const vis = filteredTasks();
  document.getElementById('file-count').textContent = vis.length + ' 件';
  render(vis);
}

/* ===== 一覧描画（チャンク分割・2026-08-19）=====
   vault全体（2000件超）を一度にDOMへ置くと初期描画が重いため、束ね・並べ替え済みの
   順序を一度だけ組み立てて（RQ）、80件ずつスクロールに応じて追加描画する。
   グループ跨ぎでも順序は1本の列として扱う＝どのグループも先頭から遅延なく見える。 */
let RQ = [], RQ_IDX = 0;
const RQ_CHUNK = 80;
let rqObserver = null;

function buildQueue(vis) {
  const gk = document.getElementById('f-group').value;
  const sortMetric = SORT_METRICS[document.getElementById('f-sort').value] || SORT_METRICS.created;
  const sortDir = document.getElementById('f-sort-dir').value || sortMetric.defaultDir;
  const cmp = (x, y) => sortMetric.cmp(x, y, sortDir);
  const q = [];
  groupTasks(gk, vis).forEach(g => {
    if (gk !== 'none') q.push({ kind:'head', label:g.label, color:g.color, n:g.items.length });
    g.items.slice().sort(cmp).forEach(t => q.push({ kind:'item', t }));
  });
  return q;
}

function render(vis) {
  const list = document.getElementById('list');
  const empty = document.getElementById('empty-state');
  list.innerHTML = '';
  if (rqObserver) { rqObserver.disconnect(); rqObserver = null; }
  if (!vis.length) { empty.style.display = 'flex'; return; }
  empty.style.display = 'none';
  RQ = buildQueue(vis);
  RQ_IDX = 0;
  renderMore();
}

function renderMore() {
  const list = document.getElementById('list');
  const end = Math.min(RQ.length, RQ_IDX + RQ_CHUNK);
  for (; RQ_IDX < end; RQ_IDX++) {
    const e = RQ[RQ_IDX];
    if (e.kind === 'head') {
      const h = document.createElement('div');
      h.className = 'group-heading';
      h.innerHTML = '<span class="gh-dot" style="background:' + e.color + '"></span>'
        + esc(e.label) + '<span class="gh-n">' + e.n + '</span>';
      list.appendChild(h);
    } else {
      list.appendChild(renderItem(e.t));
    }
  }
  const old = document.getElementById('rq-sentinel');
  if (old) old.remove();
  if (RQ_IDX < RQ.length) {
    const s = document.createElement('div');
    s.id = 'rq-sentinel';
    s.textContent = '残り ' + (RQ.length - RQ_IDX) + ' 件を読み込み中…';
    list.appendChild(s);
    if (!rqObserver) {
      rqObserver = new IntersectionObserver(entries => {
        if (entries.some(en => en.isIntersecting)) renderMore();
      }, { rootMargin: '600px' });
    }
    rqObserver.observe(s);
  }
}

function renderItem(t) {
  const card = document.createElement('div');
  card.className = 'item';
  card.dataset.path = t.path || t.virtual_id || '';
  const hd = document.createElement('div');
  hd.className = 'item-hd';
  const attnBadges = (t.attention || []).map(k =>
    '<span class="fm-badge a-' + esc(k) + '">' + esc(attentionLabel(k)) + '</span>').join('');
  const updateBadges = (t.update_kinds || []).map(k =>
    '<span class="fm-badge a-update-' + esc(k) + '">' + esc(updateKindLabel(k)) + '</span>').join('');
  const badges = [
    t.type ? '<span class="fm-badge">' + esc(t.type) + '</span>' : '',
    t.area ? '<span class="fm-badge">' + esc(t.area) + '</span>' : '',
    t.status ? '<span class="fm-badge s-' + esc(t.status) + '">' + esc(t.status) + '</span>' : '',
    attnBadges,
    updateBadges,
  ].filter(Boolean).join('');
  hd.innerHTML =
    '<div class="item-emoji">""" + _ICON_DOC + """</div>' +
    '<div class="item-body">' +
      '<div class="item-title">' + esc(t.title) + '</div>' +
      '<div class="item-summary">' + esc(t.folder || '(直下)') + (t.date ? ' ・ 作成 ' + esc(t.date) : '') + '</div>' +
      taskLinkHtml(t) +
      (badges ? '<div class="fm-badges">' + badges + '</div>' : '') +
    '</div>' +
    '<div class="item-caret">▶</div>';
  card.appendChild(hd);

  const pv = document.createElement('div');
  pv.className = 'item-preview';
  pv.innerHTML = '<div class="pv-toolbar"><button class="pv-maxi-btn" title="画面いっぱいに広げて読む">⛶</button></div>'
    + (t.virtual
      ? '<div class="pv-body"><div class="update-preview">' + virtualPreviewHtml(t) + '</div></div>'
      : '<div class="pv-body"><span class="pv-loading">読み込み中…</span></div>');
  card.appendChild(pv);
  hd.onclick = () => t.virtual ? toggleVirtualPreview(card) : togglePreview(card, pv, t.path);
  setupMaxiBtn(pv);
  appendUpdateActions(card, t);
  return card;
}

function attentionLabel(key) {
  return key === 'review' ? '要確認' : key;
}

function updateKindLabel(key) {
  return key === 'task' ? '更新タスク' : key === 'file' ? '更新ファイル' : key;
}

function vaultFileHref(path) { return '/files?p=' + encodeURIComponent(String(path)); }
function vaultPreviewHref(path) { return '/files/preview?p=' + encodeURIComponent(String(path)); }

function taskLinkHtml(t) {
  if (!t.task_path) return '';
      const label = t.task_title || t.task_path.split('/').pop().replace(/\\.md$/, '');
  return '<div class="item-task">タスク: <a href="' + vaultFileHref(t.task_path)
    + '" onclick="event.stopPropagation()">' + esc(label) + '</a></div>';
}

function virtualPreviewHtml(t) {
  const rows = [];
  (t.review_items || []).forEach(r => {
    rows.push('<h3>レビュー対象</h3>'
      + (r.summary ? '<p>' + esc(r.summary) + '</p>' : '')
      + (r.source ? '<p class="update-context">分類: ' + esc(r.label || r.source) + '</p>' : ''));
  });
  if (t.task_path) rows.push('<p class="update-task">タスク: ' + esc(t.task_title || t.task_path) + '</p>');
  return rows.join('') || '<p class="update-context">詳細情報はありません</p>';
}

function appendUpdateActions(card, t) {
  const reviews = t.review_items || [];
  if (!reviews.length) return;
  const acts = document.createElement('div');
  acts.className = 'item-acts';

  reviews.forEach(r => {
    if (r.ai_outcome) {
      const good = document.createElement('button');
      good.className = 'act-btn ok'; good.textContent = '役に立った';
      good.onclick = e => { e.stopPropagation(); rateUpdate(t, r, 'good', card); };
      acts.appendChild(good);
      const bad = document.createElement('button');
      bad.className = 'act-btn danger'; bad.textContent = '使えなかった';
      bad.onclick = e => { e.stopPropagation(); rateUpdate(t, r, 'bad', card); };
      acts.appendChild(bad);
    }
    const ok = document.createElement('button');
    ok.className = 'act-btn ok'; ok.textContent = r.ai_outcome ? '見た' : '確認済み';
    ok.onclick = e => { e.stopPropagation(); markUpdateReviewed(t, r, card); };
    acts.appendChild(ok);
  });

  const noteBtn = document.createElement('button');
  noteBtn.className = 'act-btn'; noteBtn.textContent = 'メモ';
  const noteBox = document.createElement('div');
  noteBox.className = 'note-box';
  noteBox.innerHTML = '<textarea placeholder="次便で orchestrator に伝えるメモ…"></textarea>'
    + '<button class="act-btn ok" style="align-self:flex-start;">送信</button>';
  noteBtn.onclick = e => { e.stopPropagation(); noteBox.classList.toggle('open'); };
  noteBox.querySelector('button').onclick = e => {
    e.stopPropagation();
    const text = noteBox.querySelector('textarea').value.trim();
    if (text) sendUpdateNote(t, text, noteBox);
  };
  acts.appendChild(noteBtn);
  card.appendChild(acts);
  card.appendChild(noteBox);
}

function updateRecordAfterAction(t, itemId) {
  const idx = ALL.indexOf(t);
  if (idx < 0) return;
  t.review_items = (t.review_items || []).filter(x => x.id !== itemId);
  if (!t.review_items.length) t.attention = (t.attention || []).filter(x => x !== 'review');
  if (t.virtual && !t.review_items.length) ALL.splice(idx, 1);
  MAP = {};
  ALL.forEach(x => { MAP[x.path || x.virtual_id] = x; });
  applyFilters();
}

let filesToastTimer = null;
function showFilesToast(message, error) {
  const el = document.getElementById('files-toast');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('err', !!error);
  el.classList.add('show');
  clearTimeout(filesToastTimer);
  filesToastTimer = setTimeout(() => el.classList.remove('show'), 2400);
}

function markUpdateReviewed(t, r, card) {
  fetch('/review/reviewed', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id:r.id, kind:r.kind, version_key:r.version_key }),
  }).then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res; })
    .then(() => { if (window.SFX) SFX.tick(); showFilesToast('確認済みにしました'); updateRecordAfterAction(t, r.id); })
    .catch(e => { showFilesToast('確認の記録に失敗しました', true); card.classList.add('errflash'); setTimeout(() => card.classList.remove('errflash'), 1500); });
}

function rateUpdate(t, r, rating, card) {
  let comment = '';
  if (rating === 'bad') comment = prompt('どこが外れていましたか？（任意）', '') || '';
  fetch('/review/rate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id:r.id, title:r.title || t.title, agent:r.agent || '', rating:rating,
                           comment:comment, version_key:r.version_key }),
  }).then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res; })
    .then(() => { if (window.SFX) SFX.tick(); showFilesToast('フィードバックを記録しました'); updateRecordAfterAction(t, r.id); })
    .catch(e => { showFilesToast('フィードバックの記録に失敗しました', true); card.classList.add('errflash'); setTimeout(() => card.classList.remove('errflash'), 1500); });
}

function sendUpdateNote(t, text, noteBox) {
  fetch('/queue', {
    method:'POST', headers:{ 'Content-Type':'application/json' },
    body:JSON.stringify({ name:'review_note', payload:{
      item_title:t.title, item_path:t.task_path || t.path || t.source_path || '', note:text,
      date:new Date().toLocaleDateString('sv-SE'),
    }}),
  }).then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res; })
    .then(() => { noteBox.classList.remove('open'); noteBox.querySelector('textarea').value = ''; showFilesToast('メモをキューに追加しました'); })
    .catch(() => { showFilesToast('メモの送信に失敗しました', true); });
}

function toggleVirtualPreview(card) {
  card.classList.toggle('open');
}

/* ===== プレビュー（正規エンドポイント /files/preview。read_preview_md を共有） ===== */
async function togglePreview(card, pv, path) {
  const wasOpen = card.classList.contains('open');
  card.classList.toggle('open');
  if (wasOpen || pv.dataset.loaded) return;
  await loadPreview(pv, path);
}
async function loadPreview(pv, path, nested) {
  // .pv-body が無い（= wl-nest の入れ子プレビュー。最大化ツールバーを持たない
  // シンプル構造のまま）場合は pv 自身をレンダリング先にする。
  const body = pv.querySelector('.pv-body') || pv;
  try {
    const r = await fetch(vaultPreviewHref(path));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    body.innerHTML = await r.text();
    pv.dataset.loaded = '1';
    renderMermaid(body);
    if (nested) {
      body.querySelectorAll('a.wl').forEach(a => {
        const sp = document.createElement('span');
        sp.className = 'wl-missing';
        sp.textContent = a.textContent;
        a.replaceWith(sp);
      });
    }
  } catch(e) {
    body.innerHTML = '<span class="pv-err">プレビューを読み込めませんでした: ' + esc(String(e)) + '</span>';
  }
}
function renderMermaid(root) {
  const nodes = [...root.querySelectorAll('pre.mermaid')];
  if (!nodes.length || !window.mermaid) return;
  // 構文エラー時、mermaid.run()はreject/catchでなく「Syntax error in text」のエラーSVGを
  // DOMへ直接書き込む（v10.9系の仕様）。描画後にerror-iconを検知してフォールバック表示に差し替える。
  mermaid.run({ nodes }).then(() => {
    nodes.forEach(n => {
      if (n.querySelector('.error-icon')) n.innerHTML = '<span class="pv-err">図を表示できません</span>';
    });
  }).catch(e => console.warn('mermaid:', e));
}
/* 最大化トグル（2026-09-03）：対話ドックと同じ「1ボタンが最大化⇄縮小に入れ替わる」流儀。
   ボタン自体は pv-toolbar 側にマークアップ済み（renderItem）。ここではハンドラだけ配線する
   （固定ツールバー内にあるためスクロールで流れない＝プレビュー本文と一緒には流れない）。 */
function setupMaxiBtn(pv) {
  const btn = pv.querySelector('.pv-maxi-btn');
  if (!btn) return;
  btn.onclick = (e) => {
    e.stopPropagation();
    const on = pv.classList.toggle('maxi');
    btn.textContent = on ? '⤡' : '⛶';
    btn.title = on ? '元のサイズに戻す' : '画面いっぱいに広げて読む';
    document.body.style.overflow = on ? 'hidden' : '';
  };
}
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const m = document.querySelector('.item-preview.maxi');
  if (!m) return;
  m.classList.remove('maxi');
  document.body.style.overflow = '';
  const b = m.querySelector('.pv-maxi-btn');
  if (b) { b.textContent = '⛶'; b.title = '画面いっぱいに広げて読む'; }
});
/* wikilink クリック：ページ遷移せず、その場の下に対象ノートを展開する（もう一度押すと閉じる）。
   hrefは正規入口の /files?p= だが preventDefault で辿らせず、このページ内で展開する。 */
document.addEventListener('click', (e) => {
  // 固定表示中のタイトル行を押したら、下までスクロールしていてもその場で閉じる。
  const hd = e.target.closest('.wl-nest-hd');
  if (hd) {
    const nest = hd.closest('.wl-nest');
    if (nest) { e.stopPropagation(); nest.remove(); }
    return;
  }
  const a = e.target.closest('a.wl');
  if (!a || !a.dataset.p) return;
  e.preventDefault();
  e.stopPropagation();
  const host = a.closest('p, li, div.wl-nest, .item-preview') || a.parentNode;
  const existing = host.nextElementSibling;
  if (existing && existing.classList && existing.classList.contains('wl-nest')
      && existing.dataset.p === a.dataset.p) {
    existing.remove();
    return;
  }
  const box = document.createElement('div');
  box.className = 'wl-nest';
  box.dataset.p = a.dataset.p;
  box.innerHTML = '<div class="wl-nest-hd" title="クリックで閉じる">✕ ' + esc(a.dataset.p) + '</div><span class="pv-loading">読み込み中…</span>';
  host.after(box);
  loadPreview(box, a.dataset.p, true).then(() => {
    box.insertAdjacentHTML('afterbegin', '<div class="wl-nest-hd" title="クリックで閉じる">✕ ' + esc(a.dataset.p) + '</div>');
  });
});

function openTargetFromQuery() {
  const path = new URLSearchParams(window.location.search).get('p');
  if (!path) return;
  const target = ALL.find(t => t.path === path);
  if (!target) return;

  /* 旧 /review?p= や wikilink から来た時は、保存済みビューの絞り込みに関係なく
     対象ノートへ到達できるよう一時的に対象パスだけを検索する。 */
  FILTERS = {};
  document.getElementById('f-search').value = path;
  document.getElementById('f-group').value = 'none';
  applyFilters();
  const card = [...document.querySelectorAll('.item')].find(el => el.dataset.path === path);
  if (!card) return;
  const hd = card.querySelector('.item-hd');
  if (hd) hd.click();
  requestAnimationFrame(() => card.scrollIntoView({ block:'center' }));
}

/* ===== データ読み込み ===== */
async function init() {
  try {
    const r = await fetch('/files/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    ALL = d.files || [];
    MAP = {};
    ALL.forEach(t => { MAP[t.path || t.virtual_id] = t; });
    document.getElementById('loading').style.display = 'none';
    renderUpdateBadges();
    buildDefaultViews();
    loadCustomViews();
    loadPrefs();
    applyFilters();
    openTargetFromQuery();
  } catch(e) {
    document.getElementById('loading').textContent = '読み込みエラー: ' + e;
  }
}
init();
</script>
</body></html>"""


def render_files_html():
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        PAGE, "files", dashboard_icons.nav_icon_svg("files", 19) + " ファイル")
