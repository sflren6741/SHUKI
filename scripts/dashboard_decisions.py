#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_decisions.py — ⚖️ 決裁カードページ（dashboard_server.py の /decisions ページ）
(2026-08-28 新設。従来ホームの決裁パネルは全件が縦に並んで圧迫感があり選びづらい、という
ユーザーのフィードバックを受け、クイズと同じ「1件ずつカードで提示→次へ」の器に作り直した専用ページ。
2026-09-09 に情報要求もこのページへ統合し、カードごとに yes_no / choice / text を切り替える)

データは decisions.py（99_System/decisions/open.json）が正。このモジュールは表示と
POST /queue（既存の decision_results 経路。dashboard_server.py 側で decisions.apply_choice
を呼ぶ処理は既に実装済み）を1件ずつ消化するUIだけを持つ。カードの応答型は、yes_no（既存の
承認/却下）、choice（A/B/C等の選択。合わない時は「その他（自由に書く）」で回答できる）、text（不足情報の自由記述）、datetime（日付＋開始時刻の選択）の4つ。ホームの決裁パネル
（縦積み全件表示）は撤去し、件数バッジ＋このページへのリンクだけに縮小した。
"""
import dashboard_ui  # noqa: E402
import dashboard_chat  # noqa: E402
import dashboard_icons  # noqa: E402
import shuki_i18n  # noqa: E402
from shuki_i18n import tt  # noqa: E402

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title>決裁</title>
<style>
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg);
    font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  header { flex-shrink:0; }
  main { flex:1; padding:14px 16px 24px; max-width:560px; width:100%; margin:0 auto; }
  #progress { font-size:.76rem; color:var(--muted); margin-bottom:10px; }
  #loading, #empty-state { display:flex; align-items:center; justify-content:center;
    color:var(--muted); gap:10px; font-size:.9rem; padding:80px 20px; text-align:center; flex-direction:column; }
  .spin { animation:spin 1.2s linear infinite; display:inline-block; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .card { background:var(--card); border:1px solid var(--line); border-radius:16px;
    padding:22px 20px; width:100%; transition:opacity .25s ease, transform .25s ease; }
  .card.leaving { opacity:0; transform:translateX(30px); }
  .card.entering { opacity:0; transform:translateX(-16px); }
  .c-q { font-size:1.05rem; font-weight:bold; line-height:1.5; }
  .c-ctx { font-size:.84rem; color:var(--muted); margin-top:8px; line-height:1.6; }
  .c-choices { font-size:.8rem; color:var(--muted); margin-top:12px; line-height:1.6;
    border-top:1px solid var(--line); padding-top:10px; }
  .c-yes { color:var(--teal); font-weight:bold; margin-right:3px; }
  .c-no { color:var(--red); font-weight:bold; margin:0 3px 0 10px; }
  .c-btns { display:grid; grid-template-columns:repeat(auto-fit, minmax(76px, 1fr)); gap:8px; margin-top:18px; }
  .cbtn { border:1px solid var(--line); border-radius:12px;
    padding:10px 12px; color:var(--muted); background:var(--bg); cursor:pointer;
    font-size:.84rem; font-family:inherit; display:inline-flex; align-items:center;
    justify-content:center; gap:5px; min-height:40px; }
  .cbtn:hover { border-color:var(--accent); color:var(--fg); }
  .cbtn.sel { border-color:var(--teal); color:var(--teal); font-weight:bold; }
  .cbtn.errflash { border-color:var(--red); color:var(--red); }
  .c-comment-box { display:flex; gap:6px; margin-top:12px; width:100%; }
  .c-comment-box textarea { flex:1; background:var(--bg); border:1px solid var(--line); border-radius:8px;
    color:var(--fg); font-family:inherit; font-size:.84rem; padding:8px; resize:vertical; }
  .c-comment-box textarea:focus { outline:none; border-color:var(--accent); }
  .c-answer-box { margin-top:16px; }
  .c-answer-box textarea { width:100%; background:var(--bg); border:1px solid var(--line); border-radius:8px;
    color:var(--fg); font-family:inherit; font-size:.88rem; padding:10px; resize:vertical; min-height:70px; }
  .c-answer-box textarea:focus { outline:none; border-color:var(--accent); }
  .c-datetime-box { display:grid; grid-template-columns:1.15fr .85fr; gap:10px; margin-top:16px; }
  .c-datetime-field { display:grid; gap:6px; color:var(--muted); font-size:.78rem; }
  .c-datetime-field input { width:100%; min-height:40px; padding:8px 10px; border:1px solid var(--line);
    border-radius:8px; background:var(--bg); color:var(--fg); font:inherit; color-scheme:light dark; }
  .c-datetime-field input:focus { outline:none; border-color:var(--accent); }
  .c-options { display:grid; gap:8px; margin-top:18px; }
  .c-option { width:100%; border:1px solid var(--line); border-radius:12px; padding:12px 14px;
    color:var(--fg); background:var(--bg); cursor:pointer; font-size:.88rem; font-family:inherit;
    text-align:left; line-height:1.45; }
  .c-option:hover { border-color:var(--teal); color:var(--teal); }
  .c-option-detail { display:block; color:var(--muted); font-size:.78rem; margin-top:3px; }
  .c-option.c-other { color:var(--muted); border-style:dashed; display:flex; align-items:center; gap:6px; }
  .c-option.c-other[aria-expanded="true"] { border-style:solid; border-color:var(--accent); color:var(--fg); }
  .c-answer-box[hidden] { display:none; }
  .c-src { text-decoration:none; opacity:.6; font-size:.8rem; display:inline-flex; margin-left:6px; }
  .bulk-status { min-height:1.2em; margin:0 0 10px; color:var(--muted); font-size:.76rem; }
  .hbtn:disabled { opacity:.45; cursor:not-allowed; }
  @media (max-width:360px) { .c-datetime-box { grid-template-columns:1fr; } }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head>
<body>

<!--SHUKI_PAGE_HEADER-->

<main>
  <div id="progress" style="display:none;"></div>
  <div id="bulk-status" class="bulk-status" aria-live="polite"></div>
  <div id="loading"><span class="spin">""" + dashboard_icons.ui_icon_svg("loading", 15) + """</span> 読み込み中…</div>
  <div id="empty-state" style="display:none;">""" + dashboard_icons.ui_icon_svg("celebrate", 15) + """ 決裁カード待ちなし</div>
  <div id="cardwrap"></div>
</main>
<!--SHUKI_BOTTOM_NAV-->

<script>
let QUEUE = [], TOTAL = 0, DONE = 0, BULK_BUSY = false;
// 文言は esc() より前に置く（tt_js_ui は esc() の正規表現内の引用符で文字列の境界を見失い、
// それ以降の HTML 属性 placeholder を訳せないため）
const DEC_LABELS = { placeholder: '回答を書く…' };

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function init() {
  try {
    const r = await fetch('/decisions/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    QUEUE = d.items || [];
    TOTAL = QUEUE.length;
    document.getElementById('loading').style.display = 'none';
    updateBulkButton();
    renderNext(false);
  } catch(e) {
    document.getElementById('loading').textContent = '読み込みエラー: ' + e;
  }
}

function updateProgress() {
  const el = document.getElementById('progress');
  if (!TOTAL) { el.style.display = 'none'; return; }
  el.style.display = '';
  el.textContent = Math.min(DONE + 1, TOTAL) + ' / ' + TOTAL;
}

function responseType(it) {
  return it.response_type || ((it.options && it.options.length) ? 'choice' :
    ((it.yes || it.no) ? 'yes_no' : 'text'));
}

function approvalTargets() {
  /* 「承認」は yes/no だけ。choice は選択肢、text は本人の回答が必要なので
     一括処理の対象にしない。 */
  return QUEUE.filter(it => responseType(it) === 'yes_no' && (it.yes || it.no));
}

function updateBulkButton() {
  const b = document.getElementById('bulk-approve-btn');
  if (!b) return;
  const n = approvalTargets().length;
  b.disabled = BULK_BUSY || n === 0;
  b.title = n ? n + '件の承認可能なカードをまとめて処理' : '承認可能なカードはありません';
}

function setBulkStatus(text, error) {
  const el = document.getElementById('bulk-status');
  if (!el) return;
  if (text.startsWith('✓ ')) shukiSetIconLabel(el, error ? 'warn' : 'check', text.slice(2));
  else el.textContent = text;
  el.style.color = error ? 'var(--danger)' : '';
}

function renderNext(animateIn) {
  const wrap = document.getElementById('cardwrap');
  const empty = document.getElementById('empty-state');
  updateProgress();
  if (!QUEUE.length) {
    wrap.innerHTML = '';
    empty.style.display = 'flex';
    updateBulkButton();
    return;
  }
  empty.style.display = 'none';
  const it = QUEUE[0];
  wrap.innerHTML = '';
  wrap.appendChild(renderCard(it, animateIn));
  updateBulkButton();
}

function renderCard(it, animateIn) {
  const card = document.createElement('div');
  card.className = 'card' + (animateIn ? ' entering' : '');
  card.dataset.decId = it.id;
  card.dataset.decQ = it.question;
  const rt = it.response_type || ((it.options && it.options.length) ? 'choice' :
    ((it.yes || it.no) ? 'yes_no' : 'text'));
  let choices = '';
  let answerBox = '';
  let actionButtons = '';
  if (rt === 'choice' && Array.isArray(it.options) && it.options.length) {
    // 選択肢が合わない時の逃げ道として「その他（自由に書く）」を必ず添える。
    // 自由記述は既定で畳み、選択肢を主回答にする（2026-10-09 自由記述だけはきつい）。
    choices = '<div class="c-options">' + it.options.map(o => {
      const detail = o.detail ? '<span class="c-option-detail">' + esc(o.detail) + '</span>' : '';
      return '<button type="button" class="c-option" data-option="' + esc(o.id) + '">' +
        esc(o.label || o.id) + detail + '</button>';
    }).join('') +
      '<button type="button" class="c-option c-other" data-act="other" aria-expanded="false">""" + dashboard_icons.ui_icon_svg("pencil", 13) + """ その他（自由に書く）</button>' +
      '</div>';
    answerBox = '<div class="c-answer-box" hidden><textarea placeholder="' + esc(DEC_LABELS.placeholder) + '" rows="3"></textarea>' +
      '<div class="c-btns"><button type="button" class="cbtn sel" data-act="answer">""" + dashboard_icons.ui_icon_svg("check", 13) + """ 回答する</button></div></div>';
    actionButtons = '<div class="c-btns">' +
      btnHtml('保留', '""" + dashboard_icons.ui_icon_svg("pause", 12) + """') +
      btnHtml('削除', '""" + dashboard_icons.ui_icon_svg("trash", 13) + """') +
      '</div>';
  } else if (rt === 'datetime') {
    // proposed（"YYYY-MM-DD HH:MM"）があれば既定値として入れておく。
    // 空欄から2つのピッカーを操作させると「後で決める」に流れるため、
    // SHUKI 側が先に1案を置いて『そのままでよければ1クリック』にする（2026-09-23）。
    const prop = (it.proposed || '').trim();
    const pd = prop ? prop.split(' ')[0] : '';
    const pt = prop ? (prop.split(' ')[1] || '') : '';
    const propNote = prop
      ? '<div class="c-ctx">提案: ' + esc(prop) + '（変えたければ書き換えてください）</div>' : '';
    answerBox = propNote + '<div class="c-datetime-box">' +
      '<label class="c-datetime-field">日付<input type="date" data-datetime="date" required' +
        (pd ? ' value="' + esc(pd) + '"' : '') + '></label>' +
      '<label class="c-datetime-field">開始時刻<input type="time" data-datetime="time" step="60" required' +
        (pt ? ' value="' + esc(pt) + '"' : '') + '></label>' +
      '</div>';
    actionButtons = '<div class="c-btns">' +
      '<button type="button" class="cbtn sel" data-act="answer">' +
      '""" + dashboard_icons.ui_icon_svg("check", 13) + """ 日時を確定</button>' +
      btnHtml('保留', '""" + dashboard_icons.ui_icon_svg("pause", 12) + """') +
      btnHtml('削除', '""" + dashboard_icons.ui_icon_svg("trash", 13) + """') +
      '</div>';
  } else if (rt === 'text') {
    answerBox = '<div class="c-answer-box"><textarea placeholder="' + esc(DEC_LABELS.placeholder) + '" rows="3"></textarea></div>';
    actionButtons = '<div class="c-btns">' +
      '<button type="button" class="cbtn sel" data-act="answer">""" + dashboard_icons.ui_icon_svg("check", 13) + """ 回答する</button>' +
      btnHtml('保留', '""" + dashboard_icons.ui_icon_svg("pause", 12) + """') +
      btnHtml('削除', '""" + dashboard_icons.ui_icon_svg("trash", 13) + """') +
      '</div>';
  } else if (it.yes || it.no) {
    choices = '<div class="c-choices"><span class="c-yes">YES</span>' + esc(it.yes) +
      '<span class="c-no">NO</span>' + esc(it.no) + '</div>';
    actionButtons = '<div class="c-btns">' +
      btnHtml('承認', '""" + dashboard_icons.ui_icon_svg("check", 13) + """') +
      btnHtml('却下', '""" + dashboard_icons.ui_icon_svg("cross", 13) + """') +
      btnHtml('保留', '""" + dashboard_icons.ui_icon_svg("pause", 12) + """') +
      btnHtml('コメント', '""" + dashboard_icons.ui_icon_svg("comment", 13) + """') +
      btnHtml('削除', '""" + dashboard_icons.ui_icon_svg("trash", 13) + """') +
      '</div>';
  } else {
    answerBox = '<div class="c-answer-box"><textarea placeholder="' + esc(DEC_LABELS.placeholder) + '" rows="3"></textarea></div>';
    actionButtons = '<div class="c-btns">' +
      '<button type="button" class="cbtn sel" data-act="answer">""" + dashboard_icons.ui_icon_svg("check", 13) + """ 回答する</button>' +
      btnHtml('保留', '""" + dashboard_icons.ui_icon_svg("pause", 12) + """') +
      btnHtml('削除', '""" + dashboard_icons.ui_icon_svg("trash", 13) + """') +
      '</div>';
  }
  const link = it.task_path
    ? '<span class="c-src" title="' + esc(it.task_path) + '">""" + dashboard_icons.ui_icon_svg("doc", 13) + """</span>'
    : '';
  card.innerHTML =
    '<div class="c-q">' + esc(it.question) + link + '</div>' +
    (it.context ? '<div class="c-ctx">' + esc(it.context) + '</div>' : '') +
    choices +
    answerBox + actionButtons;
  card.querySelectorAll('[data-option]').forEach(b => {
    b.onclick = () => sendDecision(card, b, '選択', '', b.dataset.option);
  });
  const otherBtn = card.querySelector('[data-act="other"]');
  if (otherBtn) {
    otherBtn.onclick = () => {
      const box = card.querySelector('.c-answer-box');
      box.hidden = !box.hidden;
      otherBtn.setAttribute('aria-expanded', box.hidden ? 'false' : 'true');
      if (!box.hidden) box.querySelector('textarea').focus();
    };
  }
  const answerBtn = card.querySelector('[data-act="answer"]');
  if (answerBtn) {
    const ta = card.querySelector('textarea');
    const dateInput = card.querySelector('[data-datetime="date"]');
    const timeInput = card.querySelector('[data-datetime="time"]');
    answerBtn.onclick = () => {
      let text = '';
      if (rt === 'datetime') {
        if (dateInput && !dateInput.reportValidity()) return;
        if (timeInput && !timeInput.reportValidity()) return;
        const selectedDate = dateInput ? dateInput.value : '';
        const selectedTime = timeInput ? timeInput.value : '';
        if (!selectedDate || !selectedTime) return;
        text = selectedDate + ' ' + selectedTime;
      } else {
        text = ta ? ta.value.trim() : '';
        if (!text) { if (ta) ta.focus(); return; }
      }
      sendDecision(card, answerBtn, '回答', text, '');
    };
  }
  card.querySelectorAll('.cbtn[data-choice]').forEach(b => {
    b.onclick = () => {
      const code = CHOICE_CODE[b.dataset.choice] || b.dataset.choice;
      if (code === 'comment') { toggleCommentBox(card); return; }
      sendDecision(card, b, b.dataset.choice, '', '');
    };
  });
  requestAnimationFrame(() => card.classList.remove('entering'));
  return card;
}

function btnHtml(choice, icon) {
  return '<button type="button" class="cbtn" data-choice="' + choice + '">' + icon + ' ' + choice + '</button>';
}

function toggleCommentBox(card) {
  const existing = card.querySelector('.c-comment-box');
  if (existing) { existing.remove(); return; }
  const box = document.createElement('div');
  box.className = 'c-comment-box';
  box.innerHTML = '<textarea placeholder="追加コメント・要望…" rows="2"></textarea>' +
    '<button type="button" class="cbtn csend">送信</button>';
  card.appendChild(box);
  const ta = box.querySelector('textarea');
  ta.focus();
  box.querySelector('.csend').onclick = () => {
    const text = ta.value.trim();
    if (!text) { box.remove(); return; }
    sendDecision(card, box.querySelector('.csend'), 'コメント', text);
  };
}

// 表示ラベルは tt() で言語ごとに翻訳されるが、サーバーに送るコードは言語非依存の
// 固定値でなければならない（翻訳後の文字列が decisions.py の日本語比較と食い違い、
// 押しても何も起きず同じ決裁が再表示され続けるバグの原因だった・2026-09-14 修正）。
const CHOICE_CODE = { '承認':'approve', '却下':'reject', '保留':'hold',
  'コメント':'comment', '削除':'delete', '選択':'select', '回答':'answer' };

function sendDecision(card, btn, choice, comment, selectedOption) {
  const code = CHOICE_CODE[choice] || choice;
  const payload = { id: card.dataset.decId, question: card.dataset.decQ, choice: code };
  if (code === 'answer') payload.answer = comment;
  else if (comment) payload.comment = comment;
  if (selectedOption) payload.selected_option = selectedOption;
  fetch('/queue', { method: 'POST', body: JSON.stringify({ name: 'decision_results', payload }) })
    .then(r => { if (!r.ok) throw 0;
      if (window.SFX) {
        if (code === 'approve') SFX.decision_approve();
        else if (code === 'reject') SFX.decision_reject();
        else SFX.tick();
      }
      QUEUE.shift();
      DONE++;
      const wrap = document.getElementById('cardwrap');
      card.classList.add('leaving');
      setTimeout(() => { renderNext(true); }, 250);
    })
    .catch(() => { btn.classList.add('errflash');
                    setTimeout(() => btn.classList.remove('errflash'), 1500); });
}

async function bulkApprove() {
  if (BULK_BUSY) return;
  const targets = approvalTargets();
  if (!targets.length) return;
  if (!confirm(targets.length + '件の承認可能なカードをまとめて承認します。よろしいですか？')) return;

  BULK_BUSY = true;
  updateBulkButton();
  setBulkStatus('承認を処理中…');
  const approved = new Set();
  let failed = 0;
  for (const it of targets) {
    const payload = { id: it.id, question: it.question, choice: 'approve' };
    try {
      const r = await fetch('/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'decision_results', payload }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      approved.add(it.id);
    } catch (e) {
      failed++;
    }
  }

  QUEUE = QUEUE.filter(it => !approved.has(it.id));
  DONE += approved.size;
  BULK_BUSY = false;
  if (approved.size && window.SFX) SFX.decision_approve();
  updateBulkButton();
  renderNext(false);
  if (failed) {
    setBulkStatus('✓ ' + approved.size + '件を承認。' + failed + '件は失敗したため個別に確認してください', true);
  } else {
    setBulkStatus('✓ ' + approved.size + '件を承認しました');
  }
}

init();
</script>
</body></html>"""


def render_decisions_page_html():
    # tt() は静的本文に適用し、シェル（ナビ・ドック）は自前で t()/tt() 済みなので
    # hydrate 後に二重適用しない。ページ見出しの語だけ tt() を通す。
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        shuki_i18n.tt_html(PAGE, ctx="decisions"), "decisions", tt(dashboard_icons.ui_icon_svg("scale", 19) + " 決裁カード", ctx="decisions"),
        '<button class="hbtn" id="bulk-approve-btn" onclick="bulkApprove()" disabled '
        'title="承認可能なカードをまとめて処理">'
        + dashboard_icons.ui_icon_svg("check", 13) + " 一括承認</button>")
