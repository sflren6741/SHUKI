#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_news.py — 📰 ニュース（dashboard_server.py の /news ページ）

news_fetch.py（日次スケジューラ Claude-NewsDigest）が生成する
99_System/news/<date>.json（当日分の選定済みニュース）をそのまま表示するだけの
読み物ページ。既読管理・レビューアクションは持たない（/review と違い「読んで終わり」の
消費コンテンツのため）。カードのリンクは常に target="_blank" で外部サイトへ直接遷移する。

データは /news/data から取得（dashboard_server.collect_news_items が
99_System/news/ 配下の最新日付 .json を読むだけ。サーバーは vault 本体を書かない）。
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
<title>📰 ニュース</title>
<style>
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg);
    font-family:var(--font-ui);
    min-height:100vh; display:flex; flex-direction:column; }
  header { flex-shrink:0; }
  .filter-bar { display:flex; align-items:center; gap:8px; padding:8px 16px;
    border-bottom:1px solid var(--line); flex-shrink:0; flex-wrap:wrap; }
  .chip-f { font-size:.76rem; color:var(--muted); border:1px solid var(--line);
    border-radius:20px; padding:5px 12px; cursor:pointer; background:var(--card);
    display:flex; align-items:center; gap:4px; min-height:32px; }
  .chip-f.active { border-color:var(--accent); color:var(--fg); background:#e9c46a1a; }
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
  .item.leaving { opacity:0; transform:translateX(24px); }  /* ✕ を押した記事が抜けていく */
  .item.rated .item-link { opacity:.6; }  /* 評価済み：残すが一段控えめに */
  .item-link { display:block; text-decoration:none; color:inherit; }
  /* 👍/👎 は評価（押した方が点灯して記事は残る・押し直せる）。✕ だけ一覧から消す。
     リンクの中に入れられないのでカード内の別行に置く */
  .item-react { display:flex; gap:6px; margin-top:9px; padding-top:9px; border-top:1px solid var(--line); }
  .rbtn-n { background:none; border:1px solid var(--line); border-radius:20px; cursor:pointer;
    color:var(--muted); font-size:.74rem; padding:4px 12px; min-height:30px;
    display:inline-flex; align-items:center; gap:5px; font-family:inherit; }
  .rbtn-n:hover { color:var(--fg); border-color:var(--accent); }
  .rbtn-n.on { color:var(--fg); border-color:var(--accent); background:#e9c46a1a; }
  .rbtn-n[data-v="skip"] { margin-left:auto; }  /* 「読まない」だけ右端に離す（誤爆防止） */
  .item-top { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
  .item-cat { font-size:.68rem; color:var(--accent); background:#e9c46a1a;
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
  .item-stars.s3 { color:var(--accent); font-size:.95rem; text-shadow:0 0 10px #e9c46a66; }
  .item-stars.s2 { color:var(--fg); }
  .knowledge-feature { background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:14px; margin-bottom:14px; }
  .knowledge-feature-label { color:var(--accent); font-size:.7rem; font-weight:bold; }
  .knowledge-feature-title { font-size:1rem; line-height:1.45; margin-top:4px; }
  .knowledge-feature-summary { color:var(--muted); font-size:.8rem; line-height:1.5; margin-top:5px; }
  .knowledge-feature-sources { display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }
  .knowledge-feature-source { color:var(--fg); background:var(--bg); border:1px solid var(--line);
    border-radius:18px; padding:5px 10px; font-size:.74rem; text-decoration:none;
    min-height:44px; display:inline-flex; align-items:center; }
  .knowledge-feature-source:hover { border-color:var(--accent); }
  .knowledge-feature-articles { margin-top:12px; }
  .knowledge-feature-articles .item:last-child { margin-bottom:0; }
""" + dashboard_ui.RESPONSIVE_CSS + """
</style>
</head>
<body>

<!--SHUKI_PAGE_HEADER-->

<div class="filter-bar" id="filter-bar">
  <span id="meta"></span>
</div>

<main>
  <section id="knowledge-feature" class="knowledge-feature" hidden aria-label="Weekly news related to your knowledge">
    <div class="knowledge-feature-label">This week</div>
    <h2 id="knowledge-feature-title" class="knowledge-feature-title"></h2>
    <p id="knowledge-feature-summary" class="knowledge-feature-summary"></p>
    <div id="knowledge-feature-articles" class="knowledge-feature-articles"></div>
  </section>
  <div id="loading"><span class="spin">""" + dashboard_icons.ui_icon_svg("loading", 15) + """</span> 読み込み中…</div>
  <div id="empty-state" style="display:none;">""" + dashboard_icons.ui_icon_svg("newspaper", 15) + """ 今日の新着はありません</div>
  <div id="list"></div>
</main>
<!--SHUKI_BOTTOM_NAV-->

<script>
let ALL = [], ACTIVE_CAT = '', META_DATE = '';

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
    renderKnowledgeFeature(d.knowledge_feature);
    document.getElementById('loading').style.display = 'none';
    buildFilterBar();
    updateMeta();
    render();
  } catch(e) {
    document.getElementById('loading').textContent = '読み込みエラー: ' + e;
  }
}

function buildFilterBar() {
  const bar = document.getElementById('filter-bar');
  const cats = [];
  const seen = new Set();
  ALL.forEach(it => { if (!seen.has(it.category)) { seen.add(it.category); cats.push(it.category); } });
  const meta = document.getElementById('meta');
  bar.innerHTML = '';
  const mkChip = (key, label) => {
    const c = document.createElement('div');
    c.className = 'chip-f';
    c.dataset.cat = key;
    c.textContent = label;
    c.onclick = () => { ACTIVE_CAT = key; render(); };
    bar.appendChild(c);
  };
  mkChip('', 'すべて');
  cats.forEach(c => mkChip(c, c));
  bar.appendChild(meta);
  updateChipActive();
}

function updateChipActive() {
  document.querySelectorAll('.chip-f').forEach(el => {
    el.classList.toggle('active', el.dataset.cat === ACTIVE_CAT);
  });
}

function visibleItems() {
  const v = ACTIVE_CAT ? ALL.filter(it => it.category === ACTIVE_CAT) : ALL.slice();
  // 星の高い順（news_fetch も保存時に並べるが、stars を持たない過去データのために表示側でも）
  return v.sort((a, b) => starOf(b) - starOf(a));
}

// stars は 1〜3。付いていない過去データ（2026-08-12 以前）は 2 とみなす
function starOf(it) {
  const n = parseInt(it.stars, 10);
  return (n >= 1 && n <= 3) ? n : 2;
}
const STAR_TITLE = { 3: '今日のうちに見たほうがいい', 2: '読む価値がある', 1: '参考程度' };

// 「あと何件残っているか」＝まだ評価も ✕ もしていない記事。押すたびに減る（読み進めた実感が出る）
function updateMeta() {
  const el = document.getElementById('meta');
  if (!el) return;
  const rest = ALL.filter(x => !x.rating).length;
  el.textContent = (META_DATE ? META_DATE + ' 更新' : '') + (rest ? '・残り' + rest + '件' : '');
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
  feature.articles.forEach(article => {
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
    card.className = 'item';
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
    articlesEl.appendChild(card);
  });
  box.hidden = feature.articles.length > 0 && articlesEl.childElementCount === 0;
}

function render() {
  updateChipActive();
  const vis = visibleItems();
  const list = document.getElementById('list');
  const empty = document.getElementById('empty-state');
  list.innerHTML = '';
  if (!vis.length) { empty.style.display = 'flex'; return; }
  empty.style.display = 'none';
  vis.forEach(it => list.appendChild(renderItem(it)));
}

function renderItem(it) {
  const box = document.createElement('div');
  box.className = 'item' + (it.rating ? ' rated' : '');
  const n = starOf(it);
  const stars = '<span class="item-stars s' + n + '" title="' + esc(STAR_TITLE[n]) + '">'
    + '★'.repeat(n) + '<span style="opacity:.25">' + '★'.repeat(3 - n) + '</span></span>';
  box.innerHTML =
    '<a class="item-link" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' +
      '<div class="item-top">' + stars +
        '<span class="item-cat">' + esc(it.category) + '</span>' +
        '<span class="item-source">' + esc(it.source) + '</span>' +
        '<span class="item-time">' + esc(relTime(it.published)) + '</span></div>' +
      '<div class="item-title">' + esc(it.title) + '</div>' +
      (it.reason ? '<div class="item-reason">' + esc(it.reason) + '</div>' : '') +
    '</a>' +
    '<div class="item-react">' +
      '<button class="rbtn-n" data-v="good" title="役に立った">&#128077; 良かった</button>' +
      '<button class="rbtn-n" data-v="bad" title="外れだった（今後の選定の参考になる）">&#128078; 外れ</button>' +
      '<button class="rbtn-n" data-v="skip" title="読まずに閉じる">&#10005;</button>' +
    '</div>';
  box.querySelectorAll('.rbtn-n').forEach(b => {
    b.classList.toggle('on', b.dataset.v === it.rating);
    b.onclick = () => react(box, it, b.dataset.v);
  });
  return box;
}

// 反応を送る。👍/👎 はカードを残して押した方を点灯（押し直せる）、✕ だけカードを消す。
// サーバー側に記録されるので、リロードしても同じ状態で戻る。
function react(box, it, value) {
  box.querySelectorAll('.rbtn-n').forEach(b => b.disabled = true);
  fetch('/news/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: it.url, value: value })
  }).then(r => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (window.SFX) SFX.tick();
    if (value !== 'skip') {
      it.rating = value;
      box.classList.add('rated');
      box.querySelectorAll('.rbtn-n').forEach(b => {
        b.disabled = false;
        b.classList.toggle('on', b.dataset.v === value);
      });
      updateMeta();
      return;
    }
    ALL = ALL.filter(x => x.url !== it.url);
    box.classList.add('leaving');
    setTimeout(() => { box.remove(); updateMeta(); if (!visibleItems().length) render(); }, 250);
  }).catch(e => {
    box.querySelectorAll('.rbtn-n').forEach(b => b.disabled = false);
    alert('記録に失敗しました: ' + e);
  });
}

init();
</script>
</body></html>"""


def render_news_html():
    # 記事データは /news/data から JS が取りに行くので PAGE は静的＝ tt() をかけてよい。
    # シェル（ナビ・下部タブ・対話ドック）はリクエスト毎に組み直す＝ナビ表示設定や
    # モデル選択の変更をサーバー再起動なしで反映する（2026-09-01）。自前で翻訳済みなので
    # hydrate 後に tt() を二重適用しない。
    # 🔄 再読み込みボタンは page_header() が共通で出すため、ここでは持たない（2026-09-27〜）。
    return dashboard_ui.hydrate_shell(
        shuki_i18n.tt_html(PAGE, ctx="news"), "news",
        tt(dashboard_icons.nav_icon_svg("home", 19) + " ニュース"))
