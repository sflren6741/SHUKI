#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_facets.py — 🔎 絞り込み・グルーピング・ソートの共有エンジン（2026-08-18 新設）

dashboard_board.py（タスクボード）が実装した「AXES を1枚定義すればフィルタチップ・値ピッカー・
グルーピングが揃う」仕組みを、他ページ（dashboard_files.py の vault全ファイル一覧）でも
ハードコードせず使い回すために切り出した。エンジンが持つのは「軸（AXES）からチップUI・
絞り込み・束ねを組み立てる」構造だけで、軸の中身（何を候補にするか）は各ページが定義する。

使い方: 呼び出し側ページの <script> 内、以下のグローバルを定義した「後」で
engine_js() の返すJSテキストを埋め込む（関数宣言はホイスティングされるので定義順は
呼び出しより後でもよいが、実行時＝init() 呼び出し時点で揃っていればよい）。
  - let ALL = [...]          対象アイテム配列
  - let FILTERS = {...}      軸key -> 選択キー配列（既定値はページ側で決める）
  - const AXES = { 軸key: { label, keyOf(item)->key, defs()->[{key,label,color,icon?}],
      matches(item, selectedKeys)->bool（省略可。階層フォルダ等「選んだ値の子孫も含めたい」軸だけ
      定義する。省略時は既定の完全一致 selectedKeys.includes(keyOf(item)) が使われる） } }
  - function searchText(t)   検索窓が照合する文字列（省略時は既定で t.title を使う）
DOM側は #f-search（検索欄）・#f-chips（チップ描画先）・#f-add（＋条件ボタン）・
#f-pop（ピッカーのポップアップ）の4要素が前提（board.py のツールバー構造と同じ）。
"""


def engine_css():
    """チップUI・値ピッカーの見た目（.f-chips/.f-chip/.f-add/#f-pop/.fp-*）。
    board.py の 2026-08-08 実装をそのまま抽出（board/files 共通）。
    レイアウト寄りの .filter-bar/select 等はページ固有のまま各ページに残す。"""
    return """
  /* 条件チップ（軸: 値 ×）。1軸に複数値を持てるので「+n」で畳む。
     display:contents で親(.tb-grp)の折り返しに直接乗せる＝狭い画面でも
     「⏚アイコン → チップ → ＋条件」が1つの流れとして自然に折り返る */
  .f-chips { display:contents; }
  .f-chip { display:inline-flex; align-items:center; background:var(--card);
    border:1px solid var(--line); border-radius:2px; font-size:.76rem; min-height:28px; }
  .f-chip:hover { border-color:var(--accent); }
  .fc-t { padding:4px 7px 4px 9px; cursor:pointer; color:var(--fg); }
  .fc-t .fc-k { color:var(--muted); }
  .fc-x { display:inline-flex; align-items:center; padding:5px 6px; cursor:pointer; color:var(--muted); }
  .fc-x:hover { color:var(--danger); }
  .f-add { display:inline-flex; align-items:center; gap:3px; background:none;
    border:1px dashed var(--line); color:var(--muted); border-radius:2px; padding:3px 9px;
    font-size:.76rem; font-family:inherit; cursor:pointer; min-height:28px; }
  .f-add:hover { border-style:solid; border-color:var(--accent); color:var(--fg); }
  /* 値ピッカー（軸選び → 値の複数選択）。position:fixed でツールバーの折り返しに影響されない */
  #f-pop { display:none; position:fixed; z-index:1002; background:var(--card);
    border:1px solid var(--line); border-radius:2px; padding:5px; min-width:186px;
    max-height:62vh; overflow-y:auto; box-shadow:0 8px 24px #00000066; }
  #f-pop.on { display:block; }
  .fp-hd { font-size:.66rem; color:var(--muted); padding:5px 8px 7px; letter-spacing:.05em; }
  .fp-item { display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:2px;
    font-size:.78rem; color:var(--fg); cursor:pointer; min-height:32px; }
  .fp-item:hover { background:color-mix(in srgb, var(--accent) 13%, transparent); }
  .fp-box { width:14px; height:14px; border:1px solid var(--line); border-radius:2px;
    flex-shrink:0; display:inline-flex; align-items:center; justify-content:center; }
  .fp-box svg { display:none; }
  .fp-item.on .fp-box { background:var(--accent); border-color:var(--accent); color:var(--bg); }
  .fp-item.on .fp-box svg { display:block; }
  .fp-count { margin-left:auto; font-size:.68rem; color:var(--muted); }
  .fp-sep { height:1px; background:var(--line); margin:5px 2px; }
"""


def views_css():
    """保存済みビューのチップ行（フォルダ別ショートカット等）の見た目。
    board/files 共通。ページ固有の色・レイアウトはここに持たせない。"""
    return """
  .v-row { display:flex; align-items:center; gap:6px; padding:6px 16px; overflow-x:auto;
    border-bottom:1px solid var(--line); flex-shrink:0; -ms-overflow-style:none; scrollbar-width:none; }
  .v-row::-webkit-scrollbar { display:none; }
  .v-chip { display:inline-flex; align-items:center; gap:5px; background:var(--card);
    border:1px solid var(--line); border-radius:20px; padding:5px 12px; font-size:.78rem;
    color:var(--fg); white-space:nowrap; cursor:pointer; flex-shrink:0; }
  .v-chip:hover { border-color:var(--accent); }
  .v-chip.on { background:var(--accent); border-color:var(--accent); color:var(--bg); font-weight:bold; }
  .v-chip .v-x { display:inline-flex; margin-left:1px; opacity:.6; }
  .v-chip .v-x:hover { opacity:1; }
  .v-add { display:inline-flex; align-items:center; gap:4px; background:none;
    border:1px dashed var(--line); border-radius:20px; color:var(--muted); padding:5px 12px;
    font-size:.78rem; font-family:inherit; cursor:pointer; flex-shrink:0; }
  .v-add:hover { border-style:solid; border-color:var(--accent); color:var(--fg); }
  .v-gear { padding:5px 9px; }
  /* ビュー管理パネル（#f-pop を使い回す）の並び替え矢印 */
  .fp-move { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px;
    color:var(--muted); cursor:pointer; border-radius:2px; }
  .fp-move:hover { background:color-mix(in srgb, var(--accent) 16%, transparent); color:var(--fg); }
"""


def views_js(storage_key, icon_cross_svg, icon_check_svg, icon_gear_svg):
    """保存済みビュー（フィルタ+ソート+グルーピングの組み合わせを名前で呼び出す）のJS。

    呼び出し側ページは以下を用意する:
      - let DEFAULT_VIEWS = [{id,name,builtin:true,state:{filters,group,sort,sortDir}}, ...]
        （組み込みビュー。folder軸のdefs()等、既存AXESから動的に組み立てる想定＝ハードコードしない）
      - #v-row 要素（チップ行の描画先）
    ビューを適用すると FILTERS/#f-group/#f-sort/#f-sort-dir を書き換えて applyFilters() を呼ぶ。
    カスタムビューは localStorage[storage_key] に保存（vault本体は書かない）。
    表示・非表示（組み込みビューも対象）と並び順は localStorage[storage_key + '__settings'] に
    { hidden:[id,...], order:[id,...] } として保存する（⚙ボタン→#f-pop を使い回すパネルで操作。
    値ピッカーと同じ #f-pop・fp-item・fp-box を再利用＝新規CSSを増やさない）。
    """
    return """
let CUSTOM_VIEWS = [];
const VIEWS_KEY = '""" + storage_key + """';
function loadCustomViews() {
  try { CUSTOM_VIEWS = JSON.parse(localStorage.getItem(VIEWS_KEY) || '[]'); }
  catch(e) { CUSTOM_VIEWS = []; }
  loadViewSettings();
}
function saveCustomViews() {
  try { localStorage.setItem(VIEWS_KEY, JSON.stringify(CUSTOM_VIEWS)); } catch(e) {}
}

/* ---- 表示/非表示・並び順（組み込み・カスタム共通） ---- */
let VIEW_HIDDEN = [], VIEW_ORDER = [];
const VIEW_SETTINGS_KEY = VIEWS_KEY + '__settings';
function loadViewSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(VIEW_SETTINGS_KEY) || '{}');
    VIEW_HIDDEN = Array.isArray(s.hidden) ? s.hidden : [];
    VIEW_ORDER = Array.isArray(s.order) ? s.order : [];
  } catch(e) { VIEW_HIDDEN = []; VIEW_ORDER = []; }
}
function saveViewSettings() {
  try { localStorage.setItem(VIEW_SETTINGS_KEY, JSON.stringify({ hidden:VIEW_HIDDEN, order:VIEW_ORDER })); } catch(e) {}
}
function allViews() {
  return (typeof DEFAULT_VIEWS !== 'undefined' ? DEFAULT_VIEWS : []).concat(CUSTOM_VIEWS);
}
/* 並び順登録済みのidを先に、未登録は元の並びのまま末尾へ。includeHidden=falseなら非表示を除く */
function orderedViews(includeHidden) {
  const all = allViews();
  const byId = {}; all.forEach(v => byId[v.id] = v);
  const ordered = [];
  VIEW_ORDER.forEach(id => { if (byId[id]) { ordered.push(byId[id]); delete byId[id]; } });
  all.forEach(v => { if (byId[v.id]) ordered.push(v); });
  return includeHidden ? ordered : ordered.filter(v => !VIEW_HIDDEN.includes(v.id));
}
function moveView(id, dir) {
  const ids = orderedViews(true).map(v => v.id);
  const i = ids.indexOf(id), j = i + dir;
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  VIEW_ORDER = ids;
  saveViewSettings();
}
function toggleViewHidden(id) {
  const s = new Set(VIEW_HIDDEN);
  s.has(id) ? s.delete(id) : s.add(id);
  VIEW_HIDDEN = [...s];
  saveViewSettings();
}
function viewManagerHtml() {
  const all = orderedViews(true);
  const rows = all.map((v, i) => {
    const hidden = VIEW_HIDDEN.includes(v.id);
    return '<div class="fp-item' + (hidden ? '' : ' on') + '" data-viewtog="' + v.id + '">'
      + '<span class="fp-box">""" + icon_check_svg + """</span>'
      + '<span>' + esc(v.name) + '</span>'
      + '<span class="fp-count" style="display:inline-flex;gap:2px;">'
      + '<span class="fp-move" data-viewup="' + v.id + '"' + (i === 0 ? ' style="opacity:.25;pointer-events:none;"' : '') + '>▲</span>'
      + '<span class="fp-move" data-viewdown="' + v.id + '"' + (i === all.length - 1 ? ' style="opacity:.25;pointer-events:none;"' : '') + '>▼</span>'
      + '</span></div>';
  }).join('');
  return '<div class="fp-hd">ビューの表示・並び順（チェック＝表示）</div>' + rows;
}
function openViewManager(anchor) { showPop(anchor, viewManagerHtml()); }

function currentViewState() {
  return {
    filters: FILTERS,
    group: document.getElementById('f-group').value,
    sort: document.getElementById('f-sort').value,
    sortDir: document.getElementById('f-sort-dir').value,
  };
}
function sameViewState(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}
function applyViewState(state) {
  FILTERS = JSON.parse(JSON.stringify(state.filters || {}));
  if (state.group != null) document.getElementById('f-group').value = state.group;
  if (state.sort != null) document.getElementById('f-sort').value = state.sort;
  if (state.sortDir != null) document.getElementById('f-sort-dir').value = state.sortDir;
  applyFilters();
  renderViews();
}
function addViewFromCurrent() {
  const name = prompt('この絞り込みをビューとして保存する名前を入力');
  if (!name) return;
  CUSTOM_VIEWS.push({ id:'v' + Date.now(), name, builtin:false, state:currentViewState() });
  saveCustomViews();
  renderViews();
}
function deleteCustomView(id) {
  CUSTOM_VIEWS = CUSTOM_VIEWS.filter(v => v.id !== id);
  saveCustomViews();
  renderViews();
}
function renderViews() {
  const wrap = document.getElementById('v-row');
  if (!wrap) return;
  const cur = currentViewState();
  wrap.innerHTML = orderedViews(false).map(v => {
    const on = sameViewState(v.state, cur);
    return '<span class="v-chip' + (on ? ' on' : '') + '" data-view="' + v.id + '">' + esc(v.name)
      + (v.builtin ? '' : '<span class="v-x" data-delview="' + v.id + '" title="このビューを削除">""" + icon_cross_svg + """</span>')
      + '</span>';
  }).join('')
    + '<button id="v-manage" class="v-add v-gear" title="ビューの表示・並び順を管理">""" + icon_gear_svg + """</button>'
    + '<button id="v-add" class="v-add" title="今の絞り込み・並べ替え・束ね方を名前で保存">+ 現在の条件を保存</button>';
}
document.addEventListener('click', e => {
  const del = e.target.closest('[data-delview]');
  if (del) { e.stopPropagation(); deleteCustomView(del.dataset.delview); return; }
  const up = e.target.closest('[data-viewup]');
  if (up) { e.stopPropagation(); moveView(up.dataset.viewup, -1); openViewManager(document.getElementById('v-manage')); renderViews(); return; }
  const down = e.target.closest('[data-viewdown]');
  if (down) { e.stopPropagation(); moveView(down.dataset.viewdown, 1); openViewManager(document.getElementById('v-manage')); renderViews(); return; }
  const tog = e.target.closest('[data-viewtog]');
  if (tog) { e.stopPropagation(); toggleViewHidden(tog.dataset.viewtog); openViewManager(document.getElementById('v-manage')); renderViews(); return; }
  const manage = e.target.closest('#v-manage');
  if (manage) { openViewManager(manage); return; }
  const chip = e.target.closest('[data-view]');
  if (chip) {
    const v = allViews().find(x => x.id === chip.dataset.view);
    if (v) applyViewState(v.state);
    return;
  }
  if (e.target.closest('#v-add')) { addViewFromCurrent(); return; }
});
"""


def engine_js(icon_check_svg, icon_cross_svg):
    """絞り込みエンジンのJSテキストを返す。

    icon_check_svg: 値ピッカーのチェックボックスに使う線アイコンSVG（呼び出し側の
      dashboard_icons.ui_icon_svg("check", ...) をそのまま渡す＝サイズはページ裁量）
    icon_cross_svg: チップの「外す」ボタンに使う線アイコンSVG（同上、"cross"）
    """
    return """
/* ===== 🔎 絞り込みエンジン（条件チップ・1軸に複数値・グルーピング共通） =====
   dashboard_facets.engine_js() が生成。中身は dashboard_board.py 2026-08-08 設計の踏襲。
   軸の定義（AXES）・対象配列（ALL）・既定フィルタ（FILTERS）はページ側が用意する。
   「絞れる粒度」と「束ねる粒度」が同じ AXES から作られる＝構造的にズレない。 */
let POP_FIELD = null;   /* 値ピッカーを開いている軸 */

function searchText(t) { return t.title; }   /* 既定＝タイトル検索。ページ側で上書き可 */

/* 軸に matches() があればそれで判定（例: フォルダ軸＝選んだフォルダの子孫も含む前方一致）。
   無ければ既定の完全一致。board.py 側の軸は matches を持たないため挙動は従来どおり。 */
function axisOn(k, t) {
  const ax = AXES[k], sel = FILTERS[k];
  return ax.matches ? ax.matches(t, sel) : sel.includes(ax.keyOf(t));
}
function filteredTasks() {
  const q = document.getElementById('f-search').value.trim().toLowerCase();
  const on = Object.keys(FILTERS).filter(k => AXES[k] && FILTERS[k] && FILTERS[k].length);
  return ALL.filter(t => (!q || String(searchText(t) || '').toLowerCase().includes(q))
    && on.every(k => axisOn(k, t)));
}

/* ---- 条件チップ ---- */
function labelOf(field, key) {
  const d = AXES[field].defs().find(x => x.key === key);
  return d ? d.label : key;
}
function renderChips() {
  const wrap = document.getElementById('f-chips');
  wrap.innerHTML = '';
  Object.keys(AXES).forEach(f => {
    const sel = FILTERS[f];
    if (!sel) return;                       /* 未追加の軸は出さない */
    const body = sel.length
      ? labelOf(f, sel[0]) + (sel.length > 1 ? ' +' + (sel.length - 1) : '')
      : 'すべて';                           /* 値ゼロ＝追加はしたが絞っていない状態 */
    const c = document.createElement('span');
    c.className = 'f-chip';
    c.innerHTML = '<span class="fc-t" data-editf="' + f + '">'
        + '<span class="fc-k">' + esc(AXES[f].label) + '</span> ' + esc(body) + '</span>'
      + '<span class="fc-x" data-delf="' + f + '" title="この条件を外す">""" + icon_cross_svg + """</span>';
    wrap.appendChild(c);
  });
}

/* ---- ピッカー（軸選び / 値の複数選択） ---- */
function showPop(anchor, html) {
  const p = document.getElementById('f-pop');
  p.innerHTML = html;
  p.className = 'on';
  const r = anchor.getBoundingClientRect();
  const left = Math.max(8, Math.min(r.left, window.innerWidth - p.offsetWidth - 8));
  let top = r.bottom + 6;
  if (top + p.offsetHeight > window.innerHeight - 8)   /* 下に入らなければ上に出す */
    top = Math.max(8, r.top - p.offsetHeight - 6);
  p.style.left = left + 'px';
  p.style.top  = top + 'px';
}
function closePop() { document.getElementById('f-pop').className = ''; POP_FIELD = null; }

function openFieldPicker(anchor) {
  POP_FIELD = null;
  const items = Object.keys(AXES).map(f =>
    '<div class="fp-item" data-pickf="' + f + '"><span>' + esc(AXES[f].label) + '</span>'
    + (FILTERS[f] ? '<span class="fp-count">追加済み</span>' : '') + '</div>').join('');
  showPop(anchor, '<div class="fp-hd">絞り込む軸</div>' + items);
}
function openValuePicker(field, anchor) {
  POP_FIELD = field;
  const ax = AXES[field], sel = FILTERS[field] || [];
  const n = {};
  if (ax.matches) {
    /* 前方一致の軸は「その値を単独で選んだら何件ヒットするか」を件数に出す（子孫込み） */
    ax.defs().forEach(d => { n[d.key] = ALL.filter(t => ax.matches(t, [d.key])).length; });
  } else {
    ALL.forEach(t => { const k = ax.keyOf(t); n[k] = (n[k] || 0) + 1; });
  }
  const items = ax.defs().filter(d => n[d.key]).map(d =>
    '<div class="fp-item' + (sel.includes(d.key) ? ' on' : '') + '" data-togv="' + esc(d.key) + '">'
    + '<span class="fp-box">""" + icon_check_svg + """</span><span>' + esc(d.label) + '</span>'
    + '<span class="fp-count">' + n[d.key] + '</span></div>').join('');
  showPop(anchor, '<div class="fp-hd">' + esc(ax.label) + ' — 複数選べます</div>' + items
    + '<div class="fp-sep"></div><div class="fp-item" data-delf="' + field + '">条件を外す</div>');
}

/* ツールバーの操作はすべてここで受ける（チップは描き直されるので個別 listener を持たせない） */
document.addEventListener('click', e => {
  const hit = s => e.target.closest(s);
  const add = hit('#f-add'), del = hit('[data-delf]'), edit = hit('[data-editf]');
  const pick = hit('[data-pickf]'), tog = hit('[data-togv]');
  if (add)  { openFieldPicker(add); return; }
  if (del)  { delete FILTERS[del.dataset.delf]; closePop(); applyFilters(); return; }
  if (edit) { openValuePicker(edit.dataset.editf, edit.closest('.f-chip')); return; }
  if (pick) { FILTERS[pick.dataset.pickf] = FILTERS[pick.dataset.pickf] || [];
              applyFilters();
              openValuePicker(pick.dataset.pickf, document.getElementById('f-add')); return; }
  if (tog && POP_FIELD) {
    const f = POP_FIELD, v = tog.dataset.togv;
    const s = new Set(FILTERS[f] || []);
    s.has(v) ? s.delete(v) : s.add(v);
    FILTERS[f] = [...s];
    applyFilters();
    /* パネルは開いたまま更新（連続で選べる）。チップは描き直されているので引き直す */
    const anchor = document.querySelector('[data-editf="' + f + '"]');
    openValuePicker(f, anchor ? anchor.closest('.f-chip') : document.getElementById('f-add'));
    return;
  }
  if (!hit('#f-pop')) closePop();
});

/* defs の表示順どおりに束ねる。defs に無いキーは末尾へ回す。 */
function groupTasks(axisKey, tasks) {
  if (axisKey === 'none')
    return tasks.length ? [{ key:'*', label:'すべて', color:'var(--accent)', items:tasks }] : [];
  const ax = AXES[axisKey] || Object.values(AXES)[0];
  const m = {};
  tasks.forEach(t => { const k = ax.keyOf(t); (m[k] = m[k] || []).push(t); });
  const out = [];
  ax.defs().forEach(d => {
    if (m[d.key]) { out.push(Object.assign({}, d, { items:m[d.key] })); delete m[d.key]; }
  });
  Object.keys(m).forEach(k => out.push({ key:k, label:k, color:'var(--muted)', items:m[k] }));
  return out;
}

/* ---- ソート比較の共通土台。個々の SORT_METRICS はページごとに定義する ---- */
function dirSign(dir) { return dir === 'desc' ? -1 : 1; }
/* hasFn を持つ軸は「無い方を向きに関係なく必ず末尾」に固定し、ある方だけ向きを掛けて比較する。
   hasFn が無い軸は欠損値がスケール上の自然な極値（未設定=0など）なので、
   向きを掛けるだけで十分。 */
function metricCmp(valFn, hasFn) {
  return (x, y, dir) => {
    if (hasFn) {
      const hx = hasFn(x), hy = hasFn(y);
      if (hx !== hy) return hx ? -1 : 1;
      if (!hx) return 0;
    }
    return dirSign(dir) * (valFn(x) - valFn(y));
  };
}
"""
