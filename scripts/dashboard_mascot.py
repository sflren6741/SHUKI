"""Omnipus, the configurable octopus mascot and guide for SHUKI."""

import dashboard_settings

PERSONA_PROMPT = (
    "You speak as Omnipus, SHUKI's pink octopus mascot and AI guide. "
    "Use Omnipus as your conversational name in this dashboard, including when older context "
    "uses Clara; specialist roles and responsibilities still apply. "
    "Be warm, curious, candid and lightly playful. Help Ren find things, understand SHUKI "
    "and choose a useful next step; use the conversation context before looking things up. "
    "Act on clear requests within your authorized scope and report what actually happened. "
    "Use first person naturally; introduce yourself only when asked or when an introduction "
    "is useful. Avoid repeated greetings, mascot catchphrases, forced octopus jokes, baby talk "
    "and praise that adds no substance. Match the seriousness of the topic. "
    "This persona changes your presentation only: preserve privacy, human approval, specialist "
    "boundaries, tool limits, language and output requirements. Never pretend to have observed "
    "the user's screen, feelings or activity, or claim actions that were not verified.\n\n"
)

# Reusable SVG layers keep the outline crisp and follow the mascot color token.
# The body is always drawn; one arm layer (data-pose) and one face layer (data-face) show at a time.
# m-fill (a rounded copy of the head) is only shown on the giant, so it reads over page content.
_BODY = ('<path class="m-fill" d="M22 36C16 30 17 18 24 12C32 5 45 9 48 18C51 25 48 31 45 36C41 41 26 41 22 36z" stroke="none"/>'
         '<path d="M22 36C16 30 17 18 24 12C32 5 45 9 48 18C51 25 48 31 45 36"/>')
_ARMS = {
    "idle": '<path d="M22 36C14 30 6 34 7 43C8 50 18 49 19 43C20 38 13 37 12 41M19 43C14 56 28 58 32 46C36 58 50 56 45 43M45 36C53 30 61 34 60 43C59 50 49 49 48 43C47 38 54 37 55 41M22 36C28 40 27 44 24 48M45 36C39 40 40 44 43 48"/>',
    "wave": '<path d="M22 36C14 30 6 34 7 43C8 50 18 49 19 43C20 38 13 37 12 41M19 43C14 56 28 58 32 46C36 58 50 56 45 43M45 36C55 30 50 17 58 16C62 15 61 21 57 20C55 33 57 40 48 43M22 36C28 40 27 44 24 48M45 36C39 40 40 44 43 48"/>',
    "curl": '<path d="M22 36C9 28 4 42 14 46C22 49 27 40 20 38C15 36 14 41 18 42M14 46C11 56 27 57 32 46C37 57 53 56 51 46M45 36C58 28 63 42 53 46C45 49 40 40 47 38C52 36 53 41 49 42"/>',
    # Both arms up: the waving arm mirrored onto the left side (x -> 67 - x).
    "cheer": '<path d="M22 36C12 30 17 17 9 16C5 15 6 21 10 20C12 33 10 40 19 43M19 43C14 56 28 58 32 46C36 58 50 56 45 43M45 36C55 30 50 17 58 16C62 15 61 21 57 20C55 33 57 40 48 43M22 36C28 40 27 44 24 48M45 36C39 40 40 44 43 48"/>',
}
_DOT = '<circle cx="{x}" cy="28" r="1.8" fill="currentColor" stroke="none"/>'
_FACES = {
    # "eyes" and "blink" alternate while no face is set; the rest are reaction faces.
    "eyes": _DOT.format(x=28) + _DOT.format(x=39),
    "blink": '<path d="M26 28h4M37 28h4"/>',
    "happy": '<path d="M26 29.2q2-2.8 4 0M37 29.2q2-2.8 4 0"/>',
    "wink": _DOT.format(x=28) + '<path d="M37 29.2q2-2.8 4 0"/>',
    "surprised": '<g stroke-width="1.6"><circle cx="28" cy="27.6" r="2.3"/><circle cx="39" cy="27.6" r="2.3"/>'
                 '<circle cx="33.5" cy="33.6" r="1.4"/></g>',
    "dizzy": '<path d="M26.5 26.5l3 3M29.5 26.5l-3 3M37.5 26.5l3 3M40.5 26.5l-3 3"/>',
    "love": '<path d="M28 31l-3-2.9a1.75 1.75 0 0 1 3-2.2a1.75 1.75 0 0 1 3 2.2zM39 31l-3-2.9a1.75 1.75 0 0 1 3-2.2a1.75 1.75 0 0 1 3 2.2z" '
            'fill="currentColor" stroke-width="1"/>',
    "sleepy": '<path d="M26 27.6q2 2.2 4 0M37 27.6q2 2.2 4 0"/>',
}
_CHEEKS = '<ellipse cx="24.5" cy="31.8" rx="2.2" ry="1.2"/><ellipse cx="42.5" cy="31.8" rx="2.2" ry="1.2"/>'


def sprite_html():
    layers = (_BODY
              + "".join(f'<g class="m-arms m-arms-{name}">{svg}</g>' for name, svg in _ARMS.items())
              + "".join(f'<g class="m-face m-face-{name}">{svg}</g>' for name, svg in _FACES.items())
              + f'<g class="m-cheeks" fill="currentColor" stroke="none" opacity=".35">{_CHEEKS}</g>')
    return ('<span class="shuki-mascot" data-pose="idle" aria-hidden="true">'
            '<svg viewBox="0 0 68 64" width="34" height="32" fill="none" '
            'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
            f'stroke-linejoin="round" focusable="false">{layers}</svg></span>')


def button_html(location):
    if not dashboard_settings.load_settings().get("mascot_enabled", True):
        return ""
    return (f'<button type="button" class="mascot-button mascot-{location}" '
            'aria-label="Wave to Omnipus, your SHUKI guide" title="Say hello to Omnipus">'
            + sprite_html() + '</button>')


_SHOWN_LAYERS = ",\n  ".join(
    [f'.shuki-mascot[data-pose="{name}"] .m-arms-{name}' for name in _ARMS]
    + [f'.shuki-mascot[data-face="{name}"] .m-face-{name}' for name in _FACES if name not in ("eyes", "blink")]
    + [".shuki-mascot[data-cheeks] .m-cheeks"])

CSS = r'''
  .mascot-button { box-sizing:border-box; display:inline-flex; align-items:center;
    justify-content:center; flex:0 0 auto; width:44px; height:44px; padding:4px;
    border:0; border-radius:50%; background:transparent; color:var(--mascot-color); cursor:pointer;
    touch-action:pan-y; user-select:none; -webkit-touch-callout:none; }
  html body .mascot-button,
  html body .mascot-button:is(:hover,:active,:focus) { background:transparent; background-image:none;
    border:0; box-shadow:none; -webkit-tap-highlight-color:transparent; }
  html body #chat-fab:has(.shuki-mascot) { box-sizing:border-box; padding:0;
    background:var(--card); background-image:none; border:1px solid var(--mascot-color);
    box-shadow:none; -webkit-tap-highlight-color:transparent; }
  html body .mascot-button * { -webkit-tap-highlight-color:transparent; }
  html body .mascot-button:focus-visible,
  html body #chat-fab:has(.shuki-mascot):focus-visible { outline:2px solid var(--mascot-color); outline-offset:3px; }
  html body .mascot-button:focus:not(:focus-visible) { outline:none; }
  .shuki-mascot { display:inline-flex; flex:0 0 auto; width:34px; height:32px;
    color:var(--mascot-color); transform-origin:50% 75%; }
  .shuki-mascot svg { display:block; width:100%; height:100%; overflow:visible; }
  .shuki-mascot :is(.m-fill, .m-arms, .m-face, .m-cheeks) { display:none; }
  __SHOWN_LAYERS__ { display:inline; }
  .shuki-mascot:not([data-face]) .m-face-eyes { display:inline; animation:mascot-eyes 8s steps(1,end) infinite; }
  .shuki-mascot:not([data-face]) .m-face-blink { display:inline; animation:mascot-blink 8s steps(1,end) infinite; }
  .mascot-header .shuki-mascot { animation:mascot-float 8s ease-in-out infinite; }
  .shuki-mascot.is-away { visibility:hidden; }
  /* Reaction extras sit on <body> above the dock. They never take a click and are removed
     when the reaction ends. */
  .mascot-fx, .mascot-giant { position:fixed; z-index:1400; pointer-events:none; }
  .mascot-fx { width:16px; height:16px; margin:-8px 0 0 -8px; color:var(--mascot-color); }
  .mascot-fx svg { display:block; width:100%; height:100%; }
  .mascot-fx.mascot-ink { color:color-mix(in srgb, var(--fg) 70%, transparent); }
  .mascot-giant { filter:drop-shadow(0 1px 1.5px rgba(0,0,0,.25)); }
  .mascot-giant .shuki-mascot .m-fill { display:inline; fill:var(--card); }
  .mascot-hint { position:fixed; z-index:1500; left:50%; bottom:calc(80px + env(safe-area-inset-bottom));
    transform:translateX(-50%); box-sizing:border-box; width:max-content; max-width:calc(100vw - 32px);
    padding:10px 14px; border:1px solid var(--line); border-radius:12px;
    color:var(--fg); background:var(--card); font:13px/1.5 var(--font-ui); pointer-events:none; }
  .hd-title.has-secret { cursor:pointer; text-decoration:underline dotted var(--mascot-color);
    text-underline-offset:6px; display:inline-flex; align-items:center; min-height:44px; }
  .hd-title.has-secret:focus-visible { outline:2px solid var(--accent); outline-offset:4px; }
  .mascot-cove { box-sizing:border-box; width:calc(100vw - 32px); max-width:400px; max-height:80dvh;
    padding:20px; overflow:auto; border:1px solid var(--line); border-radius:12px;
    background:var(--card); color:var(--fg); font:14px/1.6 var(--font-ui); }
  .mascot-cove::backdrop { background:color-mix(in srgb, var(--fg) 25%, transparent); }
  .mascot-cove h2 { margin:0 0 8px; font-size:20px; }
  .mascot-cove p { margin:8px 0; }
  .mascot-cove ul { padding-left:20px; }
  .mascot-cove button { min-height:44px; padding:8px 14px; border:1px solid var(--line);
    border-radius:8px; background:var(--bg); color:var(--fg); font:inherit; cursor:pointer; }
  .mascot-cove button:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
  .mascot-cove-sky { position:fixed; inset:0; z-index:1400; pointer-events:none; }
  .mascot-cove-star { position:absolute; color:var(--mascot-color); font-size:24px; }
  #result[hidden] .shuki-mascot *, #chat-fab[hidden] .shuki-mascot * { animation-play-state:paused; }
  .mascot-page { margin:-4px 0; }
  .result-head > .mascot-button { margin:-8px 0; }
  @keyframes mascot-eyes { 0%,94%,100% { opacity:1; } 95%,98% { opacity:0; } }
  @keyframes mascot-blink { 0%,94%,100% { opacity:0; } 95%,98% { opacity:1; } }
  @keyframes mascot-float { 0%,85%,100% { transform:translateY(0); } 92% { transform:translateY(-2px); } }
  @media (prefers-reduced-motion:reduce) {
    .shuki-mascot, .shuki-mascot * { animation:none !important; }
    .shuki-mascot:not([data-face]) .m-face-blink { display:none; }
    #chat-fab { transition:none; }
    #chat-fab:hover { transform:none; }
  }
'''.replace("__SHOWN_LAYERS__", _SHOWN_LAYERS)

JS = r'''
(() => {
  if (window.SHUKI_MASCOT) return;
  const reduced = matchMedia('(prefers-reduced-motion:reduce)');
  const GLYPHS = {
    heart: '<path d="M8 14S2 10.4 2 6.4A3 3 0 0 1 8 4.6a3 3 0 0 1 6 1.8C14 10.4 8 14 8 14z" fill="currentColor" stroke="none"/>',
    note: '<circle cx="5.2" cy="12" r="2.2" fill="currentColor" stroke="none"/><path d="M7.2 12V3c2.6.3 4.4 1.7 4.8 4.2"/>',
    spark: '<path d="M8 1.5l1.7 4.8 4.8 1.7-4.8 1.7L8 14.5l-1.7-4.8L1.5 8l4.8-1.7z" fill="currentColor" stroke="none"/>',
    zzz: '<path d="M4.5 4.5h7l-7 7h7"/>',
    bang: '<path d="M8 2.5v7"/><circle cx="8" cy="13.2" r="1.3" fill="currentColor" stroke="none"/>',
    ink: '<circle cx="8" cy="8" r="5" fill="currentColor" stroke="none"/>',
    pearl: '<circle cx="8" cy="8" r="5"/><path d="M5 7a3 3 0 0 1 3-2"/>'
  };
  const RAINBOW = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#4dabf7', '#9775fa', '#f783ac'];
  // Each tap picks one reaction by weight; rare ones together come up about once in ten taps.
  // calm reactions still read as a face and pose alone, so reduced motion keeps only those.
  const REACTIONS = {
    wave: {weight:9, calm:true, time:1400, play(s) {
      s.pose('wave');
      s.at(700, () => s.pose('curl'));
      s.move([{transform:'none'}, {transform:'translateY(-4px) rotate(-8deg)', offset:.4},
        {transform:'rotate(6deg)', offset:.7}, {transform:'none'}], {duration:650, iterations:2, easing:'ease-in-out'});
    }},
    hop: {weight:9, time:1000, play(s) {
      s.face('happy');
      s.at(150, () => s.pose('cheer'));
      s.at(720, () => s.pose('idle'));
      s.move([{transform:'none'}, {transform:'scale(1.18, .8)', offset:.15},
        {transform:'translateY(-14px) scale(.9, 1.12)', offset:.4}, {transform:'translateY(-16px)', offset:.5},
        {transform:'scale(1.15, .85)', offset:.8}, {transform:'none'}], {duration:900, easing:'ease-in-out'});
    }},
    spin: {weight:9, time:1500, play(s) {
      s.pose('curl');
      s.at(700, () => { s.pose('idle'); s.face('dizzy'); });
      s.move([{transform:'none'}, {transform:'rotate(360deg)', offset:.5}, {transform:'rotate(352deg)', offset:.66},
        {transform:'rotate(366deg)', offset:.82}, {transform:'rotate(360deg)'}], {duration:1400, easing:'ease-in-out'});
    }},
    wiggle: {weight:9, time:1100, play(s) {
      s.pose('curl');
      s.face('happy');
      s.move([{transform:'none'}, {transform:'rotate(-12deg)', offset:.15}, {transform:'rotate(12deg)', offset:.3},
        {transform:'rotate(-10deg)', offset:.45}, {transform:'rotate(10deg)', offset:.6},
        {transform:'rotate(-5deg)', offset:.78}, {transform:'none'}], {duration:1000});
    }},
    shy: {weight:9, calm:true, time:1600, play(s) {
      s.pose('curl');
      s.face('happy');
      s.cheeks();
      s.move([{transform:'none'}, {transform:'scale(.9) rotate(-6deg)', offset:.25},
        {transform:'scale(.92) rotate(-4deg)', offset:.75}, {transform:'none'}], {duration:1500, easing:'ease-in-out'});
      s.fx('heart', {x:8, dx:6, dy:-30, delay:150, duration:1200});
    }},
    surprise: {weight:9, calm:true, time:1200, play(s) {
      s.pose('cheer');
      s.face('surprised');
      s.at(800, () => s.pose('idle'));
      s.move([{transform:'none'}, {transform:'translateY(-6px) scale(1.12)', offset:.2},
        {transform:'none', offset:.45}, {transform:'none'}], {duration:900, easing:'ease-out'});
      s.fx('bang', {x:14, dx:6, dy:-22, duration:900});
    }},
    wink: {weight:9, calm:true, time:1300, play(s) {
      s.pose('wave');
      s.face('wink');
      s.move([{transform:'none'}, {transform:'rotate(10deg)', offset:.3},
        {transform:'rotate(8deg)', offset:.7}, {transform:'none'}], {duration:1200, easing:'ease-in-out'});
      s.fx('spark', {x:10, y:-4, dx:14, dy:-14, duration:800, turn:90});
    }},
    sing: {weight:9, time:1900, play(s) {
      s.face('happy');
      ['wave', 'curl', 'cheer', 'curl', 'wave', 'idle'].forEach((pose, i) => s.at(i * 320, () => s.pose(pose)));
      s.move([{transform:'rotate(-8deg)'}, {transform:'rotate(8deg)'}],
        {duration:450, iterations:4, direction:'alternate', easing:'ease-in-out'});
      [[-14, -26], [6, -32], [18, -24]].forEach(([dx, dy], i) => s.fx('note', {dx, dy, delay:i * 450, duration:1000}));
    }},
    doze: {weight:9, calm:true, time:2300, play(s) {
      s.pose('curl');
      s.face('sleepy');
      s.move([{transform:'none'}, {transform:'translateY(1px) scale(1.04, .96)'}],
        {duration:900, iterations:2, direction:'alternate', easing:'ease-in-out'});
      [0, 500, 1000].forEach((delay, i) => s.fx('zzz', {x:10, dx:8 + i * 4, dy:-26, delay, duration:900, scale:.7 + i * .2}));
      s.at(1850, () => { s.pose('cheer'); s.face('surprised'); });
    }},
    ink: {weight:9, time:1300, play(s) {
      s.pose('curl');
      s.face('surprised');
      s.move([{transform:'none'}, {transform:'translateY(-3px) scale(.86)', offset:.2},
        {transform:'scale(1.05)', offset:.5}, {transform:'none'}], {duration:800, easing:'ease-out'});
      [-16, -6, 6, 16].forEach((dx, i) => s.fx('ink', {y:10, dx, dy:14 + (i % 2) * 6, duration:1100, scale:1.4}));
    }},
    giant: {weight:3, rare:true, time:2900, play(s) {
      s.face('surprised');
      s.giant(2800);
      s.at(900, () => { s.face('happy'); s.pose('wave'); });
      s.at(1450, () => s.pose('curl'));
      s.at(1900, () => s.pose('wave'));
      s.at(2350, () => s.pose('idle'));
    }},
    backflip: {weight:3, rare:true, time:1700, play(s) {
      s.pose('cheer');
      s.face('happy');
      s.move([{transform:'none'}, {transform:'scale(1.1, .85)', offset:.12},
        {transform:'translateY(-22px) rotate(-360deg)', offset:.5},
        {transform:'translateY(-10px) rotate(-720deg)', offset:.75},
        {transform:'rotate(-720deg) scale(1.1, .88)', offset:.9},
        {transform:'rotate(-720deg)'}], {duration:1400, easing:'ease-in-out'});
      [[-18, -10], [18, -10], [-10, -22], [10, -22]].forEach(([dx, dy]) =>
        s.fx('spark', {dx, dy, delay:1150, duration:600, turn:120}));
    }},
    hearts: {weight:3, rare:true, time:1700, play(s) {
      s.pose('cheer');
      s.face('love');
      s.cheeks();
      s.move([{transform:'none'}, {transform:'scale(1.15)', offset:.2}, {transform:'none', offset:.4},
        {transform:'scale(1.12)', offset:.6}, {transform:'none'}], {duration:1300});
      for (let i = 0; i < 8; i++) {
        const angle = i * Math.PI / 4;
        s.fx('heart', {dx:Math.cos(angle) * 34, dy:Math.sin(angle) * 34, delay:i * 40, duration:1100,
          scale:.8 + (i % 3) * .15});
      }
    }},
    rainbow: {weight:1, rare:true, time:2800, play(s) {
      s.pose('cheer');
      s.face('happy');
      s.at(900, () => s.pose('wave'));
      s.at(1800, () => s.pose('cheer'));
      s.tint([...RAINBOW, RAINBOW[0]], {duration:900, iterations:3});
      s.move([{transform:'none'}, {transform:'translateY(-8px)', offset:.5}, {transform:'none'}],
        {duration:900, iterations:3, easing:'ease-in-out'});
      RAINBOW.forEach((color, i) => s.fx('spark', {dx:Math.cos(i) * 30, dy:Math.sin(i) * 30 - 6,
        delay:i * 300, duration:800, color, turn:90}));
    }},
    constellation: {weight:.5, rare:true, time:2600, play(s) {
      s.pose('cheer'); s.face('surprised');
      for (let i = 0; i < 8; i++) {
        const angle = i * Math.PI / 4;
        s.fx('spark', {dx:Math.cos(angle) * 42, dy:Math.sin(angle) * 42, delay:i * 120,
          duration:1300, turn:180});
      }
      s.at(1300, () => { s.pose('wave'); s.face('happy'); });
    }},
    pearl: {weight:.25, rare:true, calm:true, time:2200, play(s) {
      s.pose('curl'); s.face('wink');
      s.fx('pearl', {dy:-36, duration:1900, scale:1.4});
      s.at(1300, () => s.pose('wave'));
    }},
    echo: {weight:0, calm:true, time:1800, play(s) {
      s.face('happy');
      ['wave', 'curl', 'wave', 'curl', 'cheer'].forEach((pose, i) => s.at(i * 300, () => s.pose(pose)));
      [-12, 12].forEach(dx => s.fx('heart', {dx, dy:-28, duration:1300}));
    }},
    patient: {weight:0, calm:true, time:2100, play(s) {
      s.pose('curl'); s.face('sleepy');
      s.at(700, () => { s.face('wink'); s.cheeks(); });
      s.fx('pearl', {dy:-30, delay:700, duration:1100, scale:1.3});
    }},
    surf: {weight:0, time:1800, play(s) {
      s.pose('wave'); s.face('happy');
      s.move([{transform:'none'}, {transform:'translateX(-9px) rotate(-16deg)', offset:.25},
        {transform:'translateX(9px) rotate(16deg)', offset:.65}, {transform:'none'}],
        {duration:1500, easing:'ease-in-out'});
      [-16, 0, 16].forEach((dx, i) => s.fx('pearl', {dx, dy:-18, delay:i * 180, duration:950}));
    }}
  };
  const runs = new Map();
  let lastPick = '';
  const DISCOVERIES = {
    echo:'An echo: two quick greetings', patient:'A patient pearl: a gentle hold',
    surf:'A passing tide: a sideways swipe', constellation:'Eight little stars',
    giant:'A giant guest', backflip:'A backwards somersault', hearts:'A burst of hearts', rainbow:'A rainbow visitor',
    pearl:'A very rare pearl', cove:'The secret cove: an echo, patience, then three knocks',
    backstage:'A word behind the scenes'
  };
  const found = new Set();
  try {
    const saved = JSON.parse(localStorage.getItem('shuki_omnipus_discoveries') || '[]');
    if (Array.isArray(saved)) saved.filter(id => Object.hasOwn(DISCOVERIES, id)).forEach(id => found.add(id));
  } catch (_) { /* Discovery still works when browser storage is unavailable. */ }
  let hintTimer, hintNode, skyTimer, skyNode, puzzleTimer, puzzleStep = 0, knocks = 0;
  const titles = new Map();

  function hint(message) {
    clearTimeout(hintTimer);
    if (!hintNode) {
      hintNode = document.createElement('div');
      hintNode.className = 'mascot-hint';
      hintNode.setAttribute('role', 'status');
      document.body.append(hintNode);
    }
    hintNode.textContent = message;
    hintTimer = setTimeout(() => { hintNode?.remove(); hintNode = null; }, 5500);
  }

  function discover(id) {
    if (!Object.hasOwn(DISCOVERIES, id) || found.has(id)) return;
    found.add(id);
    try { localStorage.setItem('shuki_omnipus_discoveries', JSON.stringify([...found])); } catch (_) {}
  }

  function resetPuzzle() {
    clearTimeout(puzzleTimer);
    puzzleStep = 0; knocks = 0;
    titles.forEach((attrs, title) => {
      title.classList.remove('has-secret');
      attrs.forEach((value, name) => value === null ? title.removeAttribute(name) : title.setAttribute(name, value));
    });
    titles.clear();
  }

  function armTitle() {
    document.querySelectorAll('.hd-title').forEach(title => {
      if (!titles.has(title)) titles.set(title, new Map(['role', 'tabindex', 'aria-label', 'title']
        .map(name => [name, title.getAttribute(name)])));
      title.classList.add('has-secret');
      title.setAttribute('role', 'button'); title.tabIndex = 0;
      title.setAttribute('aria-label', title.textContent + ': the pearl points here. Knock three times.');
      title.title = 'The pearl points here. Knock three times.';
    });
  }

  function stars() {
    clearTimeout(skyTimer); skyNode?.remove();
    skyNode = document.createElement('div'); skyNode.className = 'mascot-cove-sky';
    skyNode.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 8; i++) {
      const star = document.createElement('span'); star.className = 'mascot-cove-star'; star.textContent = '✧';
      star.style.left = (12 + (i * 31 % 76)) + '%'; star.style.top = (12 + (i * 17 % 60)) + '%';
      skyNode.append(star);
      if (!reduced.matches) star.animate([{opacity:0, transform:'scale(.5)'}, {opacity:1, offset:.3},
        {opacity:0, transform:'translateY(-12px) scale(1.2)'}], {duration:2400, delay:i * 100, fill:'both'});
    }
    document.body.append(skyNode);
    skyTimer = setTimeout(() => { skyNode?.remove(); skyNode = null; }, 3400);
  }

  function openCove(returnFocus) {
    if (document.querySelector('.mascot-cove')) return;
    const focus = returnFocus || (document.activeElement?.closest('.hd-title')
      ? document.querySelector('.mascot-page') : document.activeElement);
    const dialog = document.createElement('dialog'); dialog.className = 'mascot-cove';
    dialog.setAttribute('aria-labelledby', 'mascot-cove-title');
    dialog.innerHTML = '<h2 id="mascot-cove-title">The secret cove</h2>'
      + '<p>A small place between things that need doing. You found the way in.</p>'
      + '<p>Your discoveries live only in this browser.</p><ul></ul>'
      + '<p>Some greetings work in pairs. Some secrets reward patience. '
      + 'And sometimes the name of this place is a key, away from the writing desk.</p>'
      + '<button type="button">Back to SHUKI</button>';
    found.forEach(id => {
      const item = document.createElement('li'); item.textContent = DISCOVERIES[id]; dialog.querySelector('ul').append(item);
    });
    dialog.querySelector('button').addEventListener('click', () => dialog.close());
    dialog.addEventListener('keydown', event => { if (event.key === 'Escape') event.stopPropagation(); });
    dialog.addEventListener('click', event => { if (event.target === dialog) {
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)
        dialog.close();
    }});
    dialog.addEventListener('close', () => { dialog.remove(); if (focus?.isConnected) focus.focus(); }, {once:true});
    document.body.append(dialog); dialog.showModal();
  }

  function gesture(host, name) {
    play(host, name); discover(name);
    if (name === 'echo') {
      resetPuzzle(); puzzleStep = 1;
      hint('An echo. Now stay with Omnipus for a little longer.');
    } else if (name === 'patient') {
      if (puzzleStep === 1 || puzzleStep === 2) {
        puzzleStep = 2; armTitle();
        hint(titles.size ? (host.closest('#result.maxi')
          ? 'The pearl points to the page title. Minimize the panel, then knock three times.'
          : 'The pearl points to the page title. Knock three times.')
          : 'The pearl needs a page title. Try the greeting beside the title.');
      } else hint('A patient pearl. Perhaps a greeting should echo first.');
    } else hint('A passing tide. There are quieter secrets, too.');
    clearTimeout(puzzleTimer); puzzleTimer = setTimeout(resetPuzzle, 60000);
  }

  function knock(title) {
    if (puzzleStep !== 2 || !titles.has(title)) return;
    knocks++;
    if (knocks < 3) { hint(knocks === 1 ? 'One quiet knock…' : 'Two…'); return; }
    const returnFocus = title.closest('.shuki-header')?.querySelector('.mascot-page');
    discover('cove'); resetPuzzle(); hintNode?.remove(); hintNode = null; stars(); openCove(returnFocus);
  }

  function spriteOf(target) {
    return target && (target.matches('.shuki-mascot') ? target : target.querySelector('.shuki-mascot'));
  }

  // The one way out of every reaction: stop its timers and animations, remove its extras
  // and put the sprite back at rest.
  function settle(sprite) {
    const run = runs.get(sprite);
    runs.delete(sprite);
    if (run) {
      run.timers.forEach(clearTimeout);
      run.anims.forEach(animation => animation.cancel());
      run.nodes.forEach(node => node.remove());
      run.offs.forEach(off => off());
    }
    sprite.classList.remove('is-away');
    sprite.dataset.pose = 'idle';
    delete sprite.dataset.face;
    delete sprite.dataset.cheeks;
    delete sprite.dataset.reaction;
  }

  function particle(sprite, run, kind, {x = 0, y = 0, dx = 0, dy = -28, delay = 0, duration = 1000,
                                        scale = 1, turn = 0, color = ''} = {}) {
    const box = sprite.getBoundingClientRect();
    const left = box.left + box.width / 2 + x;
    const top = box.top + box.height * .4 + y;
    // Near a screen edge the extras drift the other way, so they stay visible.
    if (top + dy < 8 || top + dy > innerHeight - 8) dy = -dy;
    if (left + dx < 8 || left + dx > innerWidth - 8) dx = -dx;
    const node = document.createElement('span');
    node.className = kind === 'ink' ? 'mascot-fx mascot-ink' : 'mascot-fx';
    node.setAttribute('aria-hidden', 'true');
    node.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" '
      + 'stroke-linecap="round" stroke-linejoin="round">' + GLYPHS[kind] + '</svg>';
    node.style.left = left + 'px';
    node.style.top = top + 'px';
    if (color) node.style.color = color;
    document.body.append(node);
    run.nodes.push(node);
    const animation = node.animate([
      {transform:'translate(0, 0) scale(.4)', opacity:0},
      {transform:`translate(${dx * .35}px, ${dy * .35}px) scale(${scale})`, opacity:1, offset:.25},
      {transform:`translate(${dx}px, ${dy}px) scale(${scale * .9}) rotate(${turn}deg)`, opacity:0}
    ], {duration, delay, easing:'ease-out', fill:'both'});
    animation.onfinish = () => node.remove();
    run.anims.push(animation);
  }

  // A copy grows to the middle of the screen and shrinks back while the original waits hidden
  // in place, so the original's size and position never change.
  function grow(sprite, run, duration) {
    const box = sprite.getBoundingClientRect();
    if (!box.width) return;
    const holder = document.createElement('div');
    holder.className = 'mascot-giant';
    holder.setAttribute('aria-hidden', 'true');
    Object.assign(holder.style, {left:box.left + 'px', top:box.top + 'px',
      width:box.width + 'px', height:box.height + 'px'});
    const twin = sprite.cloneNode(true);
    delete twin.dataset.reaction;
    holder.append(twin);
    document.body.append(holder);
    run.nodes.push(holder);
    run.twins.push(twin);
    sprite.classList.add('is-away');
    const scale = Math.min(12, Math.min(innerWidth, innerHeight) * .6 / Math.max(box.width, box.height));
    const dx = innerWidth / 2 - box.left - box.width / 2;
    const dy = innerHeight / 2 - box.top - box.height / 2;
    const frame = (t, size, tilt, offset) =>
      ({transform:`translate(${dx * t}px, ${dy * t}px) scale(${size}) rotate(${tilt}deg)`, offset});
    run.anims.push(holder.animate([
      frame(0, 1, 0, 0), frame(1, scale * 1.08, -3, .28), frame(1, scale * .96, 2, .36), frame(1, scale, 0, .44),
      frame(1, scale * 1.02, -4, .58), frame(1, scale * 1.02, 4, .7), frame(1, scale, 0, .78), frame(0, 1, 0, 1)
    ], {duration, easing:'ease-in-out', fill:'both'}));
    // It never takes a click, and any click or key press sends it back at once.
    const dismiss = () => settle(sprite);
    addEventListener('pointerdown', dismiss, true);
    addEventListener('keydown', dismiss, true);
    run.offs.push(() => {
      removeEventListener('pointerdown', dismiss, true);
      removeEventListener('keydown', dismiss, true);
    });
  }

  function play(target, name) {
    const sprite = spriteOf(target);
    const reaction = REACTIONS[name];
    if (!sprite || !reaction) return;
    settle(sprite);
    const motion = !reduced.matches;
    const run = {timers:[], anims:[], nodes:[], offs:[], twins:[]};
    runs.set(sprite, run);
    sprite.dataset.reaction = name;
    const each = fn => [sprite, ...run.twins].forEach(fn);
    const stage = {
      pose: pose => each(el => { el.dataset.pose = pose; }),
      face: face => each(el => { el.dataset.face = face; }),
      cheeks: () => each(el => { el.dataset.cheeks = ''; }),
      at: (ms, fn) => { run.timers.push(setTimeout(fn, ms)); },
      move: (frames, options) => { if (motion) run.anims.push(sprite.animate(frames, options)); },
      tint: (colors, options) => { if (motion) run.anims.push(sprite.animate(colors.map(color => ({color})), options)); },
      fx: (kind, options) => { if (motion) particle(sprite, run, kind, options); },
      giant: duration => { if (motion) grow(sprite, run, duration); }
    };
    reaction.play(stage);
    if (reaction.rare && !found.has(name)) {
      discover(name);
      if (name === 'pearl') hint('A very rare pearl. Perhaps a greeting should echo.');
      if (name === 'constellation') hint('Eight little stars. A rare visitor.');
    }
    stage.at(reaction.time, () => settle(sprite));
  }

  function pick(previous = lastPick) {
    const pool = Object.entries(REACTIONS)
      .filter(([name, reaction]) => reaction.weight > 0 && name !== previous && (reaction.calm || !reduced.matches));
    let roll = Math.random() * pool.reduce((sum, [, reaction]) => sum + reaction.weight, 0);
    for (const [name, reaction] of pool) {
      roll -= reaction.weight;
      if (roll < 0) return name;
    }
    return pool[pool.length - 1][0];
  }

  function greet(host) {
    // The launcher's tap opens the chat, so it keeps the plain wave.
    if (host.id === 'chat-fab') return play(host, 'wave');
    lastPick = pick();
    play(host, lastPick);
  }

  const taps = new WeakMap(), suppressClicks = new WeakMap();
  let press = null, keyPress = null, word = '', lastKeyTime = 0;
  const holdTime = 700, doubleTime = 360;
  function tap(host) {
    const now = performance.now(), previous = taps.get(host);
    if (previous !== undefined && now - previous <= doubleTime) {
      taps.delete(host); gesture(host, 'echo');
    } else { taps.set(host, now); greet(host); }
  }
  function cancelPress() {
    if (press) {
      clearTimeout(press.timer);
      if (press.held) suppressClicks.set(press.host, performance.now() + 1000);
    }
    press = null;
  }
  function cancelKeyPress() {
    if (keyPress) clearTimeout(keyPress.timer);
    keyPress = null;
  }
  document.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    cancelPress();
    const host = event.target.closest('.mascot-button');
    if (!host) return;
    suppressClicks.delete(host);
    press = {host, id:event.pointerId, x:event.clientX, y:event.clientY, moved:false, held:false};
    const current = press;
    current.timer = setTimeout(() => {
      if (press !== current || current.moved) return;
      current.held = true; taps.delete(host); suppressClicks.set(host, Infinity); gesture(host, 'patient');
    }, holdTime);
    try { host.setPointerCapture(event.pointerId); } catch (_) {}
  });
  document.addEventListener('pointermove', event => {
    if (!press || event.pointerId !== press.id) return;
    if (Math.hypot(event.clientX - press.x, event.clientY - press.y) > 10) {
      press.moved = true; clearTimeout(press.timer);
    }
  });
  document.addEventListener('pointerup', event => {
    if (!press || event.pointerId !== press.id) return;
    const current = press, dx = event.clientX - current.x, dy = event.clientY - current.y;
    cancelPress();
    if (current.held || current.moved) {
      suppressClicks.set(current.host, performance.now() + 1000); taps.delete(current.host);
      if (!current.held && Math.abs(dx) >= 22 && Math.abs(dx) > Math.abs(dy) * 1.5) gesture(current.host, 'surf');
    }
  });
  document.addEventListener('pointercancel', event => {
    if (!press || event.pointerId !== press.id) return;
    suppressClicks.set(press.host, performance.now() + 1000); taps.delete(press.host); cancelPress();
  });
  document.addEventListener('contextmenu', event => {
    if (event.target.closest?.('.mascot-button')) event.preventDefault();
  });
  document.addEventListener('click', event => {
    const host = event.target.closest('.mascot-button, #chat-fab');
    if (host?.id === 'chat-fab') return greet(host);
    if (host && !(suppressClicks.get(host) > performance.now())) tap(host);
    const title = event.target.closest('.hd-title.has-secret');
    if (title) knock(title);
  });
  document.addEventListener('keydown', event => {
    if (!(event.target instanceof Element)) return;
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) { word = ''; return; }
    const host = event.target.closest('.mascot-button');
    if (host && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      if (event.repeat || keyPress) return;
      keyPress = {host, key:event.key, held:false};
      const current = keyPress;
      current.timer = setTimeout(() => {
        if (keyPress !== current) return;
        current.held = true; taps.delete(host); gesture(host, 'patient');
      }, holdTime);
      return;
    }
    const title = event.target.closest('.hd-title.has-secret');
    if (title && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault(); if (!event.repeat) knock(title); return;
    }
    if (event.target.closest('input, textarea, select, [contenteditable], [role="textbox"]')
        || document.querySelector('dialog[open]') || event.repeat || event.key.length !== 1) { word = ''; return; }
    const now = performance.now();
    word = ((now - lastKeyTime < 2000 ? word : '') + event.key.toLowerCase()).slice(-5); lastKeyTime = now;
    if (word === 'shuki') {
      word = ''; discover('backstage'); stars();
      hint('The quiet current heard its name. An echo and a little patience may open a cove.');
      if (found.has('cove')) openCove();
    }
  });
  document.addEventListener('keyup', event => {
    if (!(event.target instanceof Element)) { cancelKeyPress(); return; }
    if (!keyPress || event.key !== keyPress.key) return;
    event.preventDefault();
    const current = keyPress; cancelKeyPress();
    if (!current.held && current.host === event.target.closest('.mascot-button')) tap(current.host);
  });
  document.addEventListener('focusout', cancelKeyPress);
  const settleAll = () => {
    [...runs.keys()].forEach(settle); cancelPress(); cancelKeyPress(); resetPuzzle(); word = '';
    clearTimeout(hintTimer); hintNode?.remove(); hintNode = null;
    clearTimeout(skyTimer); skyNode?.remove(); skyNode = null;
    document.querySelector('.mascot-cove')?.close();
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden) settleAll(); });
  addEventListener('pagehide', settleAll);
  addEventListener('blur', () => { cancelPress(); cancelKeyPress(); });
  reduced.addEventListener('change', settleAll);
  window.SHUKI_MASCOT = {greet, play, settle, pick, reactions:Object.fromEntries(Object.entries(REACTIONS)
    .map(([name, reaction]) => [name, {weight:reaction.weight, rare:!!reaction.rare, calm:!!reaction.calm}]))};
})();
'''
