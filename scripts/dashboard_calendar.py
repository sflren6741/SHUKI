#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_calendar.py — 📅 カレンダーページ（dashboard_server.py の /calendar ページ）

Schedule / Results share a monthly calendar and selection. Results reuse the activity
collector and load without Google Calendar. Legacy scheduling tools remain available.

Google Calendar（primary）の予定を、開くたびに API を直接呼んで表示する（スナップショット
ファイルは経由しない・常に最新）。今日/今週の一覧に加え、月グリッド表示にも対応する。
各予定にはその場でメモを書け、保存先は既存の memo キュー（`99_System/ui-queue/memo_YYYY-MM-DD.json`）
を再利用する。`source: calendar` と `calendar_event_id` / `calendar_summary` / `calendar_start` を付け、
日記・自由記述と同じ `processing: ai|record` の二択・同じ回収便（orchestrator.md §📝メモの回収）で仕分ける。

右下の「＋」から予定を直接作成できる（POST /calendar/event → calendar_utils.create_event）。
これはユーザーの明示操作でのみ呼ばれる経路で、orchestrator 等の自動便からは呼ばれない
（GCal書き込みは人間確認必須の原則どおり・.claude/rules/00-guardrails.md）。
"""
import dashboard_chat  # noqa: E402  (💬 全ページ共通の対話ドック)
import dashboard_icons  # noqa: E402  (線アイコンSVG)
import dashboard_ui  # noqa: E402  (共通ヘッダー・ナビ・PWA)
import shuki_i18n  # noqa: E402
from shuki_i18n import t, tt  # noqa: E402  (表示言語。未翻訳の文言は日本語のまま)


# POST /queue の共通上限（64KiB）を超えないよう、画面側でも長さを制限する。
CALENDAR_MEMO_MAX_CHARS = 4000


PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title>📅 カレンダー</title>
<link rel="stylesheet" href="/english/style.css">
<script src="/english/routine.js"></script>
<style>
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg); font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  main.cal-page { flex:1; width:100%; max-width:980px; margin:0 auto; padding:0 16px 100px; }
  .cal-intro { padding:4px 2px 14px; }
  .cal-kicker { display:flex; align-items:center; gap:6px; color:var(--accent);
    font-size:.74rem; font-weight:700; letter-spacing:.03em; }
  .cal-kicker svg { flex-shrink:0; }
  .cal-intro h2 { margin-top:8px; font-size:1.12rem; line-height:1.4; }
  .cal-intro p { margin-top:5px; color:var(--muted); font-size:.8rem; line-height:1.6; }
  .cal-range { display:flex; gap:8px; margin-bottom:14px; }
  .cal-range button { border:1px solid var(--line); border-radius:999px; padding:7px 16px;
    background:var(--card); color:var(--fg); font:inherit; font-size:.82rem; font-weight:700;
    cursor:pointer; min-height:44px; }
  .cal-range button.active { background:var(--accent); color:var(--bg); border-color:var(--accent); }

  /* ── 今日/今週：予定の縦リスト ── */
  .cal-days { display:flex; flex-direction:column; gap:16px; }
  .cal-day-head { color:var(--muted); font-size:.76rem; font-weight:700; letter-spacing:.02em;
    border-bottom:1px solid var(--line); padding-bottom:4px; }
  .cal-events { display:flex; flex-direction:column; gap:8px; }
  .cal-cell-meeting { position:absolute; top:8px; right:8px; display:inline-flex; color:var(--accent); }
  .cal-meeting { display:flex; align-items:center; gap:8px; min-height:44px; margin:0 0 8px; padding:0 12px;
    border-radius:8px; text-decoration:none; color:var(--fg); background:var(--card); border:1px solid var(--line); }
  .cal-meeting svg { color:var(--accent); flex:none; }
  .cal-meeting:hover { border-color:var(--accent); }
  .cal-meeting-items { color:var(--muted); font-size:.88rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .cal-event { background:var(--card); border:1px solid var(--line); border-radius:11px; padding:11px 13px; }
  .cal-event-head { display:flex; align-items:baseline; gap:9px; cursor:pointer; }
  .cal-event-time { color:var(--accent); font-size:.78rem; font-weight:800; font-variant-numeric:tabular-nums;
    flex-shrink:0; min-width:3.6em; }
  .cal-event-summary { flex:1; font-size:.92rem; font-weight:700; overflow-wrap:anywhere; }
  .cal-event-note-count { color:var(--muted); font-size:.72rem; flex-shrink:0; }
  .cal-event-loc { margin-top:3px; color:var(--muted); font-size:.76rem; padding-left:calc(3.6em + 9px); }
  .cal-event-notes { margin-top:9px; padding-left:calc(3.6em + 9px); display:flex; flex-direction:column; gap:6px; }
  .cal-note { background:color-mix(in srgb, var(--bg) 55%, var(--card)); border:1px solid var(--line);
    border-radius:8px; padding:7px 10px; font-size:.8rem; }
  .cal-note-head { display:flex; gap:7px; align-items:center; color:var(--muted); font-size:.68rem; }
  .cal-note-status { border:1px solid color-mix(in srgb, var(--accent) 38%, transparent);
    border-radius:999px; color:var(--accent); padding:0 6px; }
  .cal-note-status.done { color:var(--teal); border-color:color-mix(in srgb, var(--teal) 38%, transparent); }
  .cal-note-text { margin-top:4px; white-space:pre-wrap; overflow-wrap:anywhere; }
  .cal-event-form { margin-top:9px; padding-left:calc(3.6em + 9px); display:none; flex-direction:column; gap:7px; }
  .cal-event-form.open { display:flex; }
  .cal-event-form textarea { width:100%; min-height:5.5em; resize:vertical; background:var(--bg);
    color:var(--fg); border:1px solid var(--line); border-radius:8px; padding:9px 11px; font:inherit;
    font-size:.85rem; line-height:1.6; }
  .cal-event-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .cal-event-toggle { background:none; border:1px solid var(--line); border-radius:999px;
    padding:5px 13px; min-height:44px; color:var(--muted); font:inherit; font-size:.74rem; cursor:pointer; }
  .cal-event-toggle:hover { color:var(--fg); }
  .cal-action { display:inline-flex; align-items:center; justify-content:center; gap:5px;
    border:1px solid var(--line); border-radius:999px; padding:7px 15px; min-height:44px;
    font:inherit; font-size:.78rem; font-weight:800; cursor:pointer; }
  .cal-action:disabled { opacity:.55; cursor:default; }
  .cal-record { background:var(--card); color:var(--fg); }
  .cal-ai { background:var(--accent); color:var(--bg); border-color:var(--accent); }
  .cal-status { min-height:1.1em; color:var(--teal); font-size:.76rem; }
  .cal-status.error { color:var(--red); }
  .cal-empty, .cal-error { color:var(--muted); font-size:.84rem; padding:18px 2px; }
  .cal-error { color:var(--red); }

  /* ── AI提案（差し込み型）：まだ確定していないので、実予定より軽い「幽霊」表現にする ── */
  .cal-suggestions { margin-top:10px; padding-left:calc(3.6em + 9px); display:flex; flex-direction:column; gap:8px; }
  .cal-suggest { border:1.5px dashed color-mix(in srgb, var(--accent) 55%, var(--line)); border-radius:12px;
    padding:10px 13px; background:color-mix(in srgb, var(--accent) 6%, transparent); }
  .cal-suggest-head { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; font-size:.88rem; font-weight:700; }
  .cal-suggest-area { color:var(--muted); font-size:.7rem; font-weight:400; }
  .cal-suggest-reason { margin-top:3px; color:var(--muted); font-size:.74rem; }
  .cal-suggest-actions { margin-top:8px; display:flex; gap:8px; }

  /* ── 今月：グリッド。定規で引いた表ではなく、丸みのある「タイル」の集まりにする ── */
  .cal-month-nav { display:none; align-items:center; gap:14px; margin-bottom:14px; }
  .cal-month-nav button { border:1px solid var(--line); background:var(--card); color:var(--fg);
    border-radius:999px; width:44px; height:44px; font-size:1rem; cursor:pointer; }
  .cal-month-nav button:hover { border-color:var(--accent); color:var(--accent); }
  .cal-month-label { font-weight:800; font-size:1rem; letter-spacing:.01em; }
  .cal-month-today { margin-left:auto; border:1px solid var(--line); border-radius:999px;
    padding:5px 14px; background:var(--card); color:var(--muted); font:inherit; font-size:.74rem;
    cursor:pointer; }
  .cal-month-nav .cal-month-today { width:auto; white-space:nowrap; font-size:.74rem; }
  .cal-grid { display:none; grid-template-columns:repeat(7,minmax(0,1fr)); gap:7px; margin-bottom:6px; }
  .cal-grid-head { text-align:center; color:var(--muted); font-size:.68rem; font-weight:800;
    letter-spacing:.04em; padding-bottom:2px; }
  .cal-cell { min-width:0; min-height:82px; font:inherit; text-align:left; border-radius:12px; background:var(--card);
    border:1px solid var(--line); padding:8px 7px; cursor:pointer; display:flex; flex-direction:column;
    gap:5px; position:relative; transition:transform .12s, border-color .12s, box-shadow .12s; }
  .cal-cell:hover { transform:translateY(-1px); border-color:color-mix(in srgb, var(--accent) 45%, var(--line)); }
  .cal-cell.out-month { opacity:.35; }
  .cal-cell.is-today { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }
  .cal-cell.selected { background:color-mix(in srgb, var(--accent) 16%, var(--card));
    border-color:var(--accent); }
  .cal-cell-daynum { font-size:.8rem; font-weight:800; color:var(--fg); width:20px; height:20px;
    display:flex; align-items:center; justify-content:center; border-radius:50%; flex-shrink:0; }
  .cal-cell.is-today .cal-cell-daynum { background:var(--accent); color:var(--bg); }
  .cal-cell-dots { display:flex; flex-wrap:wrap; gap:3px; margin-top:auto; }
  .cal-cell-dot { width:6px; height:6px; border-radius:50%; background:var(--accent); flex-shrink:0; }
  .cal-cell-dot-suggest { width:6px; height:6px; border-radius:50%; border:1.3px dashed var(--accent);
    background:transparent; flex-shrink:0; }
  .cal-cell-more { font-size:.62rem; color:var(--muted); }
  .cal-day-detail { display:none; margin-top:18px; }
  .cal-page [hidden], #cal-fab[hidden], #cal-tooltip[hidden] { display:none !important; }
  .cal-view-tabs { display:flex; gap:4px; padding:4px; border:1px solid var(--line);
    border-radius:12px; background:var(--card); margin-bottom:14px; }
  .cal-view-tabs button { flex:1; min-height:44px; border:0; border-radius:8px;
    background:transparent; color:var(--muted); font:inherit; font-weight:700; cursor:pointer; }
  .cal-view-tabs button[aria-selected=true] { background:color-mix(in srgb, var(--accent) 12%, var(--card)); color:var(--fg); }
  .cal-results-controls { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:12px; }
  .cal-results-controls label { display:flex; align-items:center; gap:7px; color:var(--muted); font-size:.78rem; }
  .cal-results-controls select { min-height:44px; max-width:100%; min-width:0; border:1px solid var(--line);
    border-radius:8px; padding:6px 8px; background:var(--card); color:var(--fg); font:inherit; }
  .cal-results-controls .cal-project-label { flex:1; min-width:180px; }
  #cal-result-project { flex:1; width:0; }
  .cal-result-summary { display:flex; flex-wrap:wrap; align-items:center; gap:8px 18px; margin-bottom:8px; font-size:.82rem; }
  .cal-result-help { color:var(--muted); font-size:.75rem; line-height:1.6; margin-bottom:12px; }
  .cal-legend { display:flex; align-items:center; gap:4px; color:var(--muted); font-size:.7rem; }
  .cal-legend-mark { width:14px; height:14px; border-radius:3px; background:var(--heat-0); }
  .cal-legend-mark[data-level="1"] { background:var(--heat-1); }
  .cal-legend-mark[data-level="2"] { background:var(--heat-2); }
  .cal-legend-mark[data-level="3"] { background:var(--heat-3); }
  .cal-legend-mark[data-level="4"] { background:var(--heat-4); }
  .cal-cell.results-cell { background:var(--heat-0); }
  .cal-cell.results-cell.l1 { background:var(--heat-1); }
  .cal-cell.results-cell.l2 { background:var(--heat-2); }
  .cal-cell.results-cell.l3 { background:var(--heat-3); }
  .cal-cell.results-cell.l4 { background:var(--heat-4); }
  .cal-cell.results-cell.out-month { opacity:1; border-style:dashed; }
  .results-cell .cal-cell-daynum, .cal-cell-count { background:var(--card); color:var(--fg);
    width:auto; min-width:24px; height:24px; padding:2px 4px; border-radius:6px; }
  .results-cell .cal-cell-daynum { align-self:flex-start; }
  .cal-cell-count { align-self:flex-end; margin-top:auto; font-size:.72rem; text-align:center; }
  .cal-cell.results-cell.selected { outline:2px solid var(--accent); outline-offset:1px; }
  .cal-cell.is-future { background:var(--card); }
  .cal-cell.is-future .cal-cell-daynum { color:var(--muted); }
  .cal-grid[aria-busy=true] { opacity:.5; pointer-events:none; }
  .cal-grid > .cal-empty { grid-column:1 / -1; }
  .cal-result-section { margin:12px 0; }
  .cal-result-section h3 { font-size:.82rem; margin-bottom:6px; }
  .cal-result-entry { border:1px solid var(--line); border-radius:8px; background:var(--card); padding:8px 11px; margin:6px 0; }
  .cal-result-row { display:flex; align-items:center; flex-wrap:wrap; gap:7px; font-size:.84rem; }
  .cal-result-title { flex:1; min-width:100px; overflow-wrap:anywhere; }
  .cal-result-tag { color:var(--muted); font-size:.7rem; }
  .cal-result-extra { color:var(--muted); font-size:.76rem; white-space:pre-wrap; overflow-wrap:anywhere; }
  .cal-result-entry button, .cal-result-table button, .cal-error button { min-height:44px; border:1px solid var(--line);
    border-radius:8px; background:var(--card); color:var(--fg); padding:5px 9px; font:inherit; cursor:pointer; }
  .cal-result-preview { margin-top:8px; overflow:auto; overflow-wrap:anywhere; }
  .cal-result-preview img { max-width:100%; }
  .cal-result-preview pre { overflow:auto; }
  .cal-result-table { margin-top:14px; font-size:.76rem; }
  .cal-result-table summary { cursor:pointer; min-height:44px; display:flex; align-items:center; color:var(--muted); }
  .cal-result-table summary::before { content:'›'; margin-right:8px; font-size:1rem; }
  .cal-result-table[open] summary::before { transform:rotate(90deg); }
  .cal-table-scroll { overflow:auto; }
  .cal-result-table table { border-collapse:collapse; width:100%; white-space:nowrap; font-variant-numeric:tabular-nums; }
  .cal-result-table th, .cal-result-table td { text-align:right; padding:4px 8px; border-bottom:1px solid var(--line); }
  .cal-result-table th:first-child, .cal-result-table td:first-child { text-align:left; }
  #cal-tooltip { position:fixed; max-width:min(260px,calc(100vw - 16px)); padding:8px 11px;
    background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:8px;
    font-size:.78rem; pointer-events:none; z-index:80; box-shadow:0 4px 14px color-mix(in srgb, var(--fg) 12%, transparent); }
  .cal-page button:focus-visible, .cal-page select:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  @media (forced-colors:active) { .cal-cell.results-cell { border:1px solid ButtonText; }
    .cal-cell.results-cell.selected { outline:2px solid Highlight; } }
  @media (prefers-reduced-motion:reduce) { .cal-cell { transition:none; } .cal-cell:hover { transform:none; } }

  /* ── ＋ 予定を追加（左下フローティング）。右下は対話ドック（#chat-fab/#result/#result-mini、
     z-index:1000〜1300）の「一等地」で、ユーザーの実機で＋ボタンがドックの下に完全に隠れて見えなく
     なっていた（2026-09-26 ユーザーの指摘で発覚）。dashboard_chat.py の既存ルール「同じ右下の
     一等地は一つしか使わない」に倣い、競合しない左下へ動かす。 */
  .cal-fab { position:fixed; left:20px; bottom:20px; width:54px; height:54px; border-radius:50%;
    background:var(--accent); color:var(--bg); border:none; font-size:1.7rem; font-weight:700;
    line-height:1; cursor:pointer; box-shadow:0 10px 24px color-mix(in srgb, var(--accent) 45%, transparent);
    z-index:60; display:flex; align-items:center; justify-content:center; }
  .cal-fab:hover { transform:scale(1.05); }
  .cal-modal-backdrop { position:fixed; inset:0; background:color-mix(in srgb, black 55%, transparent);
    display:none; align-items:center; justify-content:center; z-index:70; padding:16px; }
  .cal-modal-backdrop.open { display:flex; }
  .cal-modal { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:22px;
    width:min(94vw,420px); display:flex; flex-direction:column; gap:12px; max-height:88vh; overflow:auto;
    box-shadow:0 24px 60px color-mix(in srgb, black 30%, transparent); }
  .cal-modal h3 { font-size:1.02rem; }
  .cal-modal label { font-size:.78rem; color:var(--muted); display:flex; flex-direction:column; gap:4px; }
  .cal-modal label.row { flex-direction:row; align-items:center; gap:7px; }
  .cal-modal input[type=text], .cal-modal input[type=date], .cal-modal input[type=time], .cal-modal textarea {
    background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:9px;
    padding:9px 11px; font:inherit; font-size:.86rem; }
  .cal-modal textarea { min-height:4em; resize:vertical; }
  #cal-new-time-row { display:none; gap:8px; }
  #cal-new-time-row label { flex:1; }
  .cal-modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:2px; }
  .cal-modal-status { font-size:.78rem; color:var(--red); min-height:1.1em; }

  @media (max-width:700px) {
    main.cal-page { padding:0 10px 110px; }
    .cal-event-loc, .cal-event-notes, .cal-event-form, .cal-suggestions { padding-left:0; margin-top:6px; }
    .cal-grid { gap:4px; }
    .cal-cell { min-height:58px; border-radius:8px; padding:4px; gap:3px; }
    .cal-cell-daynum { font-size:.72rem; width:17px; height:17px; }
    .cal-fab { left:14px; bottom:78px; width:50px; height:50px; }
  }
  @media (max-width:360px) { main.cal-page { padding-left:0; padding-right:0; }
    .cal-grid { gap:2px; } .cal-month-nav { gap:6px; } .cal-month-label { font-size:.86rem; }
    .cal-results-controls { padding:0 4px; } }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head><body>
<!--SHUKI_PAGE_HEADER-->
<main class="cal-page">
  <section class="cal-intro">
    <div class="cal-kicker">""" + dashboard_icons.ui_icon_svg("calendar", 15) + """ カレンダー</div>
    <p>Switch between your plans and recorded activity. Select a day to see its details.</p>
  </section>
  <div class="cal-view-tabs" role="tablist" aria-label="Calendar view">
    <button type="button" id="cal-tab-schedule" role="tab" aria-selected="true" aria-controls="cal-content" data-view="schedule">Schedule</button>
    <button type="button" id="cal-tab-results" role="tab" aria-selected="false" aria-controls="cal-content" tabindex="-1" data-view="results">Results</button>
  </div>
  <div id="cal-content" role="tabpanel" aria-labelledby="cal-tab-schedule">
  <div class="cal-range" role="group" aria-label="表示範囲">
    <button type="button" data-range="today">今日</button>
    <button type="button" data-range="week">今週</button>
    <button type="button" data-range="month" class="active">今月</button>
  </div>
  <div id="cal-results-controls" class="cal-results-controls" hidden>
    <label>Activity<select id="cal-result-metric" aria-label="Activity metric">
      <option value="all">All activity</option><option value="done">Completed</option>
      <option value="log">Logs</option><option value="created">Created tasks</option><option value="knowledge">Knowledge</option>
      <option value="session">Sessions</option><option value="turn">Turns</option>
    </select></label>
    <label class="cal-project-label">Project<select id="cal-result-project" aria-label="Project"><option value="">All projects</option></select></label>
  </div>
  <div id="cal-result-summary" class="cal-result-summary" aria-live="polite" hidden></div>
  <p id="cal-result-help" class="cal-result-help" hidden></p>
  <div id="cal-month-nav" class="cal-month-nav">
    <button type="button" data-month-nav="-1" aria-label="前の月">‹</button>
    <span id="cal-month-label" class="cal-month-label"></span>
    <button type="button" data-month-nav="1" aria-label="次の月">›</button>
    <button type="button" class="cal-month-today" data-month-nav="0">今月へ</button>
  </div>
  <section id="cal-english-routine" class="en-routine" aria-label="IELTS study routine"></section>
  <div id="cal-days" class="cal-days"><p class="cal-empty">読み込み中…</p></div>
  <div id="cal-month-grid" class="cal-grid"></div>
  <div id="cal-day-detail" class="cal-day-detail" aria-live="polite"></div>
  <details id="cal-result-table" class="cal-result-table" hidden>
    <summary>Daily counts and rankings</summary><div class="cal-table-scroll" id="cal-result-table-body"></div>
  </details>
  </div>
</main>
<div id="cal-tooltip" role="tooltip" hidden></div>
<button type="button" id="cal-fab" class="cal-fab" title="予定を追加" aria-label="予定を追加">+</button>
<div id="cal-modal-backdrop" class="cal-modal-backdrop">
  <div class="cal-modal">
    <h3>予定を追加</h3>
    <label>予定名<input type="text" id="cal-new-summary" maxlength="200" placeholder="例: 通院"></label>
    <label>日付<input type="date" id="cal-new-date"></label>
    <label class="row"><input type="checkbox" id="cal-new-allday" checked> 終日</label>
    <div id="cal-new-time-row">
      <label>開始<input type="time" id="cal-new-start"></label>
      <label>終了<input type="time" id="cal-new-end"></label>
    </div>
    <label>場所（任意）<input type="text" id="cal-new-location" maxlength="200"></label>
    <label>メモ（任意）<textarea id="cal-new-desc" maxlength="1000"></textarea></label>
    <div class="cal-modal-status" id="cal-modal-status"></div>
    <div class="cal-modal-actions">
      <button type="button" class="cal-event-toggle" id="cal-modal-cancel">キャンセル</button>
      <button type="button" class="cal-action cal-ai" id="cal-modal-submit">作成</button>
    </div>
  </div>
</div>
<!--SHUKI_BOTTOM_NAV-->
<script>
(() => {
  const MAX_CHARS = """ + str(CALENDAR_MEMO_MAX_CHARS) + """;
  const MEETING_ICON = '""" + dashboard_icons.ui_icon_svg("calendar", 13) + """';
  const daysBox = document.getElementById('cal-days');
  const monthNav = document.getElementById('cal-month-nav');
  const monthLabel = document.getElementById('cal-month-label');
  const monthGrid = document.getElementById('cal-month-grid');
  const dayDetail = document.getElementById('cal-day-detail');
  const rangeButtons = Array.from(document.querySelectorAll('.cal-range button'));
  const viewButtons = Array.from(document.querySelectorAll('[data-view]'));
  const resultControls = document.getElementById('cal-results-controls');
  const metricSelect = document.getElementById('cal-result-metric');
  const projectSelect = document.getElementById('cal-result-project');
  const resultSummary = document.getElementById('cal-result-summary');
  const resultHelp = document.getElementById('cal-result-help');
  const resultTable = document.getElementById('cal-result-table');
  const tooltip = document.getElementById('cal-tooltip');
  const params = new URLSearchParams(location.search);
  let currentView = params.get('view') === 'results' ? 'results' : 'schedule';
  let currentRange = ['today', 'week'].includes(params.get('range')) ? params.get('range') : 'month';
  let currentAnchor = /^[0-9]{4}-[0-9]{2}$/.test(params.get('anchor') || '') ? params.get('anchor') : null;
  let monthData = null;
  let selectedDate = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(params.get('date') || '') ? params.get('date') : null;
  if (!currentAnchor && selectedDate) currentAnchor = selectedDate.slice(0, 7);
  let loadRevision = 0;
  let loadedAnchor = null;
  let lastPointer = 'mouse';
  // Server labels are Japanese; format month/day titles here so English mode does not mix scripts.
  const LANG_EN = document.documentElement.lang === 'en';
  const WEEKDAYS = LANG_EN ? ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] : ['月','火','水','木','金','土','日'];
  function isoDate(iso) { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d); }
  function monthTitle(anchor, fallback) {
    if (!LANG_EN || !/^[0-9]{4}-[0-9]{2}$/.test(anchor || '')) return fallback;
    return isoDate(anchor + '-01').toLocaleDateString('en-GB', {month:'long', year:'numeric'});
  }
  function dayTitle(day) {
    if (!LANG_EN || !day.date) return day.label;
    return isoDate(day.date).toLocaleDateString('en-GB', {weekday:'short', day:'numeric', month:'short'})
      + (day.is_today ? ' · Today' : '');
  }
  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }
  const METRIC_LABELS = {all:'All activity', done:'Completed', log:'Logs', created:'Created tasks', knowledge:'Knowledge',
    session:'Sessions', turn:'Turns'};
  const METRIC_HELP = {
    all:'Counts completions, logs, created tasks and knowledge notes. One task can count when created and again when completed.',
    done:'Completion dates use the actual end date, then the note date or creation date. Fallback dates are labeled Estimated.',
    log:'Logs use the event date; the creation date is used when no event date is recorded.',
    created:'Tasks counted on their creation date, including tasks still in progress.',
    knowledge:'Knowledge notes counted on their creation date.',
    session:'Claude Code and Codex conversation sessions active that day. Scheduled runs are excluded. Project filter does not apply.',
    turn:'User messages to Claude Code and Codex that day. Scheduled runs, tool results and system injections are excluded. Project filter does not apply.'
  };
  const NO_ENTRY_METRICS = ['session', 'turn'];  // counted from transcripts, not vault files: no drill-down list, no project filter

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function noteHtml(n) {
    const done = n.status === 'done';
    const badge = n.processing === 'record' ? '記録のみ' : (done ? 'AI処理済み' : 'AI処理待ち');
    return '<div class="cal-note">'
      + '<div class="cal-note-head"><span>' + escHtml(String(n.ts || '').slice(5, 16)) + '</span>'
      + '<span class="cal-note-status' + (done ? ' done' : '') + '">' + badge + '</span></div>'
      + '<div class="cal-note-text">' + escHtml(n.text) + '</div></div>';
  }

  function eventHtml(ev) {
    const notes = ev.notes || [];
    const notesHtml = notes.length ? notes.map(noteHtml).join('') : '';
    return '<article class="cal-event" data-event-id="' + escHtml(ev.id) + '" data-start="' + escHtml(ev.start || '') + '">'
      + '<div class="cal-event-head" data-toggle>'
      + '<span class="cal-event-time">' + escHtml(ev.time_label) + '</span>'
      + '<span class="cal-event-summary">' + escHtml(ev.summary || '（無題の予定）') + '</span>'
      + (notes.length ? '<span class="cal-event-note-count">📝' + notes.length + '</span>' : '')
      + '</div>'
      + (ev.location ? '<div class="cal-event-loc">' + escHtml(ev.location) + '</div>' : '')
      + (notesHtml ? '<div class="cal-event-notes">' + notesHtml + '</div>' : '')
      + '<div class="cal-event-form" data-form>'
      + '<textarea maxlength="' + MAX_CHARS + '" placeholder="この予定についてメモを書く…" data-text></textarea>'
      + '<div class="cal-event-actions">'
      + '<button type="button" class="cal-action cal-record" data-save="record">記録として保存</button>'
      + '<button type="button" class="cal-action cal-ai" data-save="ai">AIに送る</button>'
      + '</div><div class="cal-status" data-status></div></div>'
      + '<button type="button" class="cal-event-toggle" data-toggle-btn>+ メモを書く</button>'
      + '</article>';
  }

  function suggestionHtml(day, s) {
    return '<article class="cal-suggest" data-path="' + escHtml(s.path) + '" data-date="' + escHtml(day.date) + '">'
      + '<div class="cal-suggest-head">✨ <span>' + escHtml(s.title) + '</span>'
      + (s.area ? '<span class="cal-suggest-area">' + escHtml(s.area) + '</span>' : '') + '</div>'
      + '<div class="cal-suggest-reason">' + escHtml(s.reason) + (s.due ? '（期限 ' + escHtml(s.due) + '）' : '') + '</div>'
      + '<div class="cal-suggest-actions">'
      + '<button type="button" class="cal-event-toggle" data-suggest-dismiss>却下</button>'
      + '<button type="button" class="cal-action cal-ai" data-suggest-accept>採用</button>'
      + '</div><div class="cal-status" data-status></div></article>';
  }

  function dayListHtml(day) {
    const events = day.events.length
      ? day.events.map(eventHtml).join('')
      : '<p class="cal-empty">予定はありません。</p>';
    const suggestions = (day.suggestions || []).map(s => suggestionHtml(day, s)).join('');
    // 定例会の日。開くとホームの確認パネルへ（ページは増やさない）
    const meeting = (day.meetings || []).length
      ? '<a class="cal-meeting" href="/?meeting=open" onclick="if (window.shukiMeetingOpen) { shukiMeetingOpen(); return false; }">' + MEETING_ICON + '<span>定例会</span><span class="cal-meeting-items">'
        + escHtml(day.meetings.join('・')) + '</span></a>' : '';
    return '<section><div class="cal-day-head">' + escHtml(dayTitle(day)) + '</div>' + meeting
      + '<div class="cal-events">' + events + '</div>'
      + (suggestions ? '<div class="cal-suggestions">' + suggestions + '</div>' : '')
      + '</section>';
  }

  // ── 予定メモの開閉・保存（今日/今週の一覧・今月の日詳細パネルの両方から使う共通ハンドラ） ──
  function bindNoteDelegation(container) {
    container.addEventListener('click', (e) => {
      const toggle = e.target.closest('[data-toggle], [data-toggle-btn]');
      if (toggle) {
        const article = toggle.closest('.cal-event');
        const form = article.querySelector('[data-form]');
        form.classList.toggle('open');
        if (form.classList.contains('open')) form.querySelector('[data-text]').focus();
        return;
      }
      const saveBtn = e.target.closest('[data-save]');
      if (saveBtn) {
        const article = saveBtn.closest('.cal-event');
        const form = article.querySelector('[data-form]');
        const textarea = form.querySelector('[data-text]');
        const status = form.querySelector('[data-status]');
        const text = textarea.value.trim();
        if (!text) { status.textContent = 'メモを書いてから保存してください。'; status.classList.add('error'); return; }
        const processing = saveBtn.dataset.save === 'ai' ? 'ai' : 'record';
        const buttons = form.querySelectorAll('.cal-action');
        buttons.forEach(b => b.disabled = true);
        status.classList.remove('error');
        status.textContent = processing === 'ai' ? 'AIに送信中…' : '記録を保存中…';
        fetch('/queue', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            name: 'memo',
            payload: {
              text, processing, source: 'calendar',
              calendar_event_id: article.dataset.eventId,
              calendar_summary: article.querySelector('.cal-event-summary').textContent,
              calendar_start: article.dataset.start || ''
            }
          })
        }).then(async (response) => {
          const result = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(result.error || ('HTTP ' + response.status));
          textarea.value = '';
          status.textContent = processing === 'ai' ? 'AIに送りました。既存の回収便で整理します。' : '記録として保存しました。';
          if (window.SFX) SFX.memo_sent();
          if (currentRange === 'month') { await loadMonth(currentAnchor); } else { await load(currentRange); }
        }).catch(() => {
          status.textContent = '保存に失敗しました。もう一度試してください。';
          status.classList.add('error');
        }).finally(() => {
          buttons.forEach(b => b.disabled = false);
        });
        return;
      }
      const acceptBtn = e.target.closest('[data-suggest-accept]');
      if (acceptBtn) {
        const card = acceptBtn.closest('.cal-suggest');
        const status = card.querySelector('[data-status]');
        const buttons = card.querySelectorAll('button');
        buttons.forEach(b => b.disabled = true);
        status.textContent = '作成中…';
        fetch('/calendar/suggest/accept', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({path: card.dataset.path, date: card.dataset.date})
        }).then(async (response) => {
          const result = await response.json().catch(() => ({}));
          if (!response.ok || !result.ok) throw new Error(result.error || ('HTTP ' + response.status));
          if (window.SFX) SFX.memo_sent();
          if (currentRange === 'month') { await loadMonth(currentAnchor); } else { await load(currentRange); }
        }).catch(() => {
          status.textContent = '作成に失敗しました。Google カレンダーへの接続を確認してください。';
          buttons.forEach(b => b.disabled = false);
        });
        return;
      }
      const dismissBtn = e.target.closest('[data-suggest-dismiss]');
      if (dismissBtn) {
        const card = dismissBtn.closest('.cal-suggest');
        const payload = {path: card.dataset.path, date: card.dataset.date};
        card.remove();
        fetch('/calendar/suggest/dismiss', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        }).catch(() => {});
        return;
      }
    });
  }
  bindNoteDelegation(daysBox);
  bindNoteDelegation(dayDetail);

  // ── 今日/今週 ──
  async function load(range) {
    currentRange = range;
    showRange();
    if (currentView === 'schedule' && window.EnglishRoutine) EnglishRoutine.mount(document.getElementById('cal-english-routine'), range !== 'today');
    if (currentView === 'results' || range === 'month') { await loadMonth(currentAnchor); return; }
    const revision = ++loadRevision;
    daysBox.innerHTML = '<p class="cal-empty">読み込み中…</p>';
    try {
      const response = await fetch('/calendar/data?range=' + encodeURIComponent(range));
      const data = await response.json();
      if (revision !== loadRevision) return;
      if (!response.ok || data.error) {
        daysBox.innerHTML = '<p class="cal-error">予定を取得できませんでした（' + escHtml(data.error || ('HTTP ' + response.status)) + '）。'
          + ' Google カレンダーへの接続を確認してください。</p>';
        return;
      }
      if (!Array.isArray(data.days) || !data.days.length) {
        daysBox.innerHTML = '<p class="cal-empty">予定はありません。</p>';
        return;
      }
      daysBox.innerHTML = data.days.map(dayListHtml).join('');
    } catch (_) {
      if (revision !== loadRevision) return;
      daysBox.innerHTML = '<p class="cal-error">予定を取得できませんでした（通信エラー）。</p>';
    }
  }

  function showRange() {
    const results = currentView === 'results';
    const isMonth = results || currentRange === 'month';
    viewButtons.forEach(b => {
      const active = b.dataset.view === currentView;
      b.setAttribute('aria-selected', String(active)); b.tabIndex = active ? 0 : -1;
    });
    document.getElementById('cal-content').setAttribute('aria-labelledby', 'cal-tab-' + currentView);
    document.querySelector('.cal-range').hidden = results;
    rangeButtons.forEach(b => {
      const active = b.dataset.range === currentRange;
      b.classList.toggle('active', active); b.setAttribute('aria-pressed', String(active));
    });
    [resultControls, resultSummary, resultHelp, resultTable].forEach(el => el.hidden = !results);
    document.getElementById('cal-fab').hidden = results;
    document.getElementById('cal-english-routine').hidden = results;
    tooltip.hidden = true;
    // [hidden]属性はCSS側の display 指定に上書きされる罠があるため、style.display を直接切り替える。
    daysBox.style.display = isMonth ? 'none' : '';
    monthNav.style.display = isMonth ? 'flex' : 'none';
    monthGrid.style.display = isMonth ? 'grid' : 'none';
    dayDetail.style.display = isMonth ? 'block' : 'none';
  }

  // ── 今月：グリッド ──
  function allDays() { return monthData ? monthData.weeks.flat() : []; }

  function currentMetric() {
    return (monthData && monthData.metrics || []).find(m => m.key === metricSelect.value);
  }

  function selectedEntries(day, metric = metricSelect.value) {
    const project = (monthData.projects || []).find(p => p.id === projectSelect.value);
    return (day.entries || []).filter(entry => {
      if (metric !== 'all' && entry.metric !== metric) return false;
      if (!project) return true;
      if (entry.metric === 'done' || entry.metric === 'created') return entry.parent === project.id;
      const areas = Array.isArray(entry.areas) ? entry.areas : [entry.areas];
      return areas.some(a => (project.area || []).includes(a));
    });
  }

  function resultCount(day) {
    // session/turn have no vault-file entries to count (data comes from transcripts, not
    // vault notes) — read the server-computed per-day count directly instead.
    if (NO_ENTRY_METRICS.includes(metricSelect.value)) {
      const m = currentMetric();
      return (m && m.days && m.days[day.date]) || 0;
    }
    return selectedEntries(day).length;
  }

  function resultLevel(day) {
    const n = resultCount(day), m = currentMetric();
    return n ? Math.min(4, 1 + (m ? m.thresholds : []).filter(t => n > t).length) : 0;
  }

  function syncUrl() {
    const url = new URL(location.href);
    if (currentView === 'results') url.searchParams.set('view', 'results'); else url.searchParams.delete('view');
    if (currentRange !== 'month') url.searchParams.set('range', currentRange); else url.searchParams.delete('range');
    if (currentAnchor) url.searchParams.set('anchor', currentAnchor);
    if (selectedDate) url.searchParams.set('date', selectedDate);
    history.replaceState(history.state, '', url);
  }

  function cellHtml(day) {
    const results = currentView === 'results';
    const events = day.events || [];
    const n = results ? resultCount(day) : events.length;
    const dots = events.slice(0, 6).map(() => '<span class="cal-cell-dot"></span>').join('');
    const more = events.length > 6 ? '<span class="cal-cell-more">+' + (events.length - 6) + '</span>' : '';
    const suggestDot = (day.suggestions && day.suggestions.length) ? '<span class="cal-cell-dot-suggest"></span>' : '';
    const classes = ['cal-cell'];
    if (!day.in_month) classes.push('out-month');
    if (day.is_today) classes.push('is-today');
    if (selectedDate === day.date) classes.push('selected');
    if (results) classes.push('results-cell', 'l' + resultLevel(day));
    if (day.is_future) classes.push('is-future');
    const label = day.date + (day.is_today ? ' · Today' : '') + (results
      ? (day.is_future ? ' · Future date' : ' · ' + METRIC_LABELS[metricSelect.value] + ': ' + plural(n, 'record'))
      : ' · ' + plural(n, 'scheduled event') + ((day.meetings || []).length ? ' · 定例会: ' + day.meetings.join('・') : ''));
    return '<button type="button" class="' + classes.join(' ') + '" data-date="' + escHtml(day.date)
      + '" data-tooltip="' + escHtml(label) + '" aria-label="' + escHtml(label)
      + '" aria-pressed="' + (selectedDate === day.date) + '"' + (day.is_today ? ' aria-current="date"' : '') + '>'
      + '<span class="cal-cell-daynum">' + day.day_num + '</span>'
      + (!results && (day.meetings || []).length ? '<span class="cal-cell-meeting" title="定例会">' + MEETING_ICON + '</span>' : '')
      + (results ? (n ? '<span class="cal-cell-count">' + n + '</span>' : '')
        : ((events.length || suggestDot) ? '<span class="cal-cell-dots">' + dots + more + suggestDot + '</span>' : ''))
      + '</button>';
  }

  function renderMonthGrid() {
    if (!monthData) return;
    monthLabel.textContent = monthTitle(monthData.anchor, monthData.month_label);
    const head = WEEKDAYS.map(w => '<div class="cal-grid-head">' + w + '</div>').join('');
    monthGrid.innerHTML = head + allDays().map(cellHtml).join('');
    if (currentView === 'results') renderResultSummary();
    renderDayDetail();
  }

  function entryHtml(entry) {
    const areas = Array.isArray(entry.areas) ? entry.areas : [entry.areas];
    return '<article class="cal-result-entry"><div class="cal-result-row">'
      + '<span class="cal-result-title">' + escHtml(entry.title) + '</span>'
      + '<span class="cal-result-tag">' + escHtml(areas.filter(Boolean).join(' · ')) + '</span>'
      + (entry.is_estimated ? '<span class="cal-result-tag" title="Date inferred from the note or creation date">Estimated</span>' : '')
      + '<button type="button" data-result-preview="' + escHtml(entry.path) + '" aria-expanded="false">View</button></div>'
      + (entry.mood ? '<p class="cal-result-extra">Mood: ' + escHtml(entry.mood) + '</p>' : '')
      + (entry.insight ? '<p class="cal-result-extra">' + escHtml(entry.insight) + '</p>' : '')
      + '<div class="cal-result-preview" hidden></div></article>';
  }

  function renderDayDetail() {
    const day = allDays().find(d => d.date === selectedDate);
    if (!day) { dayDetail.innerHTML = ''; return; }
    if (currentView !== 'results') { dayDetail.innerHTML = dayListHtml(day); return; }
    if (NO_ENTRY_METRICS.includes(metricSelect.value)) {
      // No vault files to list for session/turn — show the count only, not a (misleading) empty list.
      const n = resultCount(day);
      dayDetail.innerHTML = '<section><div class="cal-day-head">' + escHtml(dayTitle(day)) + ' · '
        + (day.is_future ? 'Future date' : plural(n, METRIC_LABELS[metricSelect.value].toLowerCase().replace(/s$/, '')))
        + '</div><p class="cal-empty">' + (day.is_future ? 'Results will appear here when activity is recorded.'
          : (n ? 'Counted from Claude Code and Codex transcripts; scheduled runs excluded. No per-record detail to show.' : 'No recorded activity for this day.'))
        + '</p></section>';
      return;
    }
    const entries = selectedEntries(day);
    let html = '<section><div class="cal-day-head">' + escHtml(dayTitle(day)) + ' · '
      + (day.is_future ? 'Future date' : plural(entries.length, 'record')) + '</div>';
    if (day.is_future) html += '<p class="cal-empty">Results will appear here when activity is recorded.</p>';
    else if (!entries.length) html += '<p class="cal-empty">No recorded activity for this day and filter.</p>';
    for (const key of ['done', 'log', 'created', 'knowledge']) {
      const group = entries.filter(e => e.metric === key);
      if (group.length) html += '<section class="cal-result-section"><h3>' + METRIC_LABELS[key] + ' · ' + group.length
        + '</h3>' + group.map(entryHtml).join('') + '</section>';
    }
    dayDetail.innerHTML = html + '</section>';
  }

  function dateButton(day) {
    return '<button type="button" data-result-date="' + escHtml(day.date) + '">' + escHtml(day.date) + '</button>';
  }

  function renderResultSummary() {
    const m = currentMetric();
    const days = allDays().filter(d => d.in_month && !d.is_future);
    const total = days.reduce((sum, d) => sum + resultCount(d), 0);
    const active = days.filter(d => resultCount(d)).length;
    const legend = '<span class="cal-legend" aria-label="Activity intensity, less to more">Less '
      + [0,1,2,3,4].map(level => '<span class="cal-legend-mark" data-level="' + level + '" aria-hidden="true"></span>').join('') + ' More</span>';
    resultSummary.innerHTML = '<strong>' + plural(total, 'record') + ' this month</strong><span>' + plural(active, 'active day') + '</span>'
      + (m && !projectSelect.value ? '<span>Streak: ' + m.current_streak + ' days · Best: ' + m.max_streak + '</span>' : '') + legend;
    resultHelp.textContent = METRIC_HELP[metricSelect.value] + ' Colors stay comparable as you move between months.'
      + (projectSelect.value ? ' Logs and knowledge are matched by project areas; tasks by their parent project.' : '');
    const keys = ['done', 'log', 'created', 'knowledge'];
    let table = '<table><caption>Daily activity in ' + escHtml(monthTitle(monthData.anchor, monthData.month_label)) + '</caption><thead><tr><th scope="col">Date</th>'
      + ['all', ...keys].map(k => '<th scope="col">' + METRIC_LABELS[k] + '</th>').join('') + '</tr></thead><tbody>';
    table += days.map(d => {
      const counts = selectedEntries(d, 'all');
      return '<tr><td>' + dateButton(d) + '</td><td>' + counts.length + '</td>'
        + keys.map(k => '<td>' + counts.filter(e => e.metric === k).length + '</td>').join('') + '</tr>';
    }).join('') + '</tbody></table>';
    const rank = days.filter(d => resultCount(d)).sort((a, b) => resultCount(b) - resultCount(a) || b.date.localeCompare(a.date)).slice(0, 10);
    if (rank.length) table += '<table><caption>Top activity days this month · ' + METRIC_LABELS[metricSelect.value]
      + '</caption><thead><tr><th scope="col">Date</th><th scope="col">Rank</th><th scope="col">Records</th></tr></thead><tbody>'
      + rank.map((d, i) => '<tr><td>' + dateButton(d) + '</td><td>' + (i + 1) + '</td><td>' + resultCount(d) + '</td></tr>').join('') + '</tbody></table>';
    if (m && m.density && !projectSelect.value) {
      const dense = days.filter(d => m.density[d.date]).sort((a,b) => m.density[b.date].max_session - m.density[a.date].max_session).slice(0,10);
      if (dense.length) table += '<table><caption>Completion density · recorded completion times only</caption><thead><tr><th scope="col">Date</th><th scope="col">Session</th></tr></thead><tbody>'
        + dense.map(d => '<tr><td>' + dateButton(d) + '</td><td>' + m.density[d.date].max_session + ' records / '
          + m.density[d.date].span_min + ' min</td></tr>').join('') + '</tbody></table>';
      const t = m.timeliness;
      const known = t && t.early + t.on_time + t.late;
      if (known) table += '<p class="cal-result-help">All-time deadline timing (' + known + ' confirmed completions): '
        + Math.round(t.early / known * 100) + '% early · ' + Math.round(t.on_time / known * 100) + '% on time · '
        + Math.round(t.late / known * 100) + '% late.</p>';
      const se = m.schedule_exec;
      if (se) table += '<p class="cal-result-help">Latest schedule execution measurement: ' + Math.round(se.rate * 100)
        + '% (' + se.matched + '/' + se.total_tagged + ') · ' + escHtml(se.generated.slice(0, 10)) + '.</p>';
    }
    document.getElementById('cal-result-table-body').innerHTML = table;
  }

  async function loadMonth(anchor) {
    const revision = ++loadRevision;
    const view = currentView;
    currentAnchor = anchor || todayIso().slice(0, 7);
    monthGrid.setAttribute('aria-busy', 'true');
    resultControls.inert = true;
    tooltip.hidden = true;
    if (!monthData) monthGrid.innerHTML = '<p class="cal-empty">Loading…</p>';
    try {
      const endpoint = view === 'results' ? '/calendar/results?' : '/calendar/data?range=month&';
      const response = await fetch(endpoint + 'anchor=' + encodeURIComponent(currentAnchor));
      const data = await response.json();
      if (revision !== loadRevision) return;
      if (!response.ok || data.error || !data.weeks) {
        throw new Error(data.error || ('HTTP ' + response.status));
      }
      monthData = data;
      currentAnchor = data.anchor;
      const days = allDays();
      if (!selectedDate || !days.some(d => d.date === selectedDate)
          || (loadedAnchor && loadedAnchor !== data.anchor && selectedDate.slice(0, 7) !== data.anchor)) {
        const dayNum = Math.max(1, Number((selectedDate || todayIso()).slice(8)) || 1);
        const inMonth = days.filter(d => d.in_month);
        const todayCell = inMonth.find(d => d.is_today);
        selectedDate = todayCell ? todayCell.date : inMonth[Math.min(dayNum, inMonth.length) - 1].date;
      }
      loadedAnchor = data.anchor;
      if (view === 'results') {
        const selected = projectSelect.value;
        projectSelect.innerHTML = '<option value="">All projects</option>' + (data.projects || []).slice()
          .sort((a,b) => a.title.localeCompare(b.title)).map(p => '<option value="' + escHtml(p.id) + '">' + escHtml(p.title) + '</option>').join('');
        projectSelect.value = (data.projects || []).some(p => p.id === selected) ? selected : '';
      }
      renderMonthGrid();
      syncUrl();
    } catch (err) {
      if (revision !== loadRevision) return;
      monthData = null;
      monthGrid.innerHTML = '';
      resultSummary.textContent = ''; resultHelp.textContent = '';
      document.getElementById('cal-result-table-body').textContent = '';
      dayDetail.innerHTML = '<p class="cal-error">Could not load ' + (view === 'results' ? 'results' : 'schedule')
        + ' (' + escHtml(String(err.message)) + '). <button type="button" data-retry>Retry</button></p>';
    } finally {
      if (revision === loadRevision) {
        monthGrid.setAttribute('aria-busy', 'false'); resultControls.inert = false;
      }
    }
  }

  rangeButtons.forEach(b => b.addEventListener('click', () => {
    if (b.dataset.range !== 'month') { selectedDate = todayIso(); currentAnchor = selectedDate.slice(0, 7); }
    load(b.dataset.range); syncUrl();
  }));
  viewButtons.forEach(b => b.addEventListener('click', () => {
    if (b.dataset.view === currentView) return;
    currentView = b.dataset.view; monthData = null;
    // Results is month-only; keep its month and day in Schedule unless the selection is still today.
    if (currentView === 'schedule' && selectedDate && selectedDate !== todayIso()) currentRange = 'month';
    resultSummary.textContent = ''; resultHelp.textContent = ''; dayDetail.innerHTML = '';
    load(currentRange);
  }));
  document.querySelector('.cal-view-tabs').addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    const index = viewButtons.indexOf(document.activeElement);
    const next = e.key === 'Home' ? 0 : e.key === 'End' ? 1 : (index + 1) % 2;
    viewButtons[next].click(); viewButtons[next].focus();
  });
  [metricSelect, projectSelect].forEach(el => el.addEventListener('change', () => {
    tooltip.hidden = true; if (monthData) renderMonthGrid();
  }));

  monthNav.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-month-nav]');
    if (!btn) return;
    const delta = parseInt(btn.dataset.monthNav, 10);
    if (delta === 0) { selectedDate = todayIso(); loadMonth(null); return; }
    const base = currentAnchor || todayIso().slice(0, 7);
    let [y, m] = (base || '').split('-').map(Number);
    if (!y || !m) { loadMonth(null); return; }
    m += delta;
    if (m < 1) { m = 12; y -= 1; } else if (m > 12) { m = 1; y += 1; }
    loadMonth(y + '-' + String(m).padStart(2, '0'));
  });

  monthGrid.addEventListener('click', (e) => {
    const cell = e.target.closest('.cal-cell');
    if (!cell) return;
    selectedDate = cell.dataset.date;
    tooltip.hidden = true;
    renderMonthGrid();
    syncUrl();
    monthGrid.querySelector('[data-date="' + selectedDate + '"]').focus({preventScroll:true});
  });
  monthGrid.addEventListener('keydown', e => {
    const cell = e.target.closest('.cal-cell');
    if (!cell) return;
    const days = allDays(), index = days.findIndex(d => d.date === cell.dataset.date);
    const offsets = {ArrowLeft:-1, ArrowRight:1, ArrowUp:-7, ArrowDown:7, Home:-(index % 7), End:6-(index % 7)};
    if (!(e.key in offsets)) return;
    e.preventDefault();
    const day = days[index + offsets[e.key]];
    if (day) monthGrid.querySelector('[data-date="' + day.date + '"]').focus();
  });
  function showTooltip(cell) {
    if (!cell) return;
    tooltip.textContent = cell.dataset.tooltip; tooltip.hidden = false;
    const rect = cell.getBoundingClientRect(), box = tooltip.getBoundingClientRect();
    tooltip.style.left = Math.max(8, Math.min(rect.left, innerWidth - box.width - 8)) + 'px';
    tooltip.style.top = Math.max(8, rect.bottom + box.height + 8 > innerHeight ? rect.top - box.height - 6 : rect.bottom + 6) + 'px';
  }
  monthGrid.addEventListener('pointerover', e => { if (e.pointerType !== 'touch') showTooltip(e.target.closest('.cal-cell')); });
  monthGrid.addEventListener('pointerleave', () => tooltip.hidden = true);
  monthGrid.addEventListener('pointerdown', e => { lastPointer = e.pointerType; });
  monthGrid.addEventListener('keydown', () => { lastPointer = 'keyboard'; }, true);
  monthGrid.addEventListener('focusin', e => { if (lastPointer !== 'touch') showTooltip(e.target.closest('.cal-cell')); });
  monthGrid.addEventListener('focusout', () => tooltip.hidden = true);
  document.addEventListener('scroll', () => tooltip.hidden = true, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') tooltip.hidden = true; });

  resultTable.addEventListener('click', e => {
    const button = e.target.closest('[data-result-date]');
    if (!button || !monthData) return;
    selectedDate = button.dataset.resultDate; renderMonthGrid(); syncUrl();
    dayDetail.scrollIntoView({block:'nearest'});
  });
  dayDetail.addEventListener('click', async e => {
    if (e.target.closest('[data-retry]')) { loadMonth(currentAnchor); return; }
    const button = e.target.closest('[data-result-preview]');
    if (!button) return;
    const preview = button.closest('.cal-result-entry').querySelector('.cal-result-preview');
    preview.hidden = !preview.hidden;
    button.setAttribute('aria-expanded', String(!preview.hidden));
    if (preview.hidden || preview.dataset.loaded) return;
    preview.textContent = 'Loading…'; button.disabled = true;
    try {
      const response = await fetch('/files/preview?p=' + encodeURIComponent(button.dataset.resultPreview));
      if (!response.ok) throw new Error('HTTP ' + response.status);
      preview.innerHTML = await response.text(); preview.dataset.loaded = '1';
    } catch (err) { preview.textContent = 'Could not load preview (' + err.message + ').'; }
    finally { button.disabled = false; }
  });

  // ── ＋ 予定を追加 ──
  const fab = document.getElementById('cal-fab');
  const backdrop = document.getElementById('cal-modal-backdrop');
  const newSummary = document.getElementById('cal-new-summary');
  const newDate = document.getElementById('cal-new-date');
  const newAllday = document.getElementById('cal-new-allday');
  const timeRow = document.getElementById('cal-new-time-row');
  const newStart = document.getElementById('cal-new-start');
  const newEnd = document.getElementById('cal-new-end');
  const newLocation = document.getElementById('cal-new-location');
  const newDesc = document.getElementById('cal-new-desc');
  const modalStatus = document.getElementById('cal-modal-status');
  const modalSubmit = document.getElementById('cal-modal-submit');
  const modalCancel = document.getElementById('cal-modal-cancel');

  function todayIso() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function openModal() {
    newSummary.value = ''; newLocation.value = ''; newDesc.value = '';
    newDate.value = (currentRange === 'month' && selectedDate) ? selectedDate : todayIso();
    newAllday.checked = true;
    timeRow.style.display = 'none';
    newStart.value = ''; newEnd.value = '';
    modalStatus.textContent = '';
    backdrop.classList.add('open');
    window.setTimeout(() => newSummary.focus(), 30);
  }
  function closeModal() { backdrop.classList.remove('open'); }

  fab.addEventListener('click', openModal);
  modalCancel.addEventListener('click', closeModal);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeModal(); });
  newAllday.addEventListener('change', () => { timeRow.style.display = newAllday.checked ? 'none' : 'flex'; });

  modalSubmit.addEventListener('click', async () => {
    const summary = newSummary.value.trim();
    const eventDate = newDate.value;
    if (!summary) { modalStatus.textContent = '予定名を入力してください。'; return; }
    if (!eventDate) { modalStatus.textContent = '日付を選んでください。'; return; }
    const allDay = newAllday.checked;
    if (!allDay && (!newStart.value || !newEnd.value)) {
      modalStatus.textContent = '開始・終了時刻を入力してください。'; return;
    }
    modalSubmit.disabled = true;
    modalStatus.textContent = '作成中…';
    try {
      const response = await fetch('/calendar/event', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          summary, date: eventDate, all_day: allDay,
          start_time: allDay ? '' : newStart.value, end_time: allDay ? '' : newEnd.value,
          location: newLocation.value.trim(), description: newDesc.value.trim()
        })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || ('HTTP ' + response.status));
      closeModal();
      if (window.SFX) SFX.memo_sent();
      if (currentRange === 'month') { await loadMonth(currentAnchor); } else { await load(currentRange); }
    } catch (err) {
      modalStatus.textContent = '作成に失敗しました。Google カレンダーへの接続を確認してください。';
    } finally {
      modalSubmit.disabled = false;
    }
  });

  load(currentRange);
})();
</script>
</body></html>"""


def render_calendar_html():
    """共通シェルをリクエストごとに差し替えて返す。"""
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        shuki_i18n.tt_html(PAGE, ctx="calendar"), "calendar", dashboard_icons.nav_icon_svg("calendar", 19) + " " + t("カレンダー"))
