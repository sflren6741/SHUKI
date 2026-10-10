#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_board.py — 📋 タスクボード（dashboard_server.py の /board ページ）

2026-10-09: Wall / Quest Log / AI Lane share one board. Status and responsibility
are filters; project progress, selection, sorting and task details use the same rows.
データは /board/data から取得。ステータス変更 → POST /queue（task_status_change）→
次便で orchestrator が .md に反映（サーバーは vault 本体を直接書かない）。
"""
import dashboard_ui  # noqa: E402  (nav_html/bottom_nav_html/PWA_HEAD/RESPONSIVE_CSS を再利用)
import dashboard_chat  # noqa: E402  (💬 全ページ共通の対話ドック)
import dashboard_icons  # noqa: E402  (線アイコンSVG)
import dashboard_facets  # noqa: E402  (🔎 絞り込み・グルーピング・ソートの共有エンジン。2026-08-18 切り出し)
import html
import json  # noqa: E402  (DATA_LABEL の差し込み)
import shuki_profile  # noqa: E402  (Area名・並び順・英字キーの単一情報源。2026-09-27)
import shuki_i18n  # noqa: E402  (現在の言語を見てラベルを選ぶ)
from shuki_i18n import t, tt  # noqa: E402  (表示言語。lang=ja なら素通し)

# 詳細パネル・トーストのJS内絵文字置き換え用（textContent→innerHTML化に伴いSVGをここで解決）
_ICON_CHECK = dashboard_icons.ui_icon_svg("check", 14)
_ICON_CROSS = dashboard_icons.ui_icon_svg("cross", 14)
# 条件チップ・値ピッカー用の小サイズ（2026-08-08）
_ICON_CHECK_S = dashboard_icons.ui_icon_svg("check", 11)
_ICON_CROSS_S = dashboard_icons.ui_icon_svg("cross", 11)
# 保存済みビュー管理パネル用（2026-08-20・/files から横展開）
_ICON_GEAR_S = dashboard_icons.nav_icon_svg("settings", 13)
# 「一手」ボタン用（2026-08-13）。ホームの card-go と同じ線アイコンで揃える（"▶"の文字グリフは使わない）
_ICON_PLAY = dashboard_icons.ui_icon_svg("play", 12)
# 束ね（プロジェクト／概念ノード）グルーピング用アイコン（2026-08-16）。currentColor継承なので
# JS側で色付き<span>に包んで使う（Area用 areaIcon() と同じ流儀）。新規SVGは足さず既存流用。
_ICON_PROJECT = dashboard_icons.ui_icon_svg("doc-link", 15)
_ICON_CONCEPT = dashboard_icons.ui_icon_svg("brain", 15)

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title> タスクボード</title>
<style>
  * { box-sizing:border-box; margin:0; }
  /* デザイントークンは /theme.css（PWA_HEAD 経由で <link> 済み）が単一の正。ここでは持たない
     （2026-07-28 まではここに独自の :root があり、テーマ設定を変えてもこのページだけ古い配色の
     ままだった＝カスケードで後勝ちする inline <style> がテーマを上書きしていたのが原因）。 */
  body { background:var(--bg); color:var(--fg);
    font-family:var(--font-ui);
    /* 100vh はモバイルブラウザでアドレスバー表示中「非表示時の最大高さ」を返すため、
       実際に見える高さより大きく計算され、一番下の bottom-nav(inflow) が画面外に
       押し出されて消える不具合があった（2026-08-18）。100dvh はアドレスバーの出入りに
       動的追従するが、その再計算のタイミングでモバイルブラウザ（特にSafari系）が
       一瞬レイアウトを崩し、今度は逆にメニューが「表示されたり消えたりする」ちらつきの
       原因になった（同日中の追加報告で発覚）。100svh は常にアドレスバー表示時の
       最小の高さに固定され動的に変化しないため、ちらつきが構造的に起きない
       （代償はアドレスバーが引っ込んだ時に下へ数十px余白ができるだけ・実害なし）。
       未対応ブラウザ向けに 100vh → 100dvh → 100svh の順でフォールバックする。 */
    height:100vh; height:100dvh; height:100svh; display:flex; flex-direction:column; overflow:hidden; }
  /* header/.hbtn の基本形は dashboard_ui.RESPONSIVE_CSS が単一の正（2026-08-03 標準化）。
     ここでは board 固有のレイアウト要件（全画面固定・下境界線）だけを追加する。 */
  header { flex-shrink:0; }
  .board-toolbar { flex-shrink:0; padding:10px 16px; border-bottom:1px solid var(--line); }
  .board-toolbar [hidden] { display:none !important; }
  .board-quickbar { display:flex; align-items:center; gap:8px; }
  .board-search { position:relative; flex:1; min-width:0; }
  .board-search > span { position:absolute; width:1px; height:1px; padding:0; overflow:hidden;
    clip-path:inset(50%); white-space:nowrap; }
  .board-search > svg { position:absolute; left:12px; top:50%; transform:translateY(-50%);
    color:var(--muted); pointer-events:none; }
  .board-overview { display:flex; align-items:center; gap:12px; margin-top:6px;
    font-size:.73rem; line-height:1.5; color:var(--muted); }
  #board-view-summary { flex:1; min-width:0; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
  #task-count { flex:none; font-variant-numeric:tabular-nums; }
  #board-settings-toggle { display:inline-flex; align-items:center; justify-content:center; gap:6px; flex:none; }
  #board-settings-toggle[aria-expanded=true] { border-color:var(--accent); color:var(--accent); }
  .board-chevron { display:inline-flex; }
  #board-settings-toggle[aria-expanded=true] .board-chevron { transform:rotate(180deg); }
  #board-filter-count { min-width:20px; padding:1px 4px; border-radius:999px;
    background:var(--accent); color:var(--bg); font-size:.68rem; line-height:1.5; }
  .board-options { margin-top:10px; padding-top:10px; border-top:1px solid var(--line);
    max-height:38svh; overflow-y:auto; scrollbar-gutter:stable; }
  #board-hint { font-size:.78rem; color:var(--muted); line-height:1.5; }
  .board-controls { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
  .board-field { display:flex; flex-direction:column; gap:4px; min-width:0; font-size:.73rem; color:var(--muted); }
  .board-toolbar select, .board-toolbar input[type=search] { min-width:0; width:100%; min-height:44px;
    background:var(--card); border:1px solid var(--line); color:var(--fg); border-radius:8px;
    padding:8px 10px; font-size:.8rem; font-family:inherit; }
  .board-toolbar .board-search input { padding-left:36px; }
  .board-toolbar :focus-visible, #wall-container :focus-visible, #lane-bar :focus-visible {
    outline:2px solid var(--accent); outline-offset:2px; }
  #board-hint { margin-top:8px; }
  .board-tools { display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; }
  .board-tools button { min-height:44px; }
  .board-tools .f-add, .board-tools .fc-t, .board-tools .fc-x { min-height:44px; }
  .board-advanced { min-width:0; flex:1 1 200px; }
  .board-advanced[open] { flex-basis:100%; }
  .board-advanced > summary { cursor:pointer; min-height:44px; display:flex; align-items:center; gap:8px;
    font-size:.77rem; color:var(--muted); }
  .board-advanced > summary::before { content:'+'; font-size:1rem; }
  .board-advanced[open] > summary::before { content:'−'; }
  .advanced-controls { display:flex; flex-wrap:wrap; gap:10px; padding:0 0 10px; }
  .advanced-controls .board-field { min-width:140px; }
  .advanced-filters { display:flex; flex-wrap:wrap; gap:6px; align-items:center; padding-bottom:8px; }
  .board-toolbar .v-row { padding:0 0 10px; border:0; }
  .board-toolbar .v-chip, .board-toolbar .v-add { min-height:44px; }
  .board-secondary { font:inherit; font-size:.76rem; padding:8px 10px; border:1px solid var(--line);
    border-radius:8px; color:var(--fg); background:var(--card); cursor:pointer; min-height:44px; }
  .board-return { margin-top:8px; width:100%; }
  @media (max-width:900px) { .board-controls { grid-template-columns:repeat(2,minmax(0,1fr)); } }
  @media (max-width:600px) { .board-toolbar { padding:10px 12px; } .board-controls { gap:8px; } }
  @media (max-height:500px) and (min-width:600px) {
    .board-toolbar { display:grid; grid-template-columns:minmax(0,1fr) minmax(160px,28%);
      gap:0 16px; padding:8px 12px; }
    .board-overview { margin-top:0; } .board-options { grid-column:1/-1; }
  }
""" + dashboard_facets.engine_css() + dashboard_facets.views_css() + """
  .layout { display:flex; flex:1; min-height:0; position:relative; }
  #wall-wrap { flex:1; display:flex; flex-direction:column; min-height:0; overflow:hidden; }
  #loading { flex:1; display:flex; align-items:center; justify-content:center;
    color:var(--muted); gap:10px; font-size:.9rem; }
  /* minmax の下限に min() を噛ませる（2026-08-08 修正）。素の minmax(300px,1fr) は
     コンテナ内幅が300pxを下回るとトラックが300pxのままはみ出し、狭い端末で横スクロールが
     出ていた（実測: 320px幅で scrollWidth 328 > clientWidth 305 ＝ 23px はみ出し）。
     min(300px,100%) なら「入るなら300px、入らないならコンテナ幅」に落ちる。 */
  #wall-container { flex:1; min-height:0; overflow-y:auto; overflow-x:hidden; padding:14px;
    display:grid; grid-template-columns:repeat(auto-fit, minmax(min(340px, 100%), 1fr)); gap:12px;
    align-content:start; }
  /* グループなし（全件フラット）だけは1カラム。300pxのカードに全件を縦積みすると
     1列目だけが極端に長くなり、右側が空白になるため（2026-08-08）。 */
  #wall-container.flat { grid-template-columns:1fr; }
  /* 2026-08-06: 上辺だけ3pxのArea色を引く「帯」を廃止。丸みのある矩形の一辺だけが
     色付きで浮くのが安っぽく見える（ユーザーのフィードバック）。色はArea アイコンだけが持つ。
     角丸も 12px → 2px。中途半端な丸みがサイバー系のトーンと噛み合わなかった。 */
  .area-card { background:var(--card); border:1px solid var(--line); border-radius:2px;
    padding:11px 13px 13px; display:flex; flex-direction:column;
    transition:border-color .2s; }
  .area-card:hover { border-color:color-mix(in srgb, var(--ac, var(--line)) 45%, var(--line)); }
  /* プロジェクト／概念ノードで束ねた時だけ破線に（2026-08-16）。「点線で囲んで固める」の要望に対応。
     Area別・締切別等の通常グルーピングは実線のまま＝「これは複数タスクを跨ぐ塊」という
     見た目の合図を束ね軸だけに絞る（全グルーピングを破線にすると合図として機能しない）。 */
  .area-card.bundle { border-style:dashed; border-color:color-mix(in srgb, var(--ac, var(--line)) 55%, var(--line)); }
  .ac-hd { display:flex; align-items:center; gap:7px; margin-bottom:8px; }
  .ac-icon { display:inline-flex; flex-shrink:0; }
  /* Area以外のグルーピング（締切・優先度・難易度…）でアイコンの代わりに色を持つドット */
  .ac-dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; margin:0 4px; }
  .ac-name { font-size:.9rem; font-weight:bold; color:var(--fg); }
  .ac-count { margin-left:auto; font-size:.72rem; color:var(--muted); }
  .ac-bar { height:5px; border-radius:2px; background:#ffffff10; overflow:hidden; margin-bottom:10px; }
  .ac-bar-fill { height:100%; border-radius:2px; background:var(--ac, var(--teal));
    transition:width .5s ease; }
  .ac-chips { display:flex; flex-direction:column; gap:5px; }
  .chip { display:flex; align-items:center; gap:7px; padding:7px 8px; border-radius:2px;
    background:var(--bg); border:1px solid var(--line); cursor:pointer; font-size:.78rem;
    transition:transform .12s, border-color .12s; min-height:36px; }
  .chip:hover { transform:translateX(3px); border-color:var(--ac, var(--accent)); }
  .chip.done  { opacity:.5; }
  .chip-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; background:var(--muted); }
  .chip-dot.p-高 { background:var(--danger); box-shadow:0 0 5px var(--danger); }
  .chip-dot.p-中 { background:var(--accent); }
  .chip-dot.p-低 { background:var(--blue); }
  /* min-width でタイトルの下限を確保する（2026-08-06 修正）。以前は flex:1 だけで、
     難易度・成長概念・期限が先に固定幅を取り、装飾の多いタスクだけタイトルが実測21px
     ＝1文字まで潰れていた。カード表面から成長概念チップ(88px・"言ったことを…"と読めない
     省略になっていた)を外し、詳細パネルのクエスト効果に集約したのも同じ理由。 */
  .chip-title { flex:1 1 auto; min-width:7.5em; overflow:hidden; text-overflow:ellipsis;
    white-space:nowrap; color:var(--fg); }
  .chip.done .chip-title { text-decoration:line-through; }
  /* チップ内の強制改行。デスクトップは1行のままなので存在しない扱い（モバイルで有効化） */
  .chip-br { display:none; }
  .chip-star { color:var(--teal); font-size:.72rem; }
  .chip-due { font-size:.68rem; flex-shrink:0; padding:1px 5px; border-radius:2px;
    display:inline-flex; align-items:center; gap:3px; }
  .due-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
  /* 期限状態は意味トークン経由（2026-08-04・生hexの旧配色固定値だったバグを修正。
     以前は #e76f51 等がテーマ刷新後も変わらず残っていた）。絵文字🔴🟠🟡はドットに統一。 */
  .due-over  { background:color-mix(in srgb, var(--danger) 14%, transparent); color:var(--danger); }
  .due-over  .due-dot { background:var(--danger); }
  .due-today { background:color-mix(in srgb, var(--warn) 14%, transparent); color:var(--warn); }
  .due-today .due-dot { background:var(--warn); }
  .due-week  { background:color-mix(in srgb, var(--accent) 12%, transparent); color:var(--accent); }
  .due-week  .due-dot { background:var(--accent); }
  .due-far   { color:var(--muted); }
  /* クエスト効果（難易度・成長概念）— カード表面は最小表示、詳細は下の .dp-quest */
  .chip-diff { font-size:.66rem; color:var(--accent); flex-shrink:0; letter-spacing:.5px; }
  /* .chip-concept はカード表面から撤去（2026-08-06）。定義は詳細パネル側の .dq-concepts が担う。 */
  /* 滞留バッジ（2026-08-06）: 起票日そのものは全チップの title 属性で読める。
     カード表面に出すのは「30日以上ここに居る」タスクだけ＝締切と違う軸の情報を持つものに絞る
     （205件すべてに日付を出すと、目を惹くべき期限バッジが埋もれる。→ UIデザイン原則 §大原則：並べない）。 */
  .chip-age { font-size:.66rem; color:var(--muted); flex-shrink:0;
    background:color-mix(in srgb, var(--muted) 12%, transparent); border-radius:2px; padding:1px 5px; }
  .chip-age.old { color:var(--warn); background:color-mix(in srgb, var(--warn) 12%, transparent); }
  /* 表示プロパティ選択（2026-08-16・Phase1）: 👁 表示ピッカーで選んだプロパティをカード表面に出す。
     同時表示3枠まで（増やしすぎるとタイトルが潰れる教訓・滞留バッジ/成長概念チップの反省を踏襲）。 */
  .chip-extra { font-size:.66rem; color:var(--blue); flex-shrink:0;
    background:color-mix(in srgb, var(--blue) 12%, transparent); border-radius:2px; padding:1px 5px; }
  /* ⏳予約中（2026-08-06）: 押下は ui-queue に溜まるだけで .md の反映は次便（最大3時間後）。
     この差を画面に出さないとリロードで完了が巻き戻ったように見え、記録への信頼が壊れる。 */
  .chip-pend { font-size:.66rem; color:var(--accent); flex-shrink:0;
    background:color-mix(in srgb, var(--accent) 14%, transparent); border-radius:2px; padding:1px 5px; }
  /* フォーカス（2026-08-06）: 「今はこれ」を1件だけ選んで見失わないようにする。
     選択は localStorage（端末ごと）。vault本体には書かない＝押しても .md は変わらない。 */
  .chip.focus { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 10%, transparent);
    box-shadow:0 0 0 1px var(--accent) inset; }
  #focus-band { display:none; align-items:center; gap:10px; margin:0 16px 10px;
    padding:9px 13px; border-radius:2px; border:1px solid var(--accent);
    background:color-mix(in srgb, var(--accent) 9%, transparent); flex-shrink:0; }
  #focus-band.on { display:flex; }
  .fb-lbl { font-size:.66rem; color:var(--accent); letter-spacing:.06em; flex-shrink:0; }
  .fb-title { font-size:.84rem; color:var(--fg); flex:1; overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap; cursor:pointer; }
  .fb-na { font-size:.72rem; color:var(--muted); flex:1; overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap; }
  .fb-clear { background:none; border:1px solid var(--line); color:var(--muted); font-family:inherit;
    border-radius:2px; padding:3px 10px; cursor:pointer; font-size:.72rem; flex-shrink:0; min-height:30px; }
  .fb-clear:hover { color:var(--fg); border-color:var(--accent); }
  /* 完了エフェクト（2026-08-06）: 小さいタスクでも「終わった」感触を返す。
     ポイント・レベルは足さない（ユーザーの指示「これ以上ゲーミフィケーション寄りにしたくない」）。 */
  #burst { position:fixed; inset:0; pointer-events:none; z-index:9998; overflow:hidden; }
  .spark { position:absolute; width:7px; height:7px; border-radius:50%;
    animation:sparkfly .72s cubic-bezier(.2,.7,.3,1) forwards; }
  @keyframes sparkfly {
    0%   { transform:translate(0,0) scale(1); opacity:1; }
    100% { transform:translate(var(--dx), var(--dy)) scale(.2); opacity:0; }
  }
  @media (prefers-reduced-motion: reduce) { .spark { display:none; } }
  .ac-empty { font-size:.76rem; color:var(--muted); padding:6px 2px; }
  .ac-card-empty { opacity:.55; }
  #empty-state { flex:1; display:none; align-items:center; justify-content:center;
    color:var(--muted); font-size:.85rem; text-align:center; padding:20px; }
  /* ===== 詳細パネル（デスクトップ=中央モーダル。2026-09-01改修） =====
     旧: .layout 内のflex子として画面右端に幅300px固定で常設 → 右下固定の対話ドック
     （#result・dashboard_chat.py）と物理的に重なり、幅も狭くて見づらかった（ユーザーのフィードバック）。
     右を取り合う構造そのものをやめ、中央オーバーレイ表示にして構造的に非重複化する。 */
  #detail-overlay { display:none; position:fixed; inset:0; background:#00000066; z-index:1199; }
  #detail-overlay.open { display:block; }
  #detail-panel { display:none; position:fixed; z-index:1200; left:50%; top:50%;
    transform:translate(-50%, -50%); width:min(640px, 90vw); max-height:min(82vh, 800px);
    overflow-y:auto; border:1px solid var(--line); border-radius:8px; padding:16px 20px;
    background:var(--card); box-shadow:0 12px 48px #00000055; }
  #detail-panel.open { display:block; }
  .dp-hd { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
  .dp-title { font-size:.92rem; font-weight:bold; line-height:1.45; margin-bottom:8px; }
  .dp-badges { display:flex; flex-wrap:wrap; gap:4px; margin-bottom:10px; }
  .badge { font-size:.68rem; border-radius:2px; padding:2px 7px;
    background:var(--line); color:var(--muted); }
  /* 生hexの旧配色固定値だったバグを意味トークン化して修正（2026-08-04） */
  .badge.s-in-progress { background:color-mix(in srgb, var(--teal) 18%, transparent); color:var(--teal); }
  .badge.s-on-hold     { background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); }
  .badge.s-done        { background:color-mix(in srgb, var(--teal) 24%, transparent); color:var(--teal); }
  .badge.s-cancelled,.badge.s-archived { background:color-mix(in srgb, var(--muted) 16%, transparent); color:var(--muted); }
  .badge.pend { background:color-mix(in srgb, var(--accent) 16%, transparent); color:var(--accent); }
  .badge.p-高 { background:color-mix(in srgb, var(--danger) 18%, transparent); color:var(--danger); }
  .badge.p-中 { background:color-mix(in srgb, var(--accent) 15%, transparent); color:var(--accent); }
  .dp-field { margin-bottom:10px; }
  .dp-lbl { font-size:.66rem; color:var(--muted); margin-bottom:2px; }
  .dp-val { font-size:.82rem; line-height:1.5; }
  /* ── クエスト効果（難易度・メリデメ・成長概念）board_quests.json 由来。無ければ dq-empty ── */
  .dp-quest { margin:0 0 14px; padding:10px 12px; background:var(--bg); border:1px solid var(--line);
    border-radius:2px; }
  .dp-quest .dq-hd { font-size:.68rem; color:var(--muted); margin-bottom:7px; letter-spacing:.05em; }
  .dq-pills { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:9px; }
  .dq-pill { font-size:.72rem; background:var(--line); color:var(--fg); border-radius:2px; padding:2px 8px; }
  .dq-cols { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:8px; }
  .dq-col { flex:1 1 130px; }
  .dq-col b { font-size:.7rem; display:block; margin-bottom:3px; }
  .dq-col.merit b { color:var(--teal); }
  .dq-col.demerit b { color:var(--red); }
  .dq-col ul { margin:0; padding-left:15px; font-size:.76rem; line-height:1.55; color:var(--fg); }
  .dq-terms { display:flex; gap:12px; flex-wrap:wrap; font-size:.7rem; color:var(--muted); margin-bottom:6px; }
  .dq-terms b { color:var(--fg); }
  .dq-value { font-size:.74rem; color:var(--accent); margin-bottom:6px; }
  .dq-concepts { font-size:.74rem; color:var(--muted); }
  .dq-concepts .cchip { display:inline-block; background:color-mix(in srgb, var(--blue) 13%, transparent);
    color:var(--blue); border-radius:2px; padding:1px 7px; margin:2px 5px 2px 0; }
  .dq-empty { font-size:.78rem; color:var(--muted); font-style:italic; }
  .dp-link { color:var(--blue); text-decoration:none; cursor:pointer; font-size:.79rem; }
  .dp-link:hover { text-decoration:underline; }
  /* ── 本文プレビュー（/files/preview 共用。2026-08-16 新設） ──
     ファイルページの .item-preview と同じ思想の縮小版。カードからタスクファイルの
     全文を読めなかった穴を埋める（メモ機能への投函より）。 */
  .dp-body { font-size:.79rem; line-height:1.6; color:var(--fg); }
  .dp-body h1, .dp-body h2, .dp-body h3, .dp-body h4 { margin:10px 0 5px; color:var(--accent);
    font-size:.86rem; }
  .dp-body h1:first-child, .dp-body h2:first-child, .dp-body h3:first-child,
  .dp-body h4:first-child { margin-top:0; }
  .dp-body p { margin:5px 0; }
  .dp-body ul, .dp-body ol { padding-left:1.2em; margin:5px 0; }
  .dp-body li { margin:2px 0; }
  .dp-body code { background:var(--line); border-radius:4px; padding:0 4px; font-size:.76rem; }
  .dp-body blockquote { border-left:3px solid var(--line); margin:6px 0; padding:2px 0 2px 9px;
    color:var(--muted); }
  .dp-body a.wl { color:var(--accent); text-decoration:none; border-bottom:1px dashed var(--accent); }
  .dp-body .wl-missing { color:var(--muted); border-bottom:1px dotted var(--muted); }
  .dp-body img { max-width:100%; border-radius:6px; margin:6px 0; display:block; }
  .dp-body table { border-collapse:collapse; margin:6px 0; font-size:.76rem; max-width:100%; }
  .dp-body th, .dp-body td { border:1px solid var(--line); padding:3px 6px; text-align:left; }
  .dp-body hr { border:0; border-top:1px solid var(--line); margin:10px 0; }
  .dp-body.pv-loading, .dp-body.pv-err { color:var(--muted); font-size:.78rem; }
  .preview-diff { margin:12px 0 4px; border:1px solid color-mix(in srgb, var(--accent) 30%, var(--line)); border-radius:6px; overflow:hidden; }
  .preview-diff summary { cursor:pointer; padding:6px 9px; color:var(--accent); font-size:.72rem; font-weight:bold; background:color-mix(in srgb, var(--accent) 7%, transparent); }
  .preview-diff-code { padding:5px 0; background:color-mix(in srgb, var(--line) 32%, var(--card)); font: .7rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; overflow-x:auto; }
  .preview-diff-line { padding:0 8px; white-space:pre; }
  .preview-diff-line.added { background:color-mix(in srgb, var(--teal) 16%, transparent); color:var(--teal); }
  .preview-diff-line.removed { background:color-mix(in srgb, var(--danger) 14%, transparent); color:var(--danger); }
  .preview-diff-mark { display:inline-block; width:1.2em; color:var(--muted); user-select:none; }
  .preview-diff-hunk { padding:3px 8px; color:var(--accent); background:color-mix(in srgb, var(--accent) 8%, transparent); }
  /* margin-bottom が無く、直下の .dp-quest（margin-top:0）と隙間ゼロで接していた分の直し（2026-08-13） */
  .dp-acts { margin-top:10px; margin-bottom:14px; display:flex; gap:6px; flex-wrap:wrap; }
  .act-btn { background:none; border:1px solid var(--line); color:var(--muted);
    border-radius:2px; padding:6px 12px; cursor:pointer; font-size:.8rem; font-family:inherit;
    min-height:36px; }
  .act-btn:hover { border-color:var(--accent); color:var(--fg); }
  .act-btn.ok { border-color:var(--teal); color:var(--teal); }
  .act-btn.ok:hover { background:color-mix(in srgb, var(--teal) 13%, transparent); }
  /* 「一手」導線専用（2026-08-13）。他の act-btn（フォーカス切替・ステータス変更）と混色させない。
     パネル内の主行動なので他の act-btn より一段大きく・上下と左右のパディング比を近づけて
     （5px/14px≒1:2.8だと横に間延びした薄いバーに見えた）正方形寄りのしっかりした押しやすさにする。 */
  .act-btn.go { display:inline-flex; align-items:center; gap:6px; border-radius:6px;
    padding:8px 16px; min-height:auto; border-color:var(--teal); color:var(--teal); }
  .act-btn.go:hover { background:color-mix(in srgb, var(--teal) 13%, transparent); }
  .act-btn.go svg { flex-shrink:0; }
  .st-btns { display:flex; flex-wrap:wrap; gap:5px; margin-top:4px; }
  .st-btn { font-size:.74rem; padding:5px 10px; border-radius:2px; min-height:32px; }
  .spin { animation:spin 1.2s linear infinite; display:inline-block; }
  @keyframes spin { to { transform:rotate(360deg); } }
  #toast { position:fixed; bottom:22px; left:50%; transform:translateX(-50%);
    background:var(--card); border:1px solid var(--teal); color:var(--fg);
    padding:7px 18px; border-radius:2px; font-size:.82rem; z-index:9999;
    opacity:0; transition:opacity .25s; pointer-events:none; }
  #toast.show { opacity:1; }
  #toast.err  { border-color:var(--red); }
  /* 「元に戻す」だけはクリックさせる（トースト本体は pointer-events:none のまま）。 */
  #toast .t-undo { pointer-events:auto; margin-left:12px; background:none; font-family:inherit;
    border:1px solid var(--accent); color:var(--accent); border-radius:2px; padding:2px 9px;
    font-size:.76rem; cursor:pointer; min-height:26px; }
  #toast .t-undo:hover { background:color-mix(in srgb, var(--accent) 14%, transparent); }
""" + dashboard_ui.RESPONSIVE_CSS + """
  /* board 固有のモバイル調整: 詳細パネルをボトムシート化・タブバーは inflow なので通常フロー */
  @media (max-width: 700px) {
    .filter-bar input[type=search] { width:100%; flex:1 1 140px; }
    #detail-panel { position:fixed; left:0; right:0; bottom:0; top:auto; width:auto;
      transform:none; max-height:75vh; border-left:none; border-top:1px solid var(--line);
      border-radius:16px 16px 0 0; box-shadow:0 -8px 24px #00000066; z-index:1001; }
    /* オーバーレイはPC中央モーダル専用（2026-09-01）。ボトムシートは背景が透けて見える
       従来仕様のままにする＝モバイルでは出さない。 */
    #detail-overlay { display:none !important; }
    /* 2026-08-08: スマホでタイトルが「…」で切れて中身が読めなかった（実測: 390px幅で
       63件中37件が省略）。1行に収めようとする限り、狭い画面ではタイトルかバッジの
       どちらかが必ず犠牲になる＝「1行」という前提の方を捨てる。
       タイトルは折り返して全文出し、難易度・期限などのバッジは2段目へ落とす。
       min-width を calc(100% - 62px) にしてあるので、dot・▶/🎯 は同じ行に残り、
       バッジ群だけが次の行に回る（横方向のはみ出しはゼロのまま）。 */
    .chip { flex-wrap:wrap; row-gap:5px; align-items:flex-start; }
    .chip-title { flex:1 1 0; min-width:0; white-space:normal;
      overflow:visible; text-overflow:clip; line-height:1.5; }
    .chip-br { display:block; flex-basis:100%; height:0; }
    /* dot・▶/🎯 はタイトル1行目の高さに合わせる（上揃えにしたので中心がずれる） */
    .chip-dot { margin-top:6px; }
    .chip-star { line-height:1.5; }
    /* 狭い画面では余白より本文。カード内の実効幅を左右で8px稼ぐ */
    #wall-container { padding:10px; gap:10px; }
  }

  /* Shared task rows and selection actions in every grouping. */
  .area-card { border-radius:12px; align-self:start; }
  .ac-name { overflow-wrap:anywhere; min-width:0; }
  .ac-count { white-space:nowrap; }
  .ac-bar { height:6px; border-radius:4px; background:var(--line); }
  .ac-bar-fill { background:var(--accent); border-radius:0 4px 4px 0; }
  .chip { align-items:flex-start; gap:4px; border-radius:8px; padding:0; min-height:64px; }
  .chip:hover { transform:none; border-color:var(--accent); }
  .chip.sel { border-color:var(--accent); }
  .task-select { display:flex; align-items:flex-start; justify-content:center; flex:none;
    width:44px; min-height:44px; padding-top:14px; cursor:pointer; }
  .task-select input { width:17px; height:17px; margin:0; accent-color:var(--accent); }
  .task-select:has(input:disabled) { cursor:default; }
  .task-open { flex:1; min-width:0; text-align:left; background:none; border:0;
    color:var(--fg); padding:10px 10px 10px 0; font:inherit; cursor:pointer; min-height:64px; }
  .task-open .chip-title { display:block; min-width:0; white-space:normal; overflow-wrap:anywhere;
    line-height:1.45; font-size:.82rem; }
  .task-meta { display:flex; flex-wrap:wrap; gap:4px 8px; align-items:center; font-size:.68rem;
    color:var(--muted); margin-top:5px; line-height:1.5; }
  .task-owner { display:inline-flex; align-items:center; gap:4px; }
  .task-owner svg { flex:none; }
  .chip.done { opacity:1; }
  .chip.done .chip-title { color:var(--muted); }
  .completed-tasks { margin-top:8px; }
  .completed-tasks > summary { min-height:44px; display:flex; align-items:center; cursor:pointer;
    font-size:.74rem; color:var(--muted); }
  .group-more { width:100%; margin-top:8px; }
  #lane-bar { position:fixed; left:50%; transform:translateX(-50%); bottom:16px; z-index:60;
    display:none; gap:6px; align-items:center; padding:8px 10px; border-radius:12px; background:var(--card);
    border:1px solid var(--line); box-shadow:0 6px 24px rgba(0,0,0,.18); width:max-content;
    max-width:calc(100vw - 24px); flex-wrap:wrap; }
  #lane-bar.on { display:flex; }
  #lane-bar .lb-n { font-size:.78rem; padding:0 4px; }
  #lane-bar button { font:inherit; font-size:.76rem; min-height:44px; padding:8px 10px; border-radius:8px;
    border:1px solid var(--line); background:var(--card); color:var(--fg); cursor:pointer; }
  #lane-bar button:hover:enabled { border-color:var(--accent); }
  #lane-bar button:disabled { opacity:.5; cursor:default; }
  #lane-bar button.go { background:var(--accent); border-color:var(--accent); color:var(--bg); }
  #lane-bar.on ~ .layout #wall-container { padding-bottom:100px; }
  @media (max-width:760px) { #lane-bar { bottom:calc(70px + env(safe-area-inset-bottom)); }
    #lane-bar.on ~ .layout #wall-container { padding-bottom:160px; } }
  @media (prefers-reduced-motion:reduce) { .ac-bar-fill, .chip { transition:none; } }
  @media (forced-colors:active) { .ac-bar-fill { background:Highlight; }
    .chip.sel { border-color:Highlight; } }
</style>
</head>
<body class="no-bn-pad">
<div id="toast"></div>
<div id="lane-bar" role="region" aria-label="選択したタスクの操作" aria-busy="false">
  <span class="lb-n"><span id="lb-count">0</span> <span>件を選択</span></span>
  <button class="go task-done" onclick="applyBulkTaskStatus('done')"><!--SHUKI_ICO:check--> 完了にする</button>
  <button onclick="applyLaneAction('human_only')">自分でやる</button>
  <button id="allow-ai" onclick="applyLaneAction('ai_ok')" title="手動の「自分でやる」指定を解除します。AIができる範囲は再判定されます。">AIを許可</button>
  <button onclick="clearLaneSel()" aria-label="選択を解除">解除</button>
</div>

<!--SHUKI_PAGE_HEADER-->

<section class="board-toolbar" aria-label="タスクボードの操作">
  <div class="board-quickbar">
    <label class="board-search"><span>タスク検索</span>
      """ + dashboard_icons.ui_icon_svg("search", 16) + """
      <input type="search" id="f-search" placeholder="タスク検索…" oninput="applyFilters()">
    </label>
    <button type="button" class="board-secondary" id="board-settings-toggle" aria-label="表示・絞り込み"
      aria-expanded="false" aria-controls="board-options" onclick="toggleBoardSettings()">
      """ + dashboard_icons.ui_icon_svg("filter", 15) + """ <span>表示設定</span>
      <span id="board-filter-count" hidden aria-hidden="true"></span>
      <span class="board-chevron" aria-hidden="true">""" + dashboard_icons.ui_icon_svg("chevron-down", 12) + """</span>
    </button>
  </div>
  <div class="board-overview"><span id="board-view-summary"></span>
    <span id="task-count" role="status" aria-live="polite"></span></div>
  <div class="board-options" id="board-options" hidden>
  <div class="board-controls">
    <label class="board-field">表示するタスク
      <select id="f-status" onchange="setBoardFilter('status', this.value)">
        <option value="open">未完了</option><option value="in-progress">進行中</option>
        <option value="on-hold">保留</option><option value="done">完了</option>
        <option value="all">すべて</option><option value="custom" hidden>カスタム条件</option>
      </select>
    </label>
    <label class="board-field">責任分担
      <select id="f-lane" onchange="setBoardFilter('responsibility', this.value)">
        <option value="all">全員</option><option value="ai">AIで完了まで</option>
        <option value="prep">AIは準備まで</option><option value="human">自分でやる</option>
        <option value="custom" hidden>カスタム条件</option>
      </select>
    </label>
    <label class="board-field">グループ分け
      <select id="f-group" onchange="applyFilters()">
        <option value="area">Area別</option><option value="project">プロジェクト別</option>
        <option value="responsibility">責任分担別</option><option value="none">一覧</option>
        <optgroup label="その他のグループ分け">
          <option value="concept">概念別</option><option value="due">締切別</option>
          <option value="priority">優先度別</option><option value="status">ステータス別</option>
          <option value="difficulty">難易度別</option><option value="progress">進捗度別</option>
          <option value="created">起票月別</option><option value="created_day">起票日別</option>
          <option value="completed_day">完了日別</option><option value="time_bucket">所要時間別</option>
          <option value="efficiency">効率別</option>
        </optgroup>
      </select>
    </label>
    <label class="board-field">並べ替え
      <select id="f-sort" onchange="onSortMetricChange()">
        <option value="pri-due">優先度→締切</option><option value="due">締切</option>
        <option value="created">起票日</option><option value="diff">難易度</option>
        <option value="title">タイトル</option><option value="long">長期効果</option>
        <option value="short">即効性</option><option value="time">所要時間</option>
        <option value="efficiency">効率</option>
      </select>
    </label>
  </div>
  <p id="board-hint">タイトルで詳細、チェックでまとめて操作。</p>
  <div class="board-tools">
    <button class="board-secondary" id="select-visible" onclick="selectVisibleTasks()">表示中を選択</button>
    <button class="board-secondary" onclick="resetBoardFilters()">条件をリセット</button>
    <details class="board-advanced" id="board-advanced">
      <summary id="advanced-summary">詳細設定・保存済みビュー</summary>
      <div class="advanced-controls">
        <label class="board-field">並べ替えの向き
          <select id="f-sort-dir" onchange="applyFilters()"><option value="desc">▼降順</option><option value="asc">▲昇順</option></select>
        </label>
        <label class="board-field">表示密度
          <select id="f-density" onchange="onDensityChange()"><option value="std">標準</option><option value="min">最小</option><option value="full">詳細</option></select>
        </label>
        <button id="f-disp" class="f-add" title="カードに出すプロパティを選ぶ（最大3つ）">プロパティ</button>
      </div>
      <div class="advanced-filters"><div id="f-chips" class="f-chips"></div>
        <button id="f-add" class="f-add">＋ 条件</button></div>
      <div id="v-row" class="v-row"></div>
    </details>
  </div>
  <button type="button" class="board-secondary board-return" onclick="toggleBoardSettings(false)">タスクに戻る</button>
  </div>
</section>
<div id="f-pop"></div>

<div id="burst"></div>
<div id="focus-band">
  <span class="fb-lbl">FOCUS</span>
  <span class="fb-title" id="fb-title"></span>
  <span class="fb-na" id="fb-na"></span>
  <button class="fb-clear" onclick="setFocus(null)">解除</button>
</div>

<div class="layout">
  <div id="wall-wrap">
    <div id="loading"><span class="spin">""" + dashboard_icons.ui_icon_svg("loading", 15) + """</span> データ読み込み中…</div>
    <div id="wall-container" style="display:none;"></div>
    <div id="empty-state">""" + dashboard_icons.ui_icon_svg("search", 15) + """ 条件に一致するタスクがありません</div>
  </div>
  <div id="detail-overlay" onclick="closeDetail()"></div>
  <div id="detail-panel">
    <div class="dp-hd">
      <span style="font-size:.75rem;color:var(--muted);">タスク詳細</span>
      <button class="hbtn" onclick="closeDetail()" style="padding:4px 10px;"><!--SHUKI_ICO:cross--> 閉じる</button>
    </div>
    <div id="dp-title"  class="dp-title"></div>
    <div id="dp-badges" class="dp-badges"></div>
    <div id="dp-acts"   class="dp-acts"></div>
    <div id="dp-fields"></div>
  </div>
</div>
<!--SHUKI_BOTTOM_NAV-->

<script>
/* ===== グローバル状態 ===== */
let ALL = [], MAP = {};
const BOARD_LABEL = __BOARD_LABEL_JSON__;

/* Area配色は /theme.css の --area-* が単一の正（dashboard_theme.AREA_C）。
   以前はここと progress/web/app.js に生hexを複製しており、テーマを変えても追従しなかった。
   ライトテーマでは暗色版が配信されるので、この経路なら自動的に切り替わる（2026-08-06）。 */
const AREA_KEY = """ + json.dumps(shuki_profile.area_key_map(), ensure_ascii=False) + """;
const _areaCss = getComputedStyle(document.documentElement);
const areaColor = (area) =>
  (_areaCss.getPropertyValue('--area-' + (AREA_KEY[area] || '')).trim()) || 'var(--muted)';
/* ウォールの Area 表示順。Area名も並び順も個人の設定なので 99_System/profile.json が正
   （2026-09-27。以前はここ・achievements.py・concept_tree.py に別々の写しがあった）。 */
const AREA_ORDER = """ + json.dumps(shuki_profile.area_names(), ensure_ascii=False) + """;
/* 🌐 データ値の表示ラベル（2026-09-07）。Area名・優先度・長期効果/即効性は
   「画面に出る言葉」であると同時に **vault のデータ値**（CSSセレクタ .badge.p-高・
   グルーピングのキー・AREA_KEY の引き当て）なので、辞書に入れて tt() で置換すると
   データ側まで書き換わって色分けとグルーピングが壊れる。
   そこで **キー（データ値）は日本語のまま、表示の直前だけ dv() で差し替える**。
   中身はサーバー側が t(値, ctx='datavalue') で解決して JSON を差し込む
   ＝lang=ja なら恒等写像（全部同じ値）になり従来と完全に同じ表示になる。 */
const DATA_LABEL = __DATA_LABEL_JSON__;
const dv = (v) => (v && DATA_LABEL[v]) || v;
/* Area10種の線アイコン。dashboard_icons.AREA_PATHS から自動生成する（2026-09-15）。
   以前はここに同じ path を手で複製しており、片方だけ直すと絵が食い違う穴だった
   （🖥 UIデザイン原則（画面編）§9・アイコンの単一情報源）。 */
const AREA_ICON_PATH = """ + json.dumps(dashboard_icons.AREA_PATHS, ensure_ascii=False) + """;
function areaIcon(area, color) {
  const p = AREA_ICON_PATH[area];
  if (!p) return '';
  return '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="' + (color || 'currentColor')
    + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + p + '</svg>';
}
const ST_LABEL = {
  todo:BOARD_LABEL.todo, 'in-progress':BOARD_LABEL.inProgress, 'on-hold':BOARD_LABEL.onHold,
  done:BOARD_LABEL.done, cancelled:BOARD_LABEL.cancelled,
};

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function starStr(n) { return (shukiIcon('star')).repeat(Math.max(0, Math.min(5, +n || 0))); }

/* ===== 🔎 絞り込み（条件チップ・1軸に複数値） =====
   2026-08-08 再設計: Areaセレクト＋ステータスのチェックボックス群＋締切セレクトという
   別々のUIをやめ、「＋条件 → 軸を選ぶ → 値を複数選ぶ」チップ1本に統合した。
   軸の定義は下の AXES がグルーピングと共有＝絞れる粒度と束ね方が構造的にズレない。
   FILTERS[軸] = [選んだキー…]。キーが1つも無い（[]）＝その軸では絞らない。
   チップUI・filteredTasks・groupTasks 本体は dashboard_facets.engine_js() が供給する
   共有エンジン（2026-08-18切り出し・/files ページと共有）。ここでは既定値だけを持つ。 */
let FILTERS = { status: ['todo', 'in-progress', 'on-hold'] };  /* 既定＝手つかず＋動いているもの */

/* One board: status and responsibility are filters, grouping only changes the containers. */
const OPEN_STATUSES = ['todo', 'in-progress', 'on-hold'];
let LANE_SEL = new Set(), BULK_BUSY = false;
function setBoardFilter(axis, value) {
  if (value === 'custom') return;
  FILTERS[axis] = value === 'all' ? [] : axis === 'status' && value === 'open' ? [...OPEN_STATUSES] : [value];
  applyFilters();
}
function resetBoardFilters() {
  FILTERS = {status:[...OPEN_STATUSES]};
  document.getElementById('f-search').value = '';
  clearLaneSel();
  applyFilters();
}
function toggleBoardSettings(show = document.getElementById('board-options').hidden) {
  document.getElementById('board-options').hidden = !show;
  const toggle = document.getElementById('board-settings-toggle');
  toggle.setAttribute('aria-expanded', String(show));
  if (!show) {
    closePop();
    toggle.focus({preventScroll:true});
  }
}
document.querySelector('.board-toolbar').addEventListener('keydown', e => {
  if (e.key === 'Escape' && !document.getElementById('board-options').hidden) {
    if (document.getElementById('f-pop').classList.contains('on')) closePop();
    else toggleBoardSettings(false);
    e.preventDefault();
    e.stopPropagation();
  }
});
function syncBoardControls() {
  const selected = FILTERS.status || [];
  const same = values => selected.length === values.length && values.every(v => selected.includes(v));
  document.getElementById('f-status').value = !selected.length ? 'all' : same(OPEN_STATUSES) ? 'open'
    : selected.length === 1 && ['in-progress','on-hold','done'].includes(selected[0]) ? selected[0] : 'custom';
  const lanes = FILTERS.responsibility || [];
  document.getElementById('f-lane').value = !lanes.length ? 'all' : lanes.length === 1 ? lanes[0] : 'custom';
  const lane = LANE_DEFS.find(d => d.key === document.getElementById('f-lane').value);
  document.getElementById('board-hint').textContent = lane ? lane.title : BOARD_LABEL.hint;
  const extra = Object.keys(FILTERS).filter(k => !['status','responsibility'].includes(k) && AXES[k] && FILTERS[k]?.length).length;
  document.getElementById('advanced-summary').textContent = BOARD_LABEL.advanced + (extra ? ' (' + extra + ')' : '');
  const active = Object.keys(FILTERS).filter(k => AXES[k] && FILTERS[k]?.length
    && !(k === 'status' && same(OPEN_STATUSES))).length;
  const badge = document.getElementById('board-filter-count');
  badge.hidden = !active; badge.textContent = active;
  document.getElementById('board-settings-toggle').setAttribute('aria-label', BOARD_LABEL.viewFilters
    + (active ? ': ' + active + ' ' + BOARD_LABEL.activeFilters : ''));
  const optionLabel = id => document.getElementById(id).selectedOptions[0]?.textContent || '';
  const summary = [optionLabel('f-status'), lane ? optionLabel('f-lane') : '', optionLabel('f-group')].filter(Boolean).join(' · ')
    + (extra ? ' · +' + extra : '');
  const view = document.getElementById('board-view-summary');
  view.textContent = summary; view.title = summary + ' · ' + optionLabel('f-sort');
}

/* 締切までの日数。null = 締切なし */
function dueDays(due) {
  if (!due) return null;
  return Math.round((new Date(due) - new Date(todayStr())) / 86400000);
}
function applyFilters() {
  syncBoardControls();
  savePrefs();
  renderChips();
  renderViews();
  const vis = filteredTasks();
  document.getElementById('task-count').textContent = vis.length + ' ' + BOARD_LABEL.count;
  drawWall(vis);
  updateLaneBar();
}

""" + dashboard_facets.engine_js(_ICON_CHECK_S, _ICON_CROSS_S) + """

/* Keep facet pickers below the quickbar so View remains reachable on short screens. */
const sharedShowPop = showPop;
showPop = (anchor, content) => {
  sharedShowPop(anchor, content);
  const pop = document.getElementById('f-pop');
  const top = Math.max(document.querySelector('.board-overview').getBoundingClientRect().bottom,
    document.querySelector('.board-quickbar').getBoundingClientRect().bottom) + 8;
  const bottom = document.querySelector('.bottom-nav')?.getBoundingClientRect();
  const limit = bottom?.height ? bottom.top - 8 : innerHeight - 8;
  pop.style.maxHeight = Math.max(44, limit - top) + 'px';
  pop.style.top = Math.max(top, Math.min(parseFloat(pop.style.top), limit - pop.offsetHeight)) + 'px';
};

/* ===== ビュー設定の永続化（端末ごと・FOCUS と同じ流儀。vault本体は書かない） ===== */
const PREF_KEY = 'shuki_board_view';
const PREF_IDS = ['f-group', 'f-sort', 'f-sort-dir', 'f-density'];
function loadPrefs() {
  let p = {};
  try { p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch(e) { p = {}; }
  PREF_IDS.forEach(id => {
    const el = document.getElementById(id);
    /* 保存値が今の選択肢に無ければ無視（選択肢を減らした時に空表示にしない） */
    if (el && p[id] != null && [...el.options].some(o => o.value === p[id])) el.value = p[id];
  });
  DENSITY = document.getElementById('f-density').value;
  /* 軸ごと消えている可能性があるので、今も存在する軸だけ復帰させる */
  if (p.filters && typeof p.filters === 'object') {
    const f = {};
    Object.keys(p.filters).forEach(k => { if (AXES[k] && Array.isArray(p.filters[k])) f[k] = p.filters[k]; });
    FILTERS = f;
  }
  if (Array.isArray(p.display))
    DISPLAY_SEL = p.display.filter(k => DISPLAY_DEFS[k]).slice(0, DISPLAY_MAX);
  /* Migrate old modes once; legacy links keep their purpose on the shared board. */
  const urlMode = new URLSearchParams(location.search).get('mode');
  const legacyMode = urlMode || (!p.unified ? p.mode : null);
  if (legacyMode === 'ai') {
    document.getElementById('f-group').value = 'responsibility';
    FILTERS.status = [...OPEN_STATUSES];
  } else if (legacyMode === 'quest') {
    document.getElementById('f-group').value = 'project';
  }

}
function savePrefs() {
  const p = { filters:FILTERS, display:DISPLAY_SEL, unified:true };
  PREF_IDS.forEach(id => { p[id] = document.getElementById(id).value; });
  try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch(e) {}
}

/* ===== データ読み込み ===== */
async function init() {
  try {
    const r = await fetch('/board/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    ALL = (d.tasks || []).filter(t => t.status !== 'archived');
    MAP = {};
    ALL.forEach(t => { MAP[t.id] = t; });
    document.getElementById('loading').style.display = 'none';
    document.getElementById('wall-container').style.display = 'grid';
    buildDefaultViews();
    loadCustomViews();
    loadPrefs();       /* 前回のグループ軸・並び順・締切フィルタを復帰（描画より前） */
    drawFocusBand();   /* 前回選んだフォーカスが残っていれば復帰（消えたタスクなら自動解除） */
    applyFilters();
  } catch(e) {
    document.getElementById('loading').textContent = '読み込みエラー: ' + e;
  }
}

/* ===== 🧱 ウォール ===== */
const PRI_ORDER = { '高':0, '中':1, '低':2 };
function todayStr() { return new Date().toLocaleDateString('sv-SE'); }  // YYYY-MM-DD (local)
function timeStr() { const d = new Date(); return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0'); }  // HH:MM (local)

/* 起票からの経過日数。created が無い旧タスクは null（バッジもツールチップも出さない）。 */
function ageDays(created) {
  if (!created) return null;
  const ms = new Date(todayStr()) - new Date(created);
  const d = Math.floor(ms / 86400000);
  return (d >= 0 && isFinite(d)) ? d : null;
}

/* ===== 🎯 フォーカス（localStorage・端末ごと。vault本体は書かない） ===== */
const FOCUS_KEY = 'shuki_board_focus';
let FOCUS = null;
try { FOCUS = localStorage.getItem(FOCUS_KEY) || null; } catch(e) { FOCUS = null; }

function setFocus(tid) {
  FOCUS = (tid && tid !== FOCUS) ? tid : null;
  try { FOCUS ? localStorage.setItem(FOCUS_KEY, FOCUS) : localStorage.removeItem(FOCUS_KEY); } catch(e) {}
  drawFocusBand();
  applyFilters();
  if (document.getElementById('detail-panel').classList.contains('open') && tid) showDetail(tid);
}

function drawFocusBand() {
  const band = document.getElementById('focus-band');
  const t = FOCUS ? MAP[FOCUS] : null;
  if (!t) { band.className = ''; FOCUS = null; return; }
  band.className = 'on';
  const ttl = document.getElementById('fb-title');
  ttl.textContent = t.title;
  ttl.setAttribute('data-goto', t.id);
  document.getElementById('fb-na').textContent = t.next_action || '';
}

/* ===== ✨ 完了エフェクト（要素の位置から粒が散る。数値・ポイントは足さない） ===== */
function burstAt(x, y) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const con = document.getElementById('burst');
  const colors = ['var(--teal)', 'var(--accent)', 'var(--blue)'];
  for (let i = 0; i < 18; i++) {
    const s = document.createElement('span');
    s.className = 'spark';
    const ang = (Math.PI * 2 * i) / 18 + Math.random() * 0.3;
    const dist = 40 + Math.random() * 70;
    s.style.left = x + 'px';
    s.style.top = y + 'px';
    s.style.background = colors[i % colors.length];
    s.style.setProperty('--dx', Math.cos(ang) * dist + 'px');
    s.style.setProperty('--dy', Math.sin(ang) * dist + 'px');
    s.style.animationDelay = (Math.random() * 0.08) + 's';
    con.appendChild(s);
    setTimeout(() => s.remove(), 900);
  }
}

function dueBadge(due) {
  if (!due) return null;
  const t = todayStr();
  const md = due.slice(5);  // MM-DD
  const dot = '<span class="due-dot"></span>';
  if (due < t)  return { cls:'due-over',  txt: dot + ' 超過' };
  if (due === t) return { cls:'due-today', txt: dot + ' 今日' };
  const wk = new Date(); wk.setDate(wk.getDate() + 7);
  if (due <= wk.toLocaleDateString('sv-SE')) return { cls:'due-week', txt: dot + ' ' + md };
  return { cls:'due-far', txt:md };
}

/* ===== 軸（AXES）— 絞り込みと束ね方の共通定義（2026-08-08） =====
   1軸 = { label, keyOf(タスク)→キー, defs()→[{key,label,color,icon?}] 表示順 }。
   フィルタ（条件チップ）もグルーピングもこの1枚の表から作る＝
   「絞れる粒度」と「束ねる粒度」が構造的にズレない。
   色は意味トークン（--danger/--warn/--accent/--blue/--teal/--muted）だけを使う
   ＝ライト/ダーク両テーマで追従する（生hexを置くと 2026-08-04 の配色バグを再発させる）。 */
function diffOf(t) { return (t.quest && +t.quest.difficulty) || 0; }

/* ===== 👁 表示プロパティ（2026-08-16・Phase1） =====
   board_quests.json の long_term/short_term/time_bucket_min/difficulty から、
   カード表面に追加で出せる4候補を定義。stamina は141件中134件が「低」で
   情報量ゼロと実測済みのため候補から除外（タスク本文の前提調査どおり）。 */
const LONG_TERM_ORDER  = { '極小':1, '小':2, '中':3, '大':4, '特大':5 };
/* キーは board_quests.json のデータ値。'なし' だけ unicode エスケープで書くのは、
   en.json に「なし→None」が入っており tt() がこのキーまで書き換えて
   52件の short_term:'なし' が引けなくなっていたため（2026-09-07 修正）。 */
const SHORT_TERM_ORDER = { '\\u306a\\u3057':0, '低':1, '中':2, '高':3 };
/* 効率スコア = 2×長期効果 − 難易度（2026-08-17）。旧式は lt/difficulty の割り算だった。

   なぜ割り算をやめたか: レベルは線形ではなく幾何級数だから。難易度は time_bucket_min の実測で
   d1 43分→d2 105分→d3 367分→d4 7,445分→d5 43,200分（n=73・1000倍のレンジ）とはっきり凸型。
   幾何級数どうしの比は log 空間では引き算になるので、ordinal をそのまま割ると
   スケールを取り違え、効果の大きいタスクが不当に沈む（AWS SAA 大/d4 が「小/d1 の雑務」に負けていた）。

   係数について: 順位に効くのは効果と難易度の「log傾きの比 r」だけで、1レベル何倍かの絶対値ではない。
   その r を金額アンカーから 1.08 と見積もったが、この推定は弱い（金額を持つのは142件中11件=9%、
   しかも生成プロンプトが「測れる効果＝お金・時間・健康のみ value_note に書く／人間関係・自己理解・意味は
   long_term に定性で振り切る」と指示しているため、上のレベルほど金額を持つタスクが選択的に脱落する）。
   ただし感度分析では r=0.7〜1.3 で順位が完全一致（Kendall tau=1.000）、r=0.5/2.0 でも tau≧0.93。
   対して旧式（割り算）との差は tau=0.663 と桁違いに大きい。つまりパラメータの不確かさより
   割り算→引き算の構造修正のほうが5倍効いており、r=1 の採用は安全側。
   効果の重み2も w=1.5〜2.5 が tau=1.000 の平坦域で、その中央。

   即効性(short_term)は定量アンカーが取れず76%が「なし/低」に偏るためこの式には入れない
   （独立した「即効性が高い順」ソートで見る）。 */
function efficiencyOf(t) {
  const q = t.quest;
  if (!q || !q.long_term || !q.difficulty) return null;
  const lt = LONG_TERM_ORDER[q.long_term];
  if (!lt) return null;
  return 2 * lt - (+q.difficulty);
}
/* 閾値は実測142件のスコア分布の三分位（33%点=2 / 67%点=4）。 */
function efficiencyLabel(t) {
  const e = efficiencyOf(t);
  if (e === null) return null;
  if (e >= 4) return '高効率';
  if (e >= 3) return '中効率';
  return '低効率';
}
/* ソート専用の数値化。quest未生成タスクは常に末尾へ回す（-1 / Infinity）。 */
function longTermOf(t)  { return (t.quest && t.quest.long_term in LONG_TERM_ORDER) ? LONG_TERM_ORDER[t.quest.long_term] : -1; }
function shortTermOf(t) { return (t.quest && t.quest.short_term in SHORT_TERM_ORDER) ? SHORT_TERM_ORDER[t.quest.short_term] : -1; }
function timeBucketOf(t) { const v = t.quest && t.quest.time_bucket_min; return (v && v > 0) ? v : Infinity; }
/* 効率ソートはスコア（整数0〜8の実測レンジ）の降順。同点の中だけ所要時間の短い順でタイブレークする。
   時間をスコアの分母に混ぜないのは、海外転職のような長期不確実タスクの time_bucket_min が実測でなく
   仮の見積もりで、分母に使うと効果が一番大きいタスクを不当に潰してしまうため（2026-08-17）。
   quest未生成タスクは -999 で常に末尾へ回す（-Infinity は同士の減算が NaN になり比較関数が壊れる）。 */
function efficiencyForSort(t) { const e = efficiencyOf(t); return e === null ? -999 : e; }
const DISPLAY_DEFS = {
  time:       { label:'所要時間', text:t => (t.quest && t.quest.time_cost) || null },
  long_term:  { label:'長期効果', text:t => dv(t.quest && t.quest.long_term) || null },
  short_term: { label:'即効性',   text:t => dv(t.quest && t.quest.short_term) || null },
  efficiency: { label:'効率',     text:efficiencyLabel },
};
const DISPLAY_MAX = 3;
let DISPLAY_SEL = [];        /* 選択中のプロパティキー（最大3・順不同） */
let DENSITY = 'std';         /* std=標準 / min=最小（難易度★・滞留バッジも隠す） / full=詳細 */

function onDensityChange() {
  DENSITY = document.getElementById('f-density').value;
  if (DENSITY === 'full' && !DISPLAY_SEL.length)
    DISPLAY_SEL = ['time', 'long_term', 'short_term'];   /* 詳細プリセット＝主要3つを自動選択 */
  if (DENSITY === 'min') DISPLAY_SEL = [];                /* 最小は追加プロパティも出さない */
  closePop();   /* プロパティピッカーを開いたまま密度を変えると選択チェックが古いまま残るため */
  savePrefs();
  applyFilters();
}
function openDisplayPicker(anchor) {
  const items = Object.keys(DISPLAY_DEFS).map(k => {
    const on = DISPLAY_SEL.includes(k);
    return '<div class="fp-item' + (on ? ' on' : '') + '" data-togd="' + k + '">'
      + '<span class="fp-box">""" + _ICON_CHECK_S + """</span><span>' + esc(DISPLAY_DEFS[k].label) + '</span></div>';
  }).join('');
  showPop(anchor, '<div class="fp-hd">表示するプロパティ（最大' + DISPLAY_MAX + 'つ）</div>' + items);
}
document.addEventListener('click', e => {
  const d = e.target.closest('#f-disp');
  if (d) { openDisplayPicker(d); return; }
  const t = e.target.closest('[data-togd]');
  if (t) {
    const k = t.dataset.togd;
    const i = DISPLAY_SEL.indexOf(k);
    if (i >= 0) DISPLAY_SEL.splice(i, 1);
    else if (DISPLAY_SEL.length < DISPLAY_MAX) DISPLAY_SEL.push(k);
    else { showToast('表示は同時に' + DISPLAY_MAX + 'つまでです。どれかを外してから選んでください'); return; }
    savePrefs();
    applyFilters();
    openDisplayPicker(document.getElementById('f-disp'));
  }
});

const DUE_DEFS = [
  { key:'over',  label:'期限切れ', color:'var(--danger)' },
  { key:'today', label:'今日',     color:'var(--warn)' },
  { key:'week',  label:'7日以内',  color:'var(--accent)' },
  { key:'month', label:'30日以内', color:'var(--blue)' },
  { key:'later', label:'それ以降', color:'var(--teal)' },
  { key:'none',  label:'締切なし', color:'var(--muted)' },
];
function dueKey(t) {
  const d = dueDays(t.due);
  if (d === null) return 'none';
  if (d < 0)   return 'over';
  if (d === 0) return 'today';
  if (d <= 7)  return 'week';
  if (d <= 30) return 'month';
  return 'later';
}
const PRI_DEFS = [
  { key:'高', label:'高優先', color:'var(--danger)' },
  { key:'中', label:'中優先', color:'var(--accent)' },
  { key:'低', label:'低優先', color:'var(--blue)' },
  { key:'(未設定)', label:'優先度なし', color:'var(--muted)' },
];
/* 優先度バッジのラベルは PRI_DEFS が単一の正。'高'+'優先' と連結すると en で
   'High'+'priority' になって語間が詰まるため、丸ごとラベルを引く（2026-09-07）。 */
const priLabel = (p) => (PRI_DEFS.find(d => d.key === p) || {}).label || p;
const ST_DEFS = [
  { key:'in-progress', label:BOARD_LABEL.inProgress,     color:'var(--teal)' },
  { key:'todo',        label:BOARD_LABEL.todo,          color:'var(--accent)' },
  { key:'on-hold',     label:BOARD_LABEL.onHold,       color:'var(--warn)' },
  { key:'done',        label:BOARD_LABEL.done,       color:'var(--teal)' },
  { key:'cancelled',   label:BOARD_LABEL.cancelled, color:'var(--muted)' },
  { key:'archived',    label:'archived',      color:'var(--muted)' },
];
const DIFF_COLOR = { 5:'var(--danger)', 4:'var(--warn)', 3:'var(--accent)', 2:'var(--blue)', 1:'var(--teal)' };
const DIFF_DEFS = [5,4,3,2,1]
  .map(n => ({ key:String(n), label:starStr(n), color:DIFF_COLOR[n] }))
  .concat([{ key:'0', label:'難易度なし', color:'var(--muted)' }]);

/* Area と起票月は vault の中身で増減するので defs は都度組み立てる */
function areaDefs() {
  const keys = [...AREA_ORDER];   /* 人生10領域 → 余り（未設定など） */
  ALL.forEach(t => { const a = t.area || '(未設定)'; if (!keys.includes(a)) keys.push(a); });
  return keys.map(a => ({ key:a, label:dv(a), color:areaColor(a), icon:areaIcon(a, areaColor(a)) }));
}
/* プロジェクト／概念ノードへの束ね（2026-08-16）。parent: を辿って行き着いた先が
   collect_board_data() 側で解決済み（tasks-by-tasks の2段階チェーンも1段に畳んである）。
   束ねられないタスク（parent_kind:'none'）は最後に「束ね元なし」でまとめて出す。 */
function bundleKey(t) { return !['project','concept'].includes(t.parent_kind) || !t.project_id ? 'none' : (t.parent_kind + ':' + t.project_id); }
function bundleIcon(kind, color) {
  const svg = kind === 'concept' ? '""" + _ICON_CONCEPT + """' : '""" + _ICON_PROJECT + """';
  return '<span style="display:inline-flex;color:' + color + '">' + svg + '</span>';
}
function projectDefs() {
  const n = {};   /* key -> { label, kind, count } */
  ALL.forEach(t => {
    const k = bundleKey(t);
    if (!n[k]) n[k] = { label: k === 'none' ? BOARD_LABEL.noProject : t.project_title, kind: t.parent_kind, count: 0 };
    n[k].count++;
  });
  const keys = Object.keys(n).filter(k => k !== 'none');
  keys.sort((a, b) => n[b].count - n[a].count);   /* 件数の多い塊から（実績優先の動的順） */
  if (n['none']) keys.push('none');
  return keys.map(k => {
    const e = n[k];
    const color = k === 'none' ? 'var(--muted)' : (e.kind === 'concept' ? 'var(--blue)' : 'var(--accent)');
    return { key:k, label:e.label, color, icon: k === 'none' ? '' : bundleIcon(e.kind, color) };
  });
}
function createdDefs() {
  return [...new Set(ALL.map(t => (t.created ? t.created.slice(0, 7) : '(不明)')))]
    /* 新しい月から。created が無い旧タスクは末尾に置く */
    .sort((a, b) => (a === '(不明)') - (b === '(不明)') || b.localeCompare(a))
    .map(k => ({
      key:k,
      label: k === '(不明)' ? '起票日なし' : k.slice(0,4) + '年' + (+k.slice(5,7)) + '月',
      color: k === '(不明)' ? 'var(--muted)' : 'var(--blue)',
    }));
}
/* 起票「日」単位の束ね（2026-08-25）。月別だと粒度が粗すぎる時用に日別を別軸として追加。
   同日起票がまとまるタスク（一括起票・週次バッチ生成等）を見分けたい場面向け。 */
function createdDayDefs() {
  return [...new Set(ALL.map(t => t.created || '(不明)'))]
    .sort((a, b) => (a === '(不明)') - (b === '(不明)') || b.localeCompare(a))
    .map(k => ({
      key:k,
      label: k === '(不明)' ? '起票日なし' : k,
      color: k === '(不明)' ? 'var(--muted)' : 'var(--blue)',
    }));
}

/* ===== 新しいグルーピング軸（2026-08-25）===== */

/* 完了日別（end_actual）。done になった日付で分類。
   大昔のタスク以外は基本 null だが、task_snapshot.py が 2026-07-28 以降に
   status→done の変更を検知して自動記入するため、最近のタスクから増えていく。 */
function completedDayDefs() {
  const keys = [...new Set(ALL.map(t => t.end_actual || null))]
    .filter(k => k !== null)
    .sort((a, b) => b.localeCompare(a));  /* 新しい日から */
  const today = todayStr();
  return keys.map(k => ({
    key:k,
    label: k === today ? '今日完了' : k,
    color: 'var(--teal)',
  })).concat([
    { key:'null', label:'未完了', color:'var(--muted)' }
  ]);
}
function completedKey(t) { return t.end_actual || 'null'; }

/* 所要時間別（quest.time_bucket_min）。見積もり分の値で区間に分類。
   quest 未生成のタスクは 'none' へ。 */
const TIME_BUCKETS = [
  { key:'0-30', label:'30分以下', min:0, max:30, color:'var(--teal)' },
  { key:'30-60', label:'1時間', min:30, max:60, color:'var(--blue)' },
  { key:'60-240', label:'2-4時間', min:60, max:240, color:'var(--accent)' },
  { key:'240+', label:'8時間以上', min:240, max:Infinity, color:'var(--warn)' },
];
function timeBucketKey(t) {
  const m = t.quest && t.quest.time_bucket_min;
  if (!m || m <= 0) return 'none';
  for (const b of TIME_BUCKETS) {
    if (m >= b.min && m < b.max) return b.key;
  }
  return '240+';
}
function timeBucketDefs() {
  return TIME_BUCKETS.concat([
    { key:'none', label:'見積なし', color:'var(--muted)' }
  ]);
}

/* 効率別（長期効果 × 2 − 難易度）。quest 未生成のタスクは 'none' へ。 */
function efficiencyKey(t) {
  const e = efficiencyOf(t);
  if (e === null) return 'none';
  if (e >= 4) return 'high';
  if (e >= 3) return 'mid';
  return 'low';
}
function efficiencyDefs() {
  return [
    { key:'high', label:'高効率', color:'var(--teal)' },
    { key:'mid', label:'中効率', color:'var(--accent)' },
    { key:'low', label:'低効率', color:'var(--warn)' },
    { key:'none', label:'未評価', color:'var(--muted)' }
  ];
}

/* 概念ノード別。parent_kind==='concept' なタスクを概念 ID で分類。
   concept: 接頭辞をつけて他の bundle と区別。概念が無いタスクは 'none'。 */
function conceptKey(t) {
  return t.parent_kind === 'concept' ? ('concept:' + t.project_id) : 'none';
}
function conceptDefs() {
  const n = {};
  ALL.forEach(t => {
    if (t.parent_kind === 'concept') {
      const k = 'concept:' + t.project_id;
      if (!n[k]) n[k] = { label: t.project_title, count: 0 };
      n[k].count++;
    }
  });
  const keys = Object.keys(n);
  keys.sort((a, b) => n[b].count - n[a].count);
  return keys.map(k => ({
    key:k,
    label: n[k].label,
    color: 'var(--blue)',
    icon: '<span style="display:inline-flex;color:var(--blue)">""" + _ICON_CONCEPT + """</span>',
  })).concat([
    { key:'none', label:'概念なし', color:'var(--muted)' }
  ]);
}

/* 進捗度別は軸ではなく drawWall() で特別に計算する（AXES に入れない）。
   プロジェクトごとに done/total を計算し、完了率で並べる。
   仕組みは進捗バーを出す時と同じ（groupTasks() で既に done/total を計算済み）。 */

const AXES = {
  area:         { label:'Area',       keyOf:t => t.area || '(未設定)',     defs:areaDefs },
  responsibility: { label:'責任分担', keyOf:responsibilityKey, defs:() => LANE_DEFS },
  project:      { label:'プロジェクト', keyOf:bundleKey,                    defs:projectDefs },
  concept:      { label:'概念ノード', keyOf:conceptKey,                    defs:conceptDefs },
  status:       { label:'ステータス', keyOf:t => t.status || '(未設定)',   defs:() => ST_DEFS },
  priority:     { label:'優先度',     keyOf:t => t.priority || '(未設定)', defs:() => PRI_DEFS },
  difficulty:   { label:'難易度',     keyOf:t => String(diffOf(t)),        defs:() => DIFF_DEFS },
  due:          { label:'締切',       keyOf:dueKey,                        defs:() => DUE_DEFS },
  created:      { label:'起票月',     keyOf:t => (t.created ? t.created.slice(0, 7) : '(不明)'),
                  defs:createdDefs },
  created_day:  { label:'起票日',     keyOf:t => t.created || '(不明)',    defs:createdDayDefs },
  completed_day:{ label:'完了日',     keyOf:completedKey,                  defs:completedDayDefs },
  time_bucket:  { label:'所要時間',   keyOf:timeBucketKey,                 defs:timeBucketDefs },
  efficiency:   { label:'効率',       keyOf:efficiencyKey,                 defs:efficiencyDefs },
};

/* groupTasks は dashboard_facets.engine_js() 側にある（AXES.area へのフォールバックは
   Object.values(AXES)[0] に一般化・area が先頭キーなので挙動は従来どおり）。 */

/* ===== 保存済みビュー（/files から横展開・dashboard_facets.py 共有部品・2026-08-20） =====
   組み込みビューは既存の AXES/DUE_DEFS 等をそのまま使う（ハードコードした値の重複を避ける）。
   ページの初期表示（FILTERS の既定値・459行目）はこの一覧と独立しており、ここを増やしても
   初期状態は変わらない（ビューは「クイックショートカット」の選択肢を増やすだけ）。 */
let DEFAULT_VIEWS = [];
function buildDefaultViews() {
  DEFAULT_VIEWS = [
    { id:'v-all', name:'すべて', builtin:true,
      state:{ filters:{}, group:'area', sort:'pri-due', sortDir:'desc' } },
    { id:'v-active', name:'進行中＋todo', builtin:true,
      state:{ filters:{ status:['todo', 'in-progress', 'on-hold'] }, group:'area', sort:'pri-due', sortDir:'desc' } },
    { id:'v-overdue', name:'期限切れ', builtin:true,
      state:{ filters:{ due:['over'], status:['todo', 'in-progress', 'on-hold'] }, group:'none', sort:'due', sortDir:'asc' } },
    { id:'v-today', name:'今日締切', builtin:true,
      state:{ filters:{ due:['today'], status:['todo', 'in-progress', 'on-hold'] }, group:'none', sort:'pri-due', sortDir:'desc' } },
    { id:'v-highpri', name:'優先度高', builtin:true,
      state:{ filters:{ priority:['高'], status:['todo', 'in-progress', 'on-hold'] }, group:'due', sort:'due', sortDir:'asc' } },
  ];
}
""" + dashboard_facets.views_js("shuki_board_custom_views", _ICON_CROSS_S, _ICON_CHECK_S, _ICON_GEAR_S) + """

/* ===== 並び順（グループ内のチップ） =====
   2026-08-18: 軸(f-sort)と向き(f-sort-dir、昇順/降順)を分離。従来10択のうち実際にペアだった
   のは起票日(created-desc/asc)のみで、他5軸(難易度/長期効果/即効性/所要時間/効率)は片方向しか
   無かった。向きトグルを足すことで軸を9つに減らしつつ、全軸を両方向対応にする。
   クエスト未生成タスクを末尾に固定する既存仕様（長期/即効性/所要時間/効率）は向きに関わらず維持する
   （missingLast=trueの軸だけ hasFn で「無い方を必ず末尾」を先に判定してから向きを掛ける）。 */
const PRI_CMP = (x, y) => (PRI_ORDER[x.priority] ?? 3) - (PRI_ORDER[y.priority] ?? 3);
const DUE_CMP = (x, y) => (x.due || '9999').localeCompare(y.due || '9999');
/* dirSign/metricCmp は dashboard_facets.engine_js() 側にある（優先度/締切/起票日/難易度/タイトルは
   hasFn 無しで済むためそのまま。長期効果/即効性/所要時間/効率は下で hasFn を渡す）。 */
const priWeight = t => ({ '高':3, '中':2, '低':1 })[t.priority] ?? 0;
const SORT_METRICS = {
  'pri-due': { label:'優先度→締切', defaultDir:'desc',
    cmp: (x, y, dir) => dirSign(dir) * (priWeight(x) - priWeight(y)) || DUE_CMP(x, y) },
  'due': { label:'締切', defaultDir:'asc',
    cmp: (x, y, dir) => (x.due && y.due ? dirSign(dir) * DUE_CMP(x, y) : (x.due ? -1 : y.due ? 1 : 0)) || PRI_CMP(x, y) },
  'created': { label:'起票日', defaultDir:'desc',
    cmp: (x, y, dir) => dirSign(dir) * (x.created || '0000').localeCompare(y.created || '0000') || DUE_CMP(x, y) },
  'diff': { label:'難易度', defaultDir:'desc',
    cmp: (x, y, dir) => dirSign(dir) * (diffOf(x) - diffOf(y)) || DUE_CMP(x, y) },
  'title': { label:'タイトル', defaultDir:'asc',
    cmp: (x, y, dir) => dirSign(dir) * x.title.localeCompare(y.title, 'ja') },
  /* 2026-08-16・Phase1: クエスト効果ベースの追加ソート軸。quest未生成タスクは常に末尾へ回る。 */
  'long': { label:'長期効果', defaultDir:'desc',
    cmp: (x, y, dir) => metricCmp(longTermOf, t => longTermOf(t) >= 0)(x, y, dir) || DUE_CMP(x, y) },
  'short': { label:'即効性', defaultDir:'desc',
    cmp: (x, y, dir) => metricCmp(shortTermOf, t => shortTermOf(t) >= 0)(x, y, dir) || DUE_CMP(x, y) },
  'time': { label:'所要時間', defaultDir:'asc',
    cmp: (x, y, dir) => metricCmp(timeBucketOf, t => timeBucketOf(t) !== Infinity)(x, y, dir) || DUE_CMP(x, y) },
  'efficiency': { label:'効率', defaultDir:'desc',
    cmp: (x, y, dir) => metricCmp(efficiencyForSort, t => efficiencyOf(t) !== null)(x, y, dir) || timeBucketOf(x) - timeBucketOf(y) || DUE_CMP(x, y) },
};
function onSortMetricChange() {
  const m = SORT_METRICS[document.getElementById('f-sort').value];
  if (m) document.getElementById('f-sort-dir').value = m.defaultDir;
  applyFilters();
  savePrefs();
}

const GROUP_LIMIT = 8;
const EXPANDED_GROUPS = new Set();
const LANE_DEFS = [
  {key:'ai', label:BOARD_LABEL.ai, color:'var(--muted)',
    title:BOARD_LABEL.aiHint},
  {key:'prep', label:BOARD_LABEL.prep, color:'var(--muted)',
    title:BOARD_LABEL.prepHint},
  {key:'human', label:BOARD_LABEL.human, color:'var(--muted)',
    title:BOARD_LABEL.humanHint},
];
function responsibilityKey(t) {
  return t.human_only ? 'human' : LANE_DEFS.some(d => d.key === t.ai_lane) ? t.ai_lane : 'human';
}
function taskRowHtml(t) {
  const done = t.status === 'done', active = OPEN_STATUSES.includes(t.status);
  const lane = LANE_DEFS.find(d => d.key === responsibilityKey(t));
  const status = ST_DEFS.find(d => d.key === t.status)?.label || t.status;
  const due = !done ? dueBadge(t.due) : null;
  const extras = DISPLAY_SEL.map(k => {
    const value = DISPLAY_DEFS[k].text(t);
    return value ? '<span class="chip-extra">' + esc(DISPLAY_DEFS[k].label) + ': ' + esc(value) + '</span>' : '';
  }).join('');
  return '<div class="chip' + (done ? ' done' : '') + (LANE_SEL.has(t.id) ? ' sel' : '')
    + (t.id === FOCUS ? ' focus' : '') + '" data-task-row="' + esc(t.id) + '" data-goto="' + esc(t.id) + '">'
    + '<label class="task-select" title="まとめて操作するタスクを選択">'
    + '<input type="checkbox" data-select-task="' + esc(t.id) + '" aria-label="' + esc(t.title) + '"'
    + (LANE_SEL.has(t.id) || done ? ' checked' : '') + (!active ? ' disabled' : '') + '></label>'
    + '<button type="button" class="task-open" data-goto="' + esc(t.id) + '">'
    + '<span class="chip-title">' + (t.id === FOCUS ? (shukiIcon('target') + ' ') : '') + esc(t.title) + '</span>'
    + '<span class="task-meta"><span>' + esc(status) + '</span>'
    + (!done ? '<span class="task-owner" title="' + esc(t.ai_reason || lane.title) + '">' + esc(lane.label) + '</span>' : '')
    + (t.human_only ? ('<span title="手動で自分の担当に指定">' + shukiIcon('lock') + '</span>') : '')
    + (due ? '<span class="chip-due ' + due.cls + '">' + due.txt + '</span>' : '')
    + (t.pending || t.ai_pending ? '<span class="chip-pend">' + esc(BOARD_LABEL.pending) + '</span>' : '')
    + (t.start && t.start.slice(0,10) > todayStr() ? '<span>' + esc(BOARD_LABEL.starts) + ' (' + esc(t.start.slice(0,10)) + ')</span>' : '')
    + (t.quest && DENSITY !== 'min' ? '<span class="chip-diff" title="難易度 ' + t.quest.difficulty + '/5">' + starStr(t.quest.difficulty) + '</span>' : '')
    + (!done && t.priority === '高' ? '<span class="chip-due due-over">' + esc(BOARD_LABEL.highPriority) + '</span>' : '')
    + extras + '</span></button></div>';
}
function drawWall(tasks) {
  const con = document.getElementById('wall-container'), empty = document.getElementById('empty-state');
  con.innerHTML = '';
  if (!tasks.length) { con.style.display = 'none'; empty.style.display = 'flex'; return; }
  con.style.display = 'grid'; empty.style.display = 'none';
  const gk = document.getElementById('f-group').value;
  con.classList.toggle('flat', gk === 'none');
  const scope = ALL.filter(t => ['todo','in-progress','on-hold','done'].includes(t.status)
    && Object.keys(FILTERS).every(k => k === 'status' || !AXES[k] || !FILTERS[k]?.length || axisOn(k,t)));
  const progress = Object.fromEntries(groupTasks(gk === 'progress' ? 'project' : gk, scope)
    .map(g => [g.key, {done:g.items.filter(t => t.status === 'done'), total:g.items.length}]));
  const metric = SORT_METRICS[document.getElementById('f-sort').value] || SORT_METRICS['pri-due'];
  const dir = document.getElementById('f-sort-dir').value || metric.defaultDir;
  const cmp = (a,b) => (a.status === 'done') - (b.status === 'done') || metric.cmp(a,b,dir);
  let groups = groupTasks(gk === 'progress' ? 'project' : gk, tasks);
  if (gk === 'progress') groups.sort((a,b) => {
    const pa = progress[a.key], pb = progress[b.key];
    return dirSign(dir) * ((pa?.done.length || 0) / (pa?.total || 1) - (pb?.done.length || 0) / (pb?.total || 1));
  });
  groups.forEach(g => {
    const rows = g.items.slice().sort(cmp), p = progress[g.key];
    const showProgress = ['area','project','concept','progress'].includes(gk) && p?.total;
    const pct = p?.total ? Math.round(p.done.length / p.total * 100) : 0;
    const card = document.createElement('div');
    card.className = 'area-card'; card.style.setProperty('--ac', g.color);
    const key = gk + ':' + g.key;
    const expanded = EXPANDED_GROUPS.has(key);
    let h = '<div class="ac-hd">' + (g.icon ? '<span class="ac-icon">' + g.icon + '</span>' : '')
      + '<span class="ac-name">' + esc(g.label) + '</span><span class="ac-count">' + rows.length + ' ' + esc(BOARD_LABEL.count) + '</span></div>';
    if (showProgress) h += '<div class="ac-count" style="margin:0 0 6px">' + p.done.length + ' / ' + p.total + ' ' + esc(BOARD_LABEL.done) + '</div>'
      + '<div class="ac-bar" role="progressbar" aria-label="' + esc(g.label) + '" aria-valuemin="0" aria-valuemax="' + p.total
      + '" aria-valuenow="' + p.done.length + '" title="' + p.done.length + ' / ' + p.total + '">'
      + '<div class="ac-bar-fill" style="width:' + pct + '%"></div></div>';
    h += '<div class="ac-chips">' + rows.slice(0,expanded ? rows.length : GROUP_LIMIT).map(taskRowHtml).join('') + '</div>';
    card.innerHTML = h;
    if (rows.length > GROUP_LIMIT) {
      const more = document.createElement('button'); more.type = 'button'; more.className = 'board-secondary group-more';
      more.textContent = expanded ? BOARD_LABEL.fewer : BOARD_LABEL.more + ' (' + rows.length + ')';
      more.setAttribute('aria-expanded', String(expanded));
      more.onclick = () => { expanded ? EXPANDED_GROUPS.delete(key) : EXPANDED_GROUPS.add(key); applyFilters(); };
      card.appendChild(more);
    }
    // Completed project tasks use the same rows. No hidden status-filter exception.
    if (['project','concept','progress'].includes(gk) && p?.done.length && !rows.some(t => t.status === 'done')) {
      const completed = p.done.filter(t => !document.getElementById('f-search').value.trim()
        || t.title.toLowerCase().includes(document.getElementById('f-search').value.trim().toLowerCase()));
      if (completed.length) {
        const details = document.createElement('details'); details.className = 'completed-tasks';
        details.innerHTML = '<summary>' + esc(BOARD_LABEL.completed) + ' (' + completed.length + ')</summary><div class="ac-chips">'
          + completed.map(taskRowHtml).join('') + '</div>';
        card.appendChild(details);
      }
    }
    con.appendChild(card);
  });
}
function toggleLaneSel(cb) {
  const id = cb.dataset.selectTask;
  if (cb.checked) LANE_SEL.add(id); else LANE_SEL.delete(id);
  cb.closest('.chip').classList.toggle('sel', cb.checked);
  updateLaneBar();
}
function clearLaneSel() {
  LANE_SEL.clear();
  document.querySelectorAll('[data-select-task]:enabled').forEach(cb => {
    cb.checked = false; cb.closest('.chip').classList.remove('sel');
  });
  updateLaneBar();
}
function selectVisibleTasks() {
  document.querySelectorAll('[data-select-task]:enabled').forEach(cb => { cb.checked = true; toggleLaneSel(cb); });
}
function updateLaneBar() {
  const visible = new Set([...document.querySelectorAll('[data-select-task]')].filter(cb => OPEN_STATUSES.includes(MAP[cb.dataset.selectTask]?.status)).map(cb => cb.dataset.selectTask));
  LANE_SEL.forEach(id => { if (!visible.has(id)) LANE_SEL.delete(id); });
  const bar = document.getElementById('lane-bar');
  document.getElementById('lb-count').textContent = LANE_SEL.size;
  bar.classList.toggle('on', LANE_SEL.size > 0);
  bar.setAttribute('aria-busy', String(BULK_BUSY));
  bar.querySelectorAll('button').forEach(b => { b.disabled = BULK_BUSY; });
  document.getElementById('allow-ai').disabled = BULK_BUSY || ![...LANE_SEL].some(id => MAP[id]?.human_only);
  document.getElementById('select-visible').disabled = BULK_BUSY || !visible.size;
}
function setBulkBusy(busy) {
  BULK_BUSY = busy; updateLaneBar();
  document.querySelectorAll('[data-select-task]').forEach(cb => { cb.disabled = busy || !OPEN_STATUSES.includes(MAP[cb.dataset.selectTask]?.status); });
}

/* Queue the manual human_only preference. Capability and runner stay server-derived. */
async function applyLaneAction(action) {
  if (BULK_BUSY) return;
  const targets = [...LANE_SEL].map(id => MAP[id]).filter(t => t && OPEN_STATUSES.includes(t.status)
    && (action === 'human_only' ? !t.human_only : t.human_only));
  if (!targets.length) return;
  setBulkBusy(true);
  let ok = 0, failed = 0;
  for (const t of targets) {
    try {
      const r = await fetch('/queue', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:'ai_lane_change', payload:{task_path:t.path, task_title:t.title, action,
          lane:t.ai_lane, runner:t.ai_runner, date:todayStr(), time:timeStr()}})});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      t.human_only = action === 'human_only';
      t.ai_pending = true; // The server reclassifies capability and runner; never invent AI eligibility here.
      LANE_SEL.delete(t.id); ok++;
    } catch(e) { failed++; }
  }
  setBulkBusy(false);
  applyFilters();
  showToast(ok + ' ' + BOARD_LABEL.queued + (failed ? ' · ' + failed + ' ' + BOARD_LABEL.failed : ''), failed > 0);
}

/* 選択したタスクをまとめて完了にする。
   個別のステータス変更と同じ task_status_change キューを使うため、サーバー側の
   vault直接書き込み禁止・次便反映の流儀を崩さない。各タスクは独立して送るので、
   一部失敗時も成功分だけを画面から反映する。 */
async function applyBulkTaskStatus(newStatus) {
  if (BULK_BUSY) return;
  const ids = [...LANE_SEL];
  const targets = ids.map(id => MAP[id]).filter(t => t && OPEN_STATUSES.includes(t.status) && t.status !== newStatus);
  if (!targets.length) return;
  if (!confirm(BOARD_LABEL.confirmComplete.replace('%n', targets.length))) return;

  setBulkBusy(true);
  let ok = 0;
  const failed = [];
  for (const t of targets) {
    const payload = {
      task_path: t.path, task_title: t.title,
      old_status: t.status, new_status: newStatus,
      date: todayStr(), time: timeStr(),
    };
    try {
      const r = await fetch('/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'task_status_change', payload }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      t.status = newStatus;
      t.pending = true;
      LANE_SEL.delete(t.id);
      ok++;
    } catch (e) {
      failed.push(t.title);
    }
  }

  setBulkBusy(false);
  applyFilters();
  if (ok && window.SFX) SFX.task_complete();
  if (failed.length) {
    showToast(ok + ' ' + BOARD_LABEL.queued + ' · ' + failed.length + ' ' + BOARD_LABEL.failed, true);
  } else {
    showToast(ok + ' ' + BOARD_LABEL.queued);
  }
}

/* ===== クエスト効果ブロック（board_quests.json 由来。generate_board_quests.py がバッチ生成） ===== */
function questBlock(q) {
  const wrap = document.createElement('div');
  wrap.className = 'dp-quest';
  if (!q) {
    wrap.innerHTML = ('<div class="dq-hd">' + shukiIcon('gamepad') + ' クエスト効果</div>')
      + '<div class="dq-empty">効果は未生成です（次回バッチで付与）</div>';
    return wrap;
  }
  const li = arr => (arr || []).map(x => '<li>' + esc(x) + '</li>').join('');
  let h = ('<div class="dq-hd">' + shukiIcon('gamepad') + ' クエスト効果</div>');
  h += '<div class="dq-pills">'
    + '<span class="dq-pill">難易度 ' + starStr(q.difficulty) + '</span>'
    + '<span class="dq-pill">体力 ' + esc(q.stamina || '?') + '</span>'
    + (q.time_cost ? '<span class="dq-pill">所要 ' + esc(q.time_cost) + '</span>' : '')
    + '</div>';
  h += '<div class="dq-cols">'
    + '<div class="dq-col merit"><b>◎ 得るもの</b><ul>' + li(q.merits) + '</ul></div>'
    + '<div class="dq-col demerit"><b>△ コスト</b><ul>' + li(q.demerits) + '</ul></div>'
    + '</div>';
  h += '<div class="dq-terms"><span>即効性: <b>' + esc(dv(q.short_term) || '?') + '</b></span>'
    + '<span>長期効果: <b>' + esc(dv(q.long_term) || '?') + '</b></span></div>';
  if (q.value_note) h += ('<div class="dq-value">' + shukiIcon('bulb') + ' ') + esc(q.value_note) + '</div>';
  if (q.concepts && q.concepts.length)
    h += ('<div class="dq-concepts">' + shukiIcon('target') + ' 成長: ') + q.concepts.map(c => '<span class="cchip">' + esc(c) + '</span>').join('') + '</div>';
  wrap.innerHTML = h;
  return wrap;
}

/* ===== 本文プレビュー（/files/preview 共用。カードから全文を読めなかった穴を埋める） ===== */
async function loadDetailBody(el, path) {
  try {
    const r = await fetch('/files/preview?p=' + encodeURIComponent(path));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    el.innerHTML = await r.text();
    el.classList.remove('pv-loading');
  } catch(e) {
    el.textContent = '本文を読み込めませんでした（' + e + '）';
    el.classList.remove('pv-loading');
    el.classList.add('pv-err');
  }
}

/* ===== 詳細パネル ===== */
function showDetail(tid) {
  const t = MAP[tid];
  if (!t) return;

  document.getElementById('dp-title').textContent = t.title;

  const badges = document.getElementById('dp-badges');
  badges.innerHTML = '';
  const mkBadge = (txt, cls) => {
    const b = document.createElement('span');
    b.className = 'badge ' + (cls || '');
    b.textContent = txt;
    badges.appendChild(b);
  };
  mkBadge(t.status || '?', 's-' + (t.status || ''));
  if (t.pending)  mkBadge((shukiIcon('hourglass') + ' 次便で反映'), 'pend');
  if (t.area)     mkBadge(dv(t.area));
  if (t.priority) mkBadge(priLabel(t.priority), 'p-' + t.priority);

  const fields = document.getElementById('dp-fields');
  fields.innerHTML = '';
  const field = (lbl, val, html) => {
    if (!val && !html) return;
    const d = document.createElement('div');
    d.className = 'dp-field';
    d.innerHTML = '<div class="dp-lbl">' + esc(lbl) + '</div>'
      + '<div class="dp-val">' + (html || esc(String(val))) + '</div>';
    fields.appendChild(d);
  };

  const lane = LANE_DEFS.find(d => d.key === responsibilityKey(t));
  field('責任分担', lane.label + (t.human_only ? ' · ' + BOARD_LABEL.manual : ''));
  field('担当の理由', t.ai_reason || lane.title);
  field('進め方', t.ai_runner === 'dispatch' ? BOARD_LABEL.scheduled : t.ai_runner === 'session' ? BOARD_LABEL.conversation : null);
  if (t.ai_pending) field('反映状況', (shukiIcon('hourglass') + ' 次便で反映'));
  fields.appendChild(questBlock(t.quest));

  field('締切', t.due);
  field('開始予定', t.start);
  const age = ageDays(t.created);
  if (age !== null) field('起票', t.created + '（' + age + '日前）');
  if (t.next_action) field('次の一手', t.next_action);

  /* 📄 本文全文（/files/preview 共用。2026-08-16 新設） */
  const bodyField = document.createElement('div');
  bodyField.className = 'dp-field';
  bodyField.innerHTML = '<div class="dp-lbl">本文</div>'
    + '<div class="dp-body pv-loading">読み込み中…</div>';
  fields.appendChild(bodyField);
  loadDetailBody(bodyField.querySelector('.dp-body'), t.path);

  /* フォーカス切替（端末ローカル・vault本体は変わらない＝次便待ちも起きない） */
  const fwrap = document.createElement('div');
  fwrap.className = 'dp-field';
  const isF = (t.id === FOCUS);
  fwrap.innerHTML = '<div class="dp-lbl">フォーカス</div>'
    + '<div class="st-btns"><button class="act-btn st-btn' + (isF ? ' ok' : '') + '" data-focus="'
    + esc(t.id) + '">' + (isF ? (shukiIcon('target') + ' 解除する') : (shukiIcon('target') + ' 今はこれ')) + '</button></div>';
  fields.appendChild(fwrap);

  if (t.parent && MAP[t.parent])
    field('親タスク', null, '<a class="dp-link" data-goto="' + esc(t.parent) + '">' + esc(MAP[t.parent].title) + '</a>');

  const ch = (t.children || []).filter(c => MAP[c]);
  if (ch.length)
    field('子タスク', null, ch.map(c =>
      '<a class="dp-link" data-goto="' + esc(c) + '">' + esc(MAP[c].title) + '</a>'
    ).join('<br>'));

  /* 束ね元（Project / 概念ノード）と、同じ束の他タスク（2026-08-16・タスクボード改修 Phase 2）。
     束ね元自体はタスクDBに実体が無いので data-goto はつけない（テキストのみ）。
     兄弟タスクは実タスクなので data-goto でパネル遷移できる＝関係性をここから辿れる。 */
  if (t.parent_kind !== 'none') {
    field('束ね元', null,
      bundleIcon(t.parent_kind, t.parent_kind === 'concept' ? 'var(--blue)' : 'var(--accent)')
      + ' <span style="vertical-align:middle;">' + esc(t.project_title) + '</span>');
    const sibs = ALL.filter(o => o.id !== t.id && bundleKey(o) === bundleKey(t));
    if (sibs.length)
      field('同じ束の他タスク（' + sibs.length + '件）', null, sibs.map(s =>
        '<a class="dp-link" data-goto="' + esc(s.id) + '">' + esc(s.title) + '</a>'
      ).join('<br>'));
  }

  /* ステータス変更（次便で反映） */
  const allStatuses = ['todo', 'in-progress', 'on-hold', 'done', 'cancelled'];
  const others = allStatuses.filter(s => s !== t.status);
  if (others.length) {
    const wrap = document.createElement('div');
    wrap.className = 'dp-field';
    wrap.innerHTML = '<div class="dp-lbl">ステータス変更（次便で反映）</div>';
    const btns = document.createElement('div');
    btns.className = 'st-btns';
    others.forEach(s => {
      const b = document.createElement('button');
      b.className = 'act-btn st-btn';
      b.textContent = ST_LABEL[s] || s;
      b.setAttribute('data-change-to', s);
      b.setAttribute('data-task-id', tid);
      btns.appendChild(b);
    });
    wrap.appendChild(btns);
    fields.appendChild(wrap);
  }

  // 「VS Codeで開く」ボタンは 2026-08-05 撤去（閲覧専用化。編集は Obsidian 側で行う）。
  // ホームのカードと同じ「一手」導線（2026-08-13）。2026-08-16 に /next から分離：
  // /next は「全タスクから1つ選ぶ」単発起動スキルで、タスク名を渡す使い方は設計と噛み合っていなかった
  // （選定済みの1件を渡しているのに選定スキルを呼んでいた）。方針すり合わせ→代行実行→完了まで進める
  // task-exec に分離（同日、first-step から代行実行込みの設計に改訂してリネーム）。
  const acts = document.getElementById('dp-acts');
  acts.innerHTML = '<a class="act-btn go exec-btn" href="#" data-exec-skill="task-exec" data-exec-text="'
    + esc(t.title) + '" data-exec-label="' + esc(t.title)
    + '" title="このタスクの進め方をすり合わせて完了まで進める">""" + _ICON_PLAY + """ 一手</a>';

  document.getElementById('detail-panel').classList.add('open');
  document.getElementById('detail-overlay').classList.add('open');
}
function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
  document.getElementById('detail-overlay').classList.remove('open');
}

/* ===== ステータス変更 → /queue ===== */
async function changeStatus(tid, newStatus, isUndo) {
  const t = MAP[tid];
  if (!t) return;
  const prevStatus = t.status;   /* 「元に戻す」で戻す先。押す前の値を控える */
  const payload = {
    task_path: t.path, task_title: t.title,
    old_status: prevStatus, new_status: newStatus,
    date: todayStr(),   // UTCではなくローカル日付（→ ' + shukiIcon('book') + '教訓集 2026-08-06）
    time: timeStr(),    // HH:MM（先延ばし実験・時刻粒度のトラッキング用。2026-08-18）
  };
  try {
    const r = await fetch(')/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'task_status_change', payload }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    t.status = newStatus;
    t.pending = true;   /* サーバー側も同じ状態を返すので、リロードしても巻き戻らない */

    /* 盤面から消える遷移（完了・キャンセル）はパネルも畳む。対象が盤面に無いのに
       それを映す器だけが残るのは中途半端で、次の一手への動線も塞ぐため。
       他の遷移はチップが残るので、パネルも開いたままが自然。 */
    const leaves = (newStatus === 'done' || newStatus === 'cancelled');
    if (newStatus === 'done') {
      if (window.SFX) SFX.task_complete();
      /* 押したボタンの位置から散らす＝「自分がやった」感触を操作した場所に返す */
      const b = document.querySelector('[data-change-to="done"][data-task-id="' + CSS.escape(tid) + '"]');
      const r2 = b ? b.getBoundingClientRect() : null;
      burstAt(r2 ? r2.left + r2.width / 2 : innerWidth / 2,
              r2 ? r2.top + r2.height / 2 : innerHeight / 2);
    }
    if (leaves && tid === FOCUS) setFocus(null);   /* 終わったものにフォーカスを残さない */

    if (isUndo) {
      showToast('""" + _ICON_CHECK + """ 取り消しました（' + (ST_LABEL[newStatus] || newStatus) + 'に戻します）');
    } else {
      /* 完了・キャンセルは誤クリックの取り消し動機が強い。パネルを自動で畳む分、
         1手で戻せる逃げ道をここに置く（無いと「フィルタON→探す→開く→押す」の4手になる）。 */
      showToast('""" + _ICON_CHECK + """ ' + (ST_LABEL[newStatus] || newStatus) + 'に変更を予約しました。次便で反映します',
                false, { label: '元に戻す', fn: () => changeStatus(tid, prevStatus, true) });
    }
    if (leaves) setTimeout(closeDetail, 700);   /* エフェクト(0.72s)を見届けてから畳む */
    else showDetail(tid);
    applyFilters();
  } catch(e) {
    showToast('""" + _ICON_CROSS + """ 予約できませんでした（' + e + '）', true);
  }
}

/* ===== トースト ===== */
let toastTimer = null;
function showToast(msg, isErr, undo) {
  const el = document.getElementById('toast');
  el.innerHTML = msg;
  if (undo) {
    const b = document.createElement('button');
    b.className = 't-undo';
    b.textContent = undo.label;
    b.onclick = () => { clearTimeout(toastTimer); el.className = ''; undo.fn(); };
    el.appendChild(b);
  }
  el.className = 'show' + (isErr ? ' err' : '');
  clearTimeout(toastTimer);
  /* 取り消しは押す間が要るので少し長く出す */
  toastTimer = setTimeout(() => { el.className = ''; }, undo ? 5200 : 2800);
}

/* ===== イベント委譲 ===== */
document.getElementById('detail-panel').addEventListener('click', e => {
  const f = e.target.closest('[data-focus]');
  if (f) { setFocus(f.getAttribute('data-focus')); return; }
  const a = e.target.closest('[data-goto]');
  if (a) { showDetail(a.getAttribute('data-goto')); return; }
  const b = e.target.closest('[data-change-to]');
  if (b) changeStatus(b.getAttribute('data-task-id'), b.getAttribute('data-change-to'));
});
document.getElementById('wall-container').addEventListener('change', e => {
  if (e.target.matches('[data-select-task]')) toggleLaneSel(e.target);
});
document.getElementById('wall-container').addEventListener('click', e => {
  if (e.target.closest('.task-select')) return;
  const c = e.target.closest('[data-goto]');
  if (c) showDetail(c.getAttribute('data-goto'));
});
document.getElementById('focus-band').addEventListener('click', e => {
  const c = e.target.closest('[data-goto]');
  if (c) showDetail(c.getAttribute('data-goto'));
});

init();
</script>
</body></html>"""


# 🌐 データ値（vault に入っている実値）の表示ラベル。tt() が触れないよう ctx を付けた
# 辞書キー（"datavalue|高" 等）で引く＝テンプレート中の '高' が巻き添えで置換されない。
# lang=ja では t() が原文を返すので恒等写像＝従来と同じ表示になる。
_DATA_VALUES = [
    *shuki_profile.area_names(),                           # Area（profile.json が正）
    "高", "中", "低",                                      # 優先度 / 即効性
    "極小", "小", "大", "特大",                            # 長期効果
    "なし",                                                # 即効性なし
]


def _data_label_json():
    """データ値（Area名・優先度等）の表示ラベル。**profile の labels が共有辞書より優先**
    （2026-09-27）。個人固有のArea名は公開される i18n 辞書に入れられないので、その訳語だけは
    profile.json の `areas[].labels` が持つ。辞書にも profile にも無ければ原文のまま。"""
    lang = shuki_i18n.current_lang()
    out = {}
    for v in _DATA_VALUES:
        out[v] = shuki_profile.area_label(v, lang) or t(v, "datavalue")
    return json.dumps(out, ensure_ascii=False)


def _board_labels_json():
    labels = {
        "hint": "タイトルで詳細、チェックでまとめて操作。", "advanced": "詳細設定・保存済みビュー",
        "viewFilters": "表示・絞り込み", "activeFilters": "有効な条件",
        "more": "すべて表示", "fewer": "折りたたむ", "completed": "完了したタスク",
        "highPriority": "高優先", "done": "完了", "todo": "未着手", "inProgress": "進行中", "onHold": "保留", "cancelled": "キャンセル済み",
        "count": "件", "queued": "件を予約。次便で反映します", "failed": "件は失敗しました",
        "starts": "開始待ち", "manual": "手動指定", "pending": "⏳ 次便で反映", "noProject": "束ね元なし",
        "ai": "AIで完了まで", "prep": "AIは準備まで", "human": "自分でやる",
        "scheduled": "自動便で実行", "conversation": "対話で進める",
        "aiHint": "AIが完了まで進められる仕事。自動便か対話かは各タスクの詳細で確認できます。",
        "prepHint": "AIが調査や準備を進めます。お金・健康・外部送信の最終判断はあなたが行います。",
        "humanHint": "自分で行う仕事。手動指定を解除しても、AIができる範囲の判定は残ります。",
        "confirmComplete": "%n件を完了に変更予約します。よろしいですか？",
    }
    return json.dumps({key: t(value, "board") for key, value in labels.items()}, ensure_ascii=False)


def render_board_html():
    # PAGE は完全な静的テンプレート（タスクは /board/data から JS が取りに行く）＝
    # vault のデータが混ざる前なので tt() をページ全体にかけてよい（shuki_i18n の前提条件）。
    # シェル（上部ナビ・下部タブ・対話ドック）はリクエスト毎に組み直す＝ナビ表示設定や
    # モデル選択の変更をサーバー再起動なしで反映する（2026-09-01）。自前で t()/tt() 済みなので
    # hydrate 後に二重適用しない。board は固定レイアウトのため下部タブは inflow=True。
    # DATA_LABEL は tt() の**後**に差し込む（先に入れるとキー側の日本語まで訳されて
    # データ値の引き当てが壊れる＝dashboard_visualize の <!--VIZ_OPTIONS--> と同じ理由）。
    page = shuki_i18n.tt_html(PAGE, ctx="board").replace("__DATA_LABEL_JSON__", _data_label_json())
    page = page.replace("__BOARD_LABEL_JSON__", _board_labels_json())
    page = page.replace('label="その他のグループ分け"',
                        'label="' + html.escape(t("その他のグループ分け", "board"), quote=True) + '"')
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        page, "board",
        tt(dashboard_icons.nav_icon_svg("board", 19) + " タスクボード"),
        inflow=True)
