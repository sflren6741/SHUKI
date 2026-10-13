// ```markmap ブロック → 階層が左から右へ揃う「整列ツリー型」マインドマップ（2026-10-13）。
// mermaid の mindmap は放射状に散らばり整列できない（visualize/reference/mermaid_proportions.md
// の実測で7図全滅）ため、マインドマップは markmap に切り替えた。記法は普通の入れ子リスト
// （見出し # も可）。
//
// 使い方: 描画したい要素の中に <pre class="markmap">（中身は Markdown のテキスト）を置き、
// window.shukiRenderMarkmaps(root) を呼ぶ。対象が無ければ何もしない＝ライブラリも読み込まない。
// 第2引数 {fit: true} は固定枠のサムネイル用（/visualize のギャラリー・タイプカード）：枠いっぱいに
// 縮小して収める。既定（本文用）は文字を縮めず縦に伸ばす。
// d3（280KB）と markmap-view は dashboard_assets/ にローカル同梱（mermaid と同じくオフライン前提）。
(function () {
  'use strict';
  if (window.shukiRenderMarkmaps) return;

  // 枝の色＝dataviz skill の検証済みカテゴリ配色（固定順・ライト/ダーク別）。
  // 文字色は枝の色にせず --fg のまま（色は線と丸だけが持つ）。
  const LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
  const DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
  const NS = 'http://www.w3.org/2000/svg';

  let loading = null;
  function addScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error(src + ' failed to load'));
      document.head.appendChild(s);
    });
  }
  function load() {
    if (window.markmap && window.markmap.Markmap) return Promise.resolve();
    if (!loading) {
      loading = (window.d3 ? Promise.resolve() : addScript('/assets/d3.min.js'))
        .then(() => addScript('/assets/markmap-view.min.js'))
        .catch(e => { loading = null; throw e; });
    }
    return loading;
  }

  let styled = false;
  function injectStyle() {
    if (styled) return;
    styled = true;
    const st = document.createElement('style');
    st.textContent =
      '.shuki-markmap{margin:8px 0;overflow-x:auto;overflow-y:hidden;}' +
      '.shuki-markmap.fit{margin:0;width:100%;height:100%;overflow:hidden;}' +
      '.shuki-markmap.fit svg{pointer-events:none;}' +
      // ページ側の「svg * { max-width:100% }」（/visualize のタイプカード等）がラベルを1語ずつ折り返させるのを打ち消す
      '.shuki-markmap svg.shuki-mm *{max-width:none;}' +
      // markmap 自身の .markmap{…} より詳細度を上げてテーマ変数を渡す
      'svg.markmap.shuki-mm{display:block;' +
      '--markmap-text-color:var(--fg,#222);' +
      '--markmap-font:400 14px/1.4 var(--font-ui,system-ui,sans-serif);' +
      '--markmap-circle-open-bg:var(--card,#fff);' +
      '--markmap-code-bg:var(--bg,#f0f0f0);--markmap-code-color:var(--fg,#222);' +
      '--markmap-a-color:var(--accent,#0097e6);--markmap-a-hover-color:var(--accent,#0097e6);' +
      '--markmap-highlight-bg:color-mix(in srgb,var(--accent,#e0b) 25%,transparent);}';
    document.head.appendChild(st);
  }

  function isDark() {
    const probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;visibility:hidden;color:var(--card,var(--bg,#fff))';
    document.body.appendChild(probe);
    const m = getComputedStyle(probe).color.match(/\d+(\.\d+)?/g) || ['255', '255', '255'];
    probe.remove();
    const [r, g, b] = m.slice(0, 3).map(Number);
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
  }

  // ── Markdown（入れ子リスト・見出し）→ {content, children} ──
  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function inline(s) {
    let t = esc(s.trim());
    t = t.replace(/^\[ \]\s+/, '☐ ').replace(/^\[[xX]\]\s+/, '☑ ');
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/==([^=]+)==/g, '<mark>$1</mark>');
    t = t.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    t = t.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '$2').replace(/\[\[([^\]]+)\]\]/g, '$1');
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return t;
  }
  function parse(src) {
    let lines = src.replace(/\r/g, '').split('\n');
    if (lines[0] && lines[0].trim() === '---') {  // markmap のフロントマター（設定）は読み飛ばす
      const end = lines.findIndex((l, k) => k > 0 && l.trim() === '---');
      if (end > 0) lines = lines.slice(end + 1);
    }
    const root = { content: '', children: [] };
    const stack = [{ level: -1, node: root }];
    let last = null;
    const HEAD = /^\s*(#{1,6})\s+(.*)$/, ITEM = /^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$/;
    for (const raw of lines) {
      if (!raw.trim()) continue;
      let level, text, m;
      if ((m = raw.match(HEAD))) { level = m[1].length - 1; text = m[2]; }
      else if ((m = raw.match(ITEM))) { level = 10 + m[1].replace(/\t/g, '    ').length; text = m[2]; }
      else if (last) { last.content += ' ' + inline(raw); continue; }  // 折り返しの続き行
      else { level = 10; text = raw; }
      while (stack[stack.length - 1].level >= level) stack.pop();
      const node = { content: inline(text), children: [] };
      stack[stack.length - 1].node.children.push(node);
      stack.push({ level, node });
      last = node;
    }
    return root.children.length === 1 ? root.children[0] : root;
  }

  async function renderOne(pre, fit) {
    const data = parse(pre.textContent || '');
    if (!data.content && !data.children.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'shuki-markmap' + (fit ? ' fit' : '');
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'shuki-mm');
    svg.style.width = '100%';
    svg.style.height = fit ? '100%' : '160px';
    wrap.appendChild(svg);
    pre.replaceWith(wrap);
    // 非表示（タブ切替前・最小化中など 0×0）のまま描くと文字の大きさが0で測られレイアウトが崩れる。
    // 見えて大きさが付くまで待ってから描く
    const sized = () => wrap.clientWidth > 0 && (!fit || wrap.clientHeight > 0);
    if (!sized()) {
      await new Promise(res => {
        const ro = new ResizeObserver(() => { if (sized()) { ro.disconnect(); res(); } });
        ro.observe(wrap);
      });
    }
    const narrow = (wrap.clientWidth || 600) < 500;
    const opts = window.markmap.deriveOptions({
      color: isDark() ? DARK : LIGHT, colorFreezeLevel: 2,
      maxWidth: narrow ? 150 : 240, spacingHorizontal: narrow ? 28 : 48, spacingVertical: 8,
      paddingX: 8, duration: 0, fitRatio: 1, maxInitialScale: 1, zoom: false, pan: false,
    });
    const mm = new window.markmap.Markmap(svg, opts);
    // 図は文字を縮めずに縦へ伸ばす（mermaid_proportions.md「はみ出すなら縦に」）。
    // 横が本文幅の0.75倍を超えて縮むなら、縮めずに横スクロールにする。
    const resize = () => {
      const { x1, y1, x2, y2 } = mm.state.rect;
      const w = x2 - x1, h = y2 - y1;
      if (!(w > 0 && h > 0)) return;
      const avail = Math.max(wrap.clientWidth - 16, 1);
      let scale = Math.min(1, avail / w);
      if (scale < 0.75) { svg.style.width = Math.ceil(w + 16) + 'px'; scale = 1; }
      else svg.style.width = '100%';
      svg.style.height = Math.ceil(h * scale + 28) + 'px';  // 最下段の丸（半径分）が切れない余白
      mm.fit(1);
    };
    try { await mm.setData(data); }
    catch (e) {
      console.warn('markmap:', e);
      wrap.innerHTML = '<span style="color:var(--muted)">マインドマップを表示できません</span>';
      return;
    }
    if (fit) {  // サムネイル：枠に収まるまで縮小（クリックは親の拡大表示に任せる）
      new ResizeObserver(() => { if (sized()) mm.fit(); }).observe(wrap);  // 枠の大きさが変わったら収め直す
      mm.fit();
      return;
    }
    resize();
    // 枝を畳む/開くと大きさが変わるので枠も合わせる
    svg.addEventListener('click', () => setTimeout(resize, 30));
  }

  window.shukiRenderMarkmaps = function (root, opts) {
    const fit = !!(opts && opts.fit);
    if (!root || !root.querySelectorAll) return Promise.resolve();
    if (!root.querySelectorAll('pre.markmap').length) return Promise.resolve();
    injectStyle();
    return load().then(() => Promise.all([...root.querySelectorAll('pre.markmap')].map(pre =>
      renderOne(pre, fit).catch(e => {
        console.warn('markmap:', e);
        if (pre.isConnected) pre.outerHTML = '<span style="color:var(--muted)">マインドマップを表示できません</span>';
      }))))
      .catch(e => console.warn('markmap:', e));
  };
})();
