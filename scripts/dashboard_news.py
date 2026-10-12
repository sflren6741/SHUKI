#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_news.py — 📰 ニュース（dashboard_server.py の /news ページ）

news_fetch.py（日次スケジューラ Claude-NewsDigest）が生成する
99_System/news/<date>.json（当日分の選定済みニュース）をそのまま表示するだけの
読み物ページ。新規／既読を切り替え、評価とは独立した既読状態を保存する。
カードのリンクは常に target="_blank" で外部サイトへ直接遷移する。

データは /news/data から取得。news_store が最新号と機械ゾーンの既読状態を読む。
サーバーは vault 本体を書かない。
"""
import dashboard_ui  # noqa: E402  (nav_html/bottom_nav_html/PWA_HEAD/RESPONSIVE_CSS を再利用)
import dashboard_chat  # noqa: E402  (💬 全ページ共通の対話ドック)
import dashboard_icons  # noqa: E402  (線アイコンSVG)
import shuki_i18n  # noqa: E402
from shuki_i18n import tt  # noqa: E402  (表示言語。lang=ja なら素通し)

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title> ニュース</title>
<style>
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg);
    font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  header { flex-shrink:0; }
  .filter-bar { display:flex; align-items:center; column-gap:8px; row-gap:14px; padding:8px 16px;
    border-bottom:1px solid var(--line); flex-shrink:0; flex-wrap:wrap; }
  /* §6.2: compact filter tabs (32px); use vertical hit expansion so neighboring tabs stay distinct. */
  .news-tab { position:relative; box-sizing:border-box; height:32px; min-height:32px;
    font:inherit; font-size:.8rem; color:var(--muted); border:1px solid var(--line);
    border-radius:20px; padding:0 10px; cursor:pointer; background:var(--card);
    display:flex; align-items:center; gap:4px; white-space:nowrap; }
  .news-tab::before { content:''; position:absolute; inset:-7px 0; }
  .news-tab.active { border-color:var(--accent); color:var(--fg);
    background:color-mix(in srgb, var(--accent) 10%, var(--card)); }
  .news-tab:focus-visible, .rbtn-n:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
  #meta { font-size:.72rem; color:var(--muted); margin-left:auto; }
  main { flex:1; padding:14px 16px 24px; max-width:760px; width:100%; margin:0 auto; }
  #loading, #empty-state { display:flex; align-items:center; justify-content:center;
    color:var(--muted); gap:10px; font-size:.9rem; padding:60px 20px; text-align:center; flex-direction:column; }
  .spin { animation:spin 1.2s linear infinite; display:inline-block; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .item { background:var(--card); border:1px solid var(--line); border-radius:12px;
    margin-bottom:10px; padding:12px 14px; display:block;
    transition:opacity .25s ease, transform .25s ease; }
  .item:hover { border-color:var(--accent); }
  .item.rated .item-link { opacity:.6; }  /* 評価済み：残すが一段控えめに */
  .item-link { display:block; text-decoration:none; color:inherit; }
  .item-react { display:flex; align-items:center; flex-wrap:wrap; column-gap:6px; row-gap:14px; margin-top:9px; padding-top:9px; border-top:1px solid var(--line); }
  /* §6.2: compact article actions (32px); expand the hit area vertically only. */
  .rbtn-n { position:relative; box-sizing:border-box; height:32px; min-height:32px;
    background:none; border:1px solid var(--line); border-radius:20px; cursor:pointer;
    color:var(--muted); font-size:.74rem; padding:0 10px;
    display:inline-flex; align-items:center; gap:5px; font-family:inherit; }
  .rbtn-n::before { content:''; position:absolute; inset:-7px 0; }
  .rbtn-n:hover { color:var(--fg); border-color:var(--accent); }
  .rbtn-n.on { color:var(--fg); border-color:var(--accent); background:color-mix(in srgb, var(--accent) 10%, var(--card)); }
  .rbtn-n[data-v="read"], .read-label { margin-left:auto; }
  .rbtn-n:disabled { cursor:default; opacity:.6; }
  .read-label { color:var(--muted); font-size:.74rem; display:inline-flex; align-items:center; min-height:32px; }
  .news-error { color:var(--danger); font-size:.8rem; margin-top:8px; }
  .item-top { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
  .item-cat { font-size:.68rem; color:var(--accent); background:color-mix(in srgb, var(--accent) 10%, var(--card));
    border-radius:5px; padding:1px 7px; flex-shrink:0; }
  .item-source { font-size:.7rem; color:var(--muted); }
  .item-time { font-size:.68rem; color:var(--muted); margin-left:auto; flex-shrink:0; white-space:nowrap; }
  .item-title { font-size:.92rem; font-weight:bold; margin-top:5px; line-height:1.45; }
  .item-reason { font-size:.8rem; color:var(--muted); margin-top:5px; line-height:1.5; }
  /* ★ 確認すべき度合い（重要性×緊急性・news_fetch が 1〜3 で付ける・2026-08-13）。
     色は3段階だがカードの枠は塗らない（縁を塗ると角丸で色が中途半端に切れる）。
     大量に並んだ時に「今日どれを見るか」が一目で分かることだけが目的。 */
  .item-stars { font-size:.86rem; letter-spacing:1px; flex-shrink:0; color:var(--muted);
    line-height:1; }
  .item-stars.s3 { color:var(--accent); font-size:.95rem; }
  .item-stars.s2 { color:var(--fg); }
  .knowledge-feature { background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:14px; margin-bottom:14px; }
  .knowledge-feature-label { color:var(--accent); font-size:.7rem; font-weight:bold; }
  .knowledge-feature-title { font-size:1rem; line-height:1.45; margin-top:4px; }
  .knowledge-feature-summary { color:var(--muted); font-size:.8rem; line-height:1.5; margin-top:5px; }
  .knowledge-feature-sources { display:flex; flex-wrap:wrap; column-gap:7px; row-gap:14px; margin-top:10px; }
  .knowledge-feature-source { position:relative; box-sizing:border-box; height:32px; min-height:32px;
    color:var(--fg); background:var(--bg); border:1px solid var(--line);
    border-radius:18px; padding:0 10px; font-size:.74rem; text-decoration:none;
    display:inline-flex; align-items:center; white-space:nowrap; }
  .knowledge-feature-source::before { content:''; position:absolute; inset:-7px 0; }
  .knowledge-feature-source:hover { border-color:var(--accent); }
  .knowledge-feature-articles { margin-top:12px; }
  .knowledge-feature-articles .item:last-child { margin-bottom:0; }
  @media (max-width:700px) { .item, .knowledge-feature { padding:12px; } }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head>
<body>

<!--SHUKI_PAGE_HEADER-->

<div class="filter-bar" id="filter-bar">
  <div role="tablist" aria-label="ニュースの状態" style="display:flex;gap:8px;">
    <button type="button" id="news-tab-new" class="news-tab active" role="tab" aria-selected="true" aria-controls="news-content" data-state="new">新規</button>
    <button type="button" id="news-tab-read" class="news-tab" role="tab" aria-selected="false" aria-controls="news-content" tabindex="-1" data-state="read">既読</button>
  </div>
  <span id="meta"></span>
  <a class="news-tab" href="/news/sources" style="text-decoration:none;">登録元</a>
</div>

<main id="news-content" role="tabpanel" aria-labelledby="news-tab-new">
  <div id="loading"><span class="spin">""" + dashboard_icons.ui_icon_svg("loading", 15) + """</span> 読み込み中…</div>
  <div id="empty-state" style="display:none;"></div>
  <div id="list"></div>
  <section id="knowledge-feature" class="knowledge-feature" hidden aria-label="Weekly news related to your knowledge">
    <div class="knowledge-feature-label">This week</div>
    <h2 id="knowledge-feature-title" class="knowledge-feature-title"></h2>
    <p id="knowledge-feature-summary" class="knowledge-feature-summary"></p>
    <div id="knowledge-feature-articles" class="knowledge-feature-articles"></div>
  </section>
</main>
<!--SHUKI_BOTTOM_NAV-->

<script>
let ALL = [], ACTIVE_STATE = 'new', META_DATE = '', FEATURE = null;

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function relTime(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return Math.max(1, Math.round(diff / 60)) + '分前';
  if (diff < 86400) return Math.round(diff / 3600) + '時間前';
  return Math.round(diff / 86400) + '日前';
}

async function init() {
  try {
    const r = await fetch('/news/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    ALL = d.items || [];
    META_DATE = d.date || '';
    FEATURE = d.knowledge_feature;
    document.getElementById('loading').style.display = 'none';
    buildFilterBar();
    updateMeta();
    render();
  } catch(e) {
    document.getElementById('loading').textContent = '読み込みエラー: ' + e;
  }
}

function buildFilterBar() {
  const tabs = Array.from(document.querySelectorAll('.news-tab'));
  tabs.forEach((tab, index) => {
    tab.onclick = () => { ACTIVE_STATE = tab.dataset.state; render(); };
    tab.onkeydown = event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[1] : tabs[1 - index];
      next.click(); next.focus();
    };
  });
}

function updateChipActive() {
  document.querySelectorAll('.news-tab').forEach(el => {
    const active = el.dataset.state === ACTIVE_STATE;
    el.classList.toggle('active', active);
    el.setAttribute('aria-selected', String(active));
    el.tabIndex = active ? 0 : -1;
  });
  document.getElementById('news-content').setAttribute('aria-labelledby', 'news-tab-' + ACTIVE_STATE);
}

function inActiveTab(it) { return Boolean(it.read) === (ACTIVE_STATE === 'read'); }

function visibleItems() {
  const v = ALL.filter(inActiveTab);
  // 星の高い順（news_fetch も保存時に並べるが、stars を持たない過去データのために表示側でも）
  return v.sort((a, b) => starOf(b) - starOf(a));
}

// stars は 1〜3。付いていない過去データ（2026-08-12 以前）は 2 とみなす
function starOf(it) {
  const n = parseInt(it.stars, 10);
  return (n >= 1 && n <= 3) ? n : 2;
}
const STAR_TITLE = { 3: '今日のうちに見たほうがいい', 2: '読む価値がある', 1: '参考程度' };

// Reading and rating are separate actions.
function updateMeta() {
  const el = document.getElementById('meta');
  if (!el) return;
  el.textContent = META_DATE;
  if (META_DATE) {
    const label = document.createElement('span');
    label.textContent = '更新';
    el.append(' ', label);
  }
}

function renderKnowledgeFeature(feature) {
  const box = document.getElementById('knowledge-feature');
  const articlesEl = document.getElementById('knowledge-feature-articles');
  articlesEl.replaceChildren();
  if (!feature || feature.kind !== 'related_news' || !Array.isArray(feature.articles)) {
    box.hidden = true;
    return;
  }
  document.getElementById('knowledge-feature-title').textContent = feature.title || '';
  const range = feature.range_start && feature.range_end
    ? ' (' + feature.range_start + ' – ' + feature.range_end + ')' : '';
  document.getElementById('knowledge-feature-summary').textContent = (feature.summary || '') + range;
  feature.articles.filter(inActiveTab).forEach(article => {
    if (!article || !Array.isArray(article.sources) || !article.sources.length) return;
    let url;
    try { url = new URL(article.url); } catch(e) { return; }
    if (!['http:', 'https:'].includes(url.protocol)) return;
    const notes = document.createElement('div');
    notes.className = 'knowledge-feature-sources';
    article.sources.forEach(source => {
      const path = String((source && source.path) || '');
      if (!path.startsWith('06_Resources/Resources/') || !path.endsWith('.md')
          || path.split('/').includes('..') || path.includes(String.fromCharCode(92))) return;
      const link = document.createElement('a');
      link.className = 'knowledge-feature-source';
      link.href = '/files?p=' + encodeURIComponent(path);
      link.textContent = 'Related note: ' + String(source.title || path.split('/').pop());
      notes.appendChild(link);
    });
    if (!notes.childElementCount) return;
    const card = document.createElement('article');
    card.className = 'item' + (article.rating ? ' rated' : '');
    const link = document.createElement('a');
    link.className = 'item-link';
    link.href = url.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    const meta = document.createElement('div');
    meta.className = 'item-source';
    meta.textContent = String(article.source || '') + ' · ' + relTime(article.published);
    const title = document.createElement('h3');
    title.className = 'item-title';
    title.textContent = String(article.title || '');
    const reason = document.createElement('p');
    reason.className = 'item-reason';
    reason.textContent = String(article.reason || '');
    link.append(meta, title, reason);
    card.append(link, notes);
    appendActions(card, article);
    articlesEl.appendChild(card);
  });
  box.hidden = articlesEl.childElementCount === 0 && (feature.articles.length > 0 || ACTIVE_STATE === 'read');
}

function render() {
  updateChipActive();
  updateMeta();
  renderKnowledgeFeature(FEATURE);
  const vis = visibleItems();
  const list = document.getElementById('list');
  const empty = document.getElementById('empty-state');
  list.innerHTML = '';
  empty.textContent = ACTIVE_STATE === 'read' ? '既読の記事はありません' : '今日の新着はありません';
  empty.style.display = !vis.length && document.getElementById('knowledge-feature').hidden ? 'flex' : 'none';
  vis.forEach(it => list.appendChild(renderItem(it)));
}

function renderItem(it) {
  const box = document.createElement('div');
  box.className = 'item' + (it.rating ? ' rated' : '');
  const n = starOf(it);
  const stars = '<span class="item-stars s' + n + '" title="' + esc(STAR_TITLE[n]) + '">'
    + (shukiIcon('star')).repeat(n) + '<span style="opacity:.25">' + (shukiIcon('star')).repeat(3 - n) + '</span></span>';
  box.innerHTML =
    '<a class="item-link" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' +
      '<div class="item-top">' + stars +
        '<span class="item-cat">' + esc(it.category) + '</span>' +
        '<span class="item-source">' + esc(it.source) + '</span>' +
        '<span class="item-time">' + esc(relTime(it.published)) + '</span></div>' +
      '<div class="item-title">' + esc(it.title) + '</div>' +
      (it.reason ? '<div class="item-reason">' + esc(it.reason) + '</div>' : '') +
    '</a>';
  appendActions(box, it);
  return box;
}

function appendActions(box, it) {
  const actions = document.createElement('div');
  actions.className = 'item-react';
  actions.innerHTML =
      '<button class="rbtn-n" data-v="good" title="役に立った">' + shukiIcon('thumbs-up') + ' 良かった</button>' +
      '<button class="rbtn-n" data-v="bad" title="外れだった（今後の選定の参考になる）">' + shukiIcon('thumbs-down') + ' 外れ</button>' +
      (it.read ? '<span class="read-label">既読</span>' : '<button class="rbtn-n" data-v="read">既読にする</button>');
  box.appendChild(actions);
  box.querySelectorAll('.rbtn-n').forEach(b => {
    b.classList.toggle('on', b.dataset.v === it.rating);
    if (b.dataset.v !== 'read') b.setAttribute('aria-pressed', String(b.dataset.v === it.rating));
    b.onclick = () => react(box, it, b.dataset.v);
  });
}

// Move only after the server acknowledges the saved read state.
function react(box, it, value) {
  box.querySelector('.news-error')?.remove();
  const readButton = box.querySelector('[data-v="read"]');
  const readLabel = readButton && readButton.textContent;
  if (value === 'read') readButton.textContent = '保存中…';
  box.querySelectorAll('.rbtn-n').forEach(b => b.disabled = true);
  fetch('/news/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: it.url, value: value })
  }).then(r => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (window.SFX) SFX.tick();
    if (value !== 'read') {
      it.rating = value;
      box.classList.add('rated');
      box.querySelectorAll('.rbtn-n').forEach(b => {
        b.disabled = false;
        b.classList.toggle('on', b.dataset.v === value);
        if (b.dataset.v !== 'read') b.setAttribute('aria-pressed', String(b.dataset.v === value));
      });
      updateMeta();
      return;
    }
    const articles = ALL.concat(FEATURE && Array.isArray(FEATURE.articles) ? FEATURE.articles : []);
    articles.filter(x => x.url === it.url).forEach(x => x.read = true);
    render();
    const remaining = document.querySelector('[data-v="read"]') || document.getElementById('news-tab-read');
    remaining.focus({preventScroll:true});
  }).catch(e => {
    box.querySelectorAll('.rbtn-n').forEach(b => b.disabled = false);
    if (readButton) readButton.textContent = readLabel;
    const error = document.createElement('p');
    error.className = 'news-error';
    error.setAttribute('role', 'alert');
    error.textContent = '保存できませんでした。もう一度お試しください。';
    box.appendChild(error);
  });
}

init();
</script>
</body></html>"""


SOURCES_PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + dashboard_ui.pwa_head() + dashboard_chat.assets_head() + """
<title> ニュースの登録元</title>
<style>
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg); font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  main { flex:1; padding:14px 16px 24px; max-width:760px; width:100%; margin:0 auto; }
  /* UIデザイン原則 §6.2：見た目は S=32px／入力・主ボタン M=40px、当たり判定はスマホだけ外側で44pxへ */
  .back { display:inline-flex; align-items:center; height:32px; color:var(--muted);
    font-size:.8rem; text-decoration:none; position:relative; }
  .back:hover { color:var(--fg); }
  section { margin-top:18px; }
  h2 { font-size:1rem; display:flex; align-items:baseline; gap:8px; }
  .count { font-size:.78rem; color:var(--muted); font-weight:normal; }
  .lead { font-size:.8rem; color:var(--muted); line-height:1.5; margin-top:4px; }
  h3 { font-size:.74rem; color:var(--accent); margin:14px 0 6px; font-weight:bold; }
  .row { background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:8px 8px 8px 12px; margin-bottom:6px; display:flex; align-items:center; gap:8px; }
  .row-main { flex:1; min-width:0; }
  .row-name { font-size:.88rem; font-weight:bold; overflow-wrap:anywhere; }
  .row-sub { font-size:.72rem; color:var(--muted); overflow-wrap:anywhere; text-decoration:none; }
  a.row-sub:hover { color:var(--fg); }
  .btn { font:inherit; font-size:.76rem; background:none; border:1px solid var(--line); border-radius:20px;
    color:var(--muted); padding:0 12px; height:32px; cursor:pointer; flex-shrink:0; position:relative; }
  .btn.primary { height:40px; padding:0 16px; }
  @media (pointer:coarse) { .btn::before, .back::before { content:''; position:absolute; inset:-6px 0; } }
  .btn:hover { color:var(--fg); border-color:var(--accent); }
  .btn.primary { color:var(--fg); border-color:var(--accent);
    background:color-mix(in srgb, var(--accent) 10%, var(--card)); }
  .btn:disabled { opacity:.6; cursor:default; }
  .btn:focus-visible, input:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  form { background:var(--card); border:1px dashed var(--line); border-radius:12px; padding:12px;
    margin-top:10px; display:grid; gap:8px; }
  label { display:grid; gap:3px; font-size:.74rem; color:var(--muted); }
  input { font:inherit; font-size:.86rem; color:var(--fg); background:var(--bg);
    border:1px solid var(--line); border-radius:8px; padding:0 10px; height:40px; width:100%; }
  .form-foot { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .status { font-size:.78rem; color:var(--muted); }
  .status.err { color:var(--danger); }
  .empty { font-size:.8rem; color:var(--muted); padding:8px 0; }
  /* AIとの対話で足すのが主経路（2026-10-11 ユーザーの要望）。手入力フォームは details に畳む */
  .ask { background:color-mix(in srgb, var(--accent) 7%, var(--card)); border:1px solid var(--accent);
    border-radius:12px; padding:12px; margin-top:8px; display:grid; gap:8px; }
  .ask-title { font-size:.9rem; font-weight:bold; }
  .ask-row { display:flex; gap:8px; align-items:center; }
  .ask-row input { flex:1; min-width:0; }
  .ask-chips { display:flex; gap:6px; flex-wrap:wrap; }
  details.manual { margin-top:10px; }
  details.manual > summary { font-size:.78rem; color:var(--muted); cursor:pointer; height:32px;
    display:flex; align-items:center; gap:6px; list-style:none; }
  details.manual > summary::-webkit-details-marker { display:none; }
  details.manual > summary::before { content:'+'; font-weight:bold; }
  details.manual[open] > summary::before { content:'−'; }
  details.manual form { margin-top:4px; }
  .tag { font-size:.68rem; color:var(--muted); border:1px solid var(--line); border-radius:10px;
    padding:0 6px; margin-left:6px; font-weight:normal; white-space:nowrap; }
  .tag.ai { color:var(--accent); border-color:var(--accent); }
  .score { font-size:.7rem; color:var(--muted); margin-left:8px; white-space:nowrap; }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head>
<body>

<!--SHUKI_PAGE_HEADER-->

<main>
  <a class="back" href="/news">← ニュースに戻る</a>

  <form class="ask" id="ask-form" aria-labelledby="ask-h">
    <div class="ask-title" id="ask-h">AIと一緒に登録元を探す</div>
    <p class="lead" style="margin:0;">追いたいテーマを書くと、対話パネルでAIが候補のフィードを探して実際に取得できるか確かめ、あなたが選んだものだけを登録します。</p>
    <div class="ask-row">
      <input name="topic" maxlength="300" aria-label="追いたいテーマ" placeholder="例：ドイツのエンジニア転職市場">
      <button class="btn primary" type="submit">AIに探してもらう</button>
    </div>
    <div class="ask-chips">
      <button class="btn" type="button" id="ask-review">今のフィードを評価で見直す</button>
    </div>
  </form>

  <section aria-labelledby="feeds-h">
    <h2 id="feeds-h">購読フィード <span class="count" id="feed-count"></span></h2>
    <p class="lead">毎朝ここに登録したRSS/Atomフィードから新着を集め、AIが重要なものだけを選んでニュースに並べます。</p>
    <div id="feeds"><p class="empty">読み込み中…</p></div>
    <details class="manual"><summary>URLが分かっている時は手で追加</summary>
    <form id="feed-form">
      <label>フィードのURL<input name="url" type="url" required placeholder="https://example.com/feed"></label>
      <label>名前（空欄ならフィードの題名）<input name="name" maxlength="200"></label>
      <label>カテゴリ<input name="category" required maxlength="200" list="cats"></label>
      <datalist id="cats"></datalist>
      <div class="form-foot"><button class="btn primary" type="submit">確認して追加</button>
        <span class="status" id="feed-status" role="status"></span></div>
    </form>
    </details>
  </section>

  <section aria-labelledby="watch-h">
    <h2 id="watch-h">ウォッチ <span class="count" id="watch-count"></span></h2>
    <p class="lead">一度だけ追いかけたい話題です。毎朝Web検索し、見つかったらニュースの先頭に載せて終わります。期限が来ても終わります。</p>
    <div id="watches"><p class="empty">読み込み中…</p></div>
    <details class="manual"><summary>話題を手で追加</summary>
    <form id="watch-form">
      <label>探す話題<input name="query" required maxlength="200" placeholder="例：IELTS 2027 試験形式の変更"></label>
      <label>期限（空欄なら30日後）<input name="expires" type="date"></label>
      <div class="form-foot"><button class="btn primary" type="submit">ウォッチを追加</button>
        <span class="status" id="watch-status" role="status"></span></div>
    </form>
    </details>
  </section>
</main>
<!--SHUKI_BOTTOM_NAV-->

<script>
const MSG_LABELS = {
  noFeeds: 'フィードはまだありません',
  noWatches: '進行中のウォッチはありません',
  remove: '外す',
  stop: 'やめる',
  expires: '期限',
  removeConfirm: 'このフィードを外しますか？',
  stopConfirm: 'このウォッチをやめますか？',
  checking: 'フィードを確認中…',
  saving: '保存中…',
  added: '追加しました',
  failed: '保存できませんでした',
  loadFailed: '読み込みエラー',
  viaAi: 'AIが追加',
  askLabel: 'ニュースの登録元を探す',
  reviewLabel: 'ニュースのフィードを見直す',
  needTopic: '追いたいテーマを書いてください',
  noDock: '対話パネルを開けませんでした。ページを再読み込みしてください。'
};

async function send(body) {
  const r = await fetch('/news/sources', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
  return d;
}

function row(name, sub, href, buttonLabel, onClick, extras) {
  const box = document.createElement('div');
  box.className = 'row';
  const main = document.createElement('div');
  main.className = 'row-main';
  const title = document.createElement('div');
  title.className = 'row-name';
  title.textContent = name;
  (extras || []).forEach(el => title.appendChild(el));
  const meta = document.createElement(href ? 'a' : 'div');
  meta.className = 'row-sub';
  meta.textContent = sub;
  if (href) { meta.href = href; meta.target = '_blank'; meta.rel = 'noopener noreferrer'; }
  main.append(title, meta);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn';
  button.textContent = buttonLabel;
  button.onclick = () => onClick(button);
  box.append(main, button);
  return box;
}

function empty(text) {
  const p = document.createElement('p');
  p.className = 'empty';
  p.textContent = text;
  return p;
}

function render(d) {
  const feeds = document.getElementById('feeds');
  feeds.replaceChildren();
  document.getElementById('feed-count').textContent = String((d.feeds || []).length);
  const groups = {};
  (d.feeds || []).forEach(f => (groups[f.category || '—'] = groups[f.category || '—'] || []).push(f));
  Object.keys(groups).sort().forEach(cat => {
    const h = document.createElement('h3');
    h.textContent = cat;
    feeds.appendChild(h);
    groups[cat].forEach(f => {
      let host = f.url;
      try { host = new URL(f.url).host; } catch (e) {}
      // 評価の実績（良かった／外れ）と「AIが追加」を名前の横に小さく出す＝見直しの手がかり
      const extras = [];
      const r = f.ratings || {};
      if (r.good || r.bad) {
        const score = document.createElement('span');
        score.className = 'score';
        score.innerHTML = shukiIcon('thumbs-up') + ' ' + (r.good || 0) + ' ' + shukiIcon('thumbs-down') + ' ' + (r.bad || 0);
        extras.push(score);
      }
      if (f.via === 'ai') {
        const tag = document.createElement('span');
        tag.className = 'tag ai';
        tag.textContent = MSG_LABELS.viaAi + (f.added ? ' ' + f.added.slice(5) : '');
        extras.push(tag);
      }
      feeds.appendChild(row(f.name, host, /^https?:/.test(f.url) ? f.url : null, MSG_LABELS.remove, async button => {
        if (!confirm(MSG_LABELS.removeConfirm + '\\n' + f.name)) return;
        button.disabled = true;
        try { render(await send({ action: 'remove_feed', url: f.url })); }
        catch (e) { button.disabled = false; alert(MSG_LABELS.failed + ': ' + e.message); }
      }, extras));
    });
  });
  if (!feeds.childElementCount) feeds.appendChild(empty(MSG_LABELS.noFeeds));
  const cats = document.getElementById('cats');
  cats.replaceChildren(...(d.categories || []).map(c => { const o = document.createElement('option'); o.value = c; return o; }));

  const watches = document.getElementById('watches');
  watches.replaceChildren();
  document.getElementById('watch-count').textContent = String((d.watches || []).length);
  (d.watches || []).forEach(w => {
    watches.appendChild(row(w.query, MSG_LABELS.expires + ' ' + (w.expires || '—'), null, MSG_LABELS.stop, async button => {
      if (!confirm(MSG_LABELS.stopConfirm + '\\n' + w.query)) return;
      button.disabled = true;
      try { render(await send({ action: 'stop_watch', id: w.id })); }
      catch (e) { button.disabled = false; alert(MSG_LABELS.failed + ': ' + e.message); }
    }));
  });
  if (!watches.childElementCount) watches.appendChild(empty(MSG_LABELS.noWatches));
}

function bindForm(formId, statusId, pendingText, toBody) {
  const form = document.getElementById(formId);
  const status = document.getElementById(statusId);
  form.onsubmit = async event => {
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    status.className = 'status';
    status.textContent = pendingText;
    try {
      render(await send(toBody(new FormData(form))));
      form.reset();
      status.textContent = MSG_LABELS.added;
    } catch (e) {
      status.className = 'status err';
      status.textContent = MSG_LABELS.failed + ': ' + e.message;
    } finally {
      button.disabled = false;
    }
  };
}

bindForm('feed-form', 'feed-status', MSG_LABELS.checking, f => ({
  action: 'add_feed', url: f.get('url'), name: f.get('name'), category: f.get('category')
}));
bindForm('watch-form', 'watch-status', MSG_LABELS.saving, f => ({
  action: 'add_watch', query: f.get('query'), expires: f.get('expires')
}));

// 主経路：対話パネルで news-sources スキルを起動する（モデル選択→実行はドック側の exec が担う）
function askAi(text, label) {
  if (typeof exec !== 'function') { alert(MSG_LABELS.noDock); return; }
  exec('news-sources', encodeURIComponent(text), label);
}
document.getElementById('ask-form').onsubmit = event => {
  event.preventDefault();
  const input = event.target.elements.topic;
  const topic = input.value.trim();
  if (!topic) { input.placeholder = MSG_LABELS.needTopic; input.focus(); return; }
  askAi(topic, MSG_LABELS.askLabel);
};
document.getElementById('ask-review').onclick = () => askAi('review', MSG_LABELS.reviewLabel);

function load() {
  return fetch('/news/sources/data', { cache: 'no-store' }).then(r => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }).then(render).catch(e => {
    document.getElementById('feeds').replaceChildren(empty(MSG_LABELS.loadFailed + ': ' + e.message));
  });
}
// AIが対話で足した・外したものを、返答が終わった時とタブに戻った時に一覧へ反映する
window.addEventListener('shuki:chat', e => { if (e.detail && e.detail.type === 'reply') load(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
load();
</script>
</body></html>"""


def render_sources_html():
    # 購読フィードとウォッチの一覧・追加・削除（2026-10-11）。データは /news/sources/data。
    return dashboard_ui.hydrate_shell(
        shuki_i18n.tt_html(SOURCES_PAGE, ctx="news"), "news",
        tt(dashboard_icons.nav_icon_svg("home", 19) + " ニュースの登録元"))


def render_news_html():
    # 記事データは /news/data から JS が取りに行くので PAGE は静的＝ tt() をかけてよい。
    # シェル（ナビ・下部タブ・対話ドック）はリクエスト毎に組み直す＝ナビ表示設定や
    # モデル選択の変更をサーバー再起動なしで反映する（2026-09-01）。自前で翻訳済みなので
    # hydrate 後に tt() を二重適用しない。
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        shuki_i18n.tt_html(PAGE, ctx="news"), "news",
        tt(dashboard_icons.nav_icon_svg("home", 19) + " ニュース"))
