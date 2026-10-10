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

# Reusable SVG frames keep the outline crisp and follow the mascot color token.
_BODY = '<path d="M22 36C16 30 17 18 24 12C32 5 45 9 48 18C51 25 48 31 45 36"/>'
_ARMS = {
    "idle": '<path d="M22 36C14 30 6 34 7 43C8 50 18 49 19 43C20 38 13 37 12 41M19 43C14 56 28 58 32 46C36 58 50 56 45 43M45 36C53 30 61 34 60 43C59 50 49 49 48 43C47 38 54 37 55 41M22 36C28 40 27 44 24 48M45 36C39 40 40 44 43 48"/>',
    "wave": '<path d="M22 36C14 30 6 34 7 43C8 50 18 49 19 43C20 38 13 37 12 41M19 43C14 56 28 58 32 46C36 58 50 56 45 43M45 36C55 30 50 17 58 16C62 15 61 21 57 20C55 33 57 40 48 43M22 36C28 40 27 44 24 48M45 36C39 40 40 44 43 48"/>',
    "curl": '<path d="M22 36C9 28 4 42 14 46C22 49 27 40 20 38C15 36 14 41 18 42M14 46C11 56 27 57 32 46C37 57 53 56 51 46M45 36C58 28 63 42 53 46C45 49 40 40 47 38C52 36 53 41 49 42"/>',
}
_EYES = '<circle cx="28" cy="28" r="1.8" fill="currentColor" stroke="none"/><circle cx="39" cy="28" r="1.8" fill="currentColor" stroke="none"/>'
_BLINK = '<path d="M26 28h4M37 28h4"/>'


def sprite_html():
    frames = "".join(
        f'<g class="mascot-frame mascot-{pose}">{_BODY}{_ARMS["idle" if pose == "blink" else pose]}{_BLINK if pose == "blink" else _EYES}</g>'
        for pose in ("idle", "blink", "wave", "curl")
    )
    return ('<span class="shuki-mascot" data-pose="idle" aria-hidden="true">'
            '<svg viewBox="0 0 68 64" width="34" height="32" fill="none" '
            'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
            f'stroke-linejoin="round" focusable="false">{frames}</svg></span>')


def button_html(location):
    settings = dashboard_settings.load_settings()
    if not settings.get("mascot_enabled", True):
        return ""
    wander = ' data-wander="true"' if location == "header" and settings.get("mascot_wander", True) else ""
    return (f'<button type="button" class="mascot-button mascot-{location}" '
            f'aria-label="Wave to Omnipus, your SHUKI guide" title="Say hello to Omnipus"{wander}>'
            + sprite_html() + '</button>')


CSS = r'''
  .mascot-button { box-sizing:border-box; display:inline-flex; align-items:center;
    justify-content:center; flex:0 0 auto; width:44px; height:44px; padding:4px;
    border:0; border-radius:50%; background:transparent; color:var(--mascot-color); cursor:pointer; }
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
  .mascot-header { position:relative; z-index:1; }
  #result:has(.mascot-header[data-wander="true"]) #chat-log {
    min-height:76px; padding-bottom:52px; box-sizing:border-box; }
  .shuki-mascot { display:inline-flex; flex:0 0 auto; width:34px; height:32px;
    color:var(--mascot-color); transform-origin:50% 75%; }
  .shuki-mascot svg { display:block; width:100%; height:100%; overflow:visible; }
  .mascot-frame { display:none; }
  .shuki-mascot[data-pose="idle"] .mascot-idle { display:block; animation:mascot-eyes 8s steps(1,end) infinite; }
  .shuki-mascot[data-pose="idle"] .mascot-blink { display:block; animation:mascot-blink 8s steps(1,end) infinite; }
  .shuki-mascot[data-pose="wave"] .mascot-wave,
  .shuki-mascot[data-pose="curl"] .mascot-curl { display:block; }
  .mascot-header .shuki-mascot { animation:mascot-float 8s ease-in-out infinite; }
  .shuki-mascot.is-greeting { animation:mascot-hop .65s ease-in-out 2; }
  #result[hidden] .shuki-mascot *, #chat-fab[hidden] .shuki-mascot * { animation-play-state:paused; }
  .mascot-page { margin:-4px 0; }
  .result-head > .mascot-button { margin:-8px 0; }
  @keyframes mascot-eyes { 0%,94%,100% { opacity:1; } 95%,98% { opacity:0; } }
  @keyframes mascot-blink { 0%,94%,100% { opacity:0; } 95%,98% { opacity:1; } }
  @keyframes mascot-float { 0%,85%,100% { transform:translateY(0); } 92% { transform:translateY(-2px); } }
  @keyframes mascot-hop { 0%,100% { transform:translateY(0) rotate(0); } 40% { transform:translateY(-4px) rotate(-8deg); } 70% { transform:rotate(6deg); } }
  @media (prefers-reduced-motion:reduce) {
    .shuki-mascot, .shuki-mascot * { animation:none !important; }
    .shuki-mascot[data-pose="idle"] .mascot-blink { display:none; }
    #chat-fab { transition:none; }
    #chat-fab:hover { transform:none; }
  }
'''

JS = r'''
(() => {
  if (window.SHUKI_MASCOT) return;
  const greetings = new WeakMap();
  function greet(host) {
    const sprite = host.querySelector('.shuki-mascot');
    if (!sprite) return;
    const previous = greetings.get(sprite);
    if (previous) previous.forEach(clearTimeout);
    sprite.dataset.pose = 'wave';
    sprite.classList.add('is-greeting');
    greetings.set(sprite, [
      setTimeout(() => { sprite.dataset.pose = 'curl'; }, 700),
      setTimeout(() => {
        sprite.dataset.pose = 'idle';
        sprite.classList.remove('is-greeting');
        greetings.delete(sprite);
      }, 1400)
    ]);
  }
  document.addEventListener('click', event => {
    const host = event.target.closest('.mascot-button, #chat-fab');
    if (host) greet(host);
  });
  const roamer = document.querySelector('.mascot-header[data-wander="true"]');
  const panel = document.getElementById('result');
  const log = document.getElementById('chat-log');
  const conversation = document.getElementById('conversation-view');
  const reduced = matchMedia('(prefers-reduced-motion:reduce)');
  let roaming = null;
  let nextMove = null;
  function stopMoving(park = false) {
    clearTimeout(nextMove);
    nextMove = null;
    if (roaming) {
      const transform = getComputedStyle(roamer).transform;
      roaming.cancel();
      roaming = null;
      roamer.style.transform = transform === 'none' ? '' : transform;
    }
    if (park && roamer) roamer.style.transform = '';
  }
  function canRoam() {
    return roamer && !reduced.matches && !document.hidden && !panel.hidden
      && !panel.classList.contains('mini') && !conversation.hidden
      && log.scrollTop + log.clientHeight >= log.scrollHeight - 2
      && !roamer.matches(':hover,:focus-visible');
  }
  function move() {
    stopMoving();
    if (!canRoam()) return;
    const bounds = log.getBoundingClientRect();
    const button = roamer.getBoundingClientRect();
    if (bounds.width < button.width + 8 || bounds.height < button.height + 8) return;
    const matrix = new DOMMatrixReadOnly(getComputedStyle(roamer).transform);
    const originX = button.left - matrix.m41;
    const originY = button.top - matrix.m42;
    const left = bounds.left + 4;
    const top = bounds.top + 4;
    const right = bounds.right - button.width - 4;
    const bottom = bounds.bottom - button.height - 4;
    const messages = [...log.querySelectorAll('.chat-msg')]
      .filter(message => message.getClientRects().length).map(message => message.getBoundingClientRect());
    function clearSpot(x, y) {
      return !messages.some(message => x < message.right + 2 && x + button.width > message.left - 2
        && y < message.bottom + 2 && y + button.height > message.top - 2);
    }
    // Try free space beside shorter messages; the bottom padding is a safe fallback.
    let x = left + Math.random() * (right - left);
    let y = bottom;
    for (let attempt = 0; attempt < 24; attempt++) {
      const nextX = left + Math.random() * (right - left);
      const nextY = top + Math.random() * (bottom - top);
      if (clearSpot(nextX, nextY)) { x = nextX; y = nextY; break; }
    }
    if (!clearSpot(x, y)) return;
    roaming = roamer.animate([
      {transform:`translate(${matrix.m41}px, ${matrix.m42}px)`, opacity:1},
      {opacity:.35, offset:.5},
      {transform:`translate(${x-originX}px, ${y-originY}px)`, opacity:1}
    ], {duration:2600, easing:'ease-in-out', fill:'forwards'});
    roaming.onfinish = () => {
      roaming.commitStyles();
      roaming.cancel();
      roaming = null;
      nextMove = setTimeout(move, 3200 + Math.random() * 2400);
    };
  }
  function syncRoaming() {
    stopMoving(true);
    if (canRoam()) nextMove = setTimeout(move, 1200);
  }
  if (roamer) {
    roamer.addEventListener('pointerenter', () => stopMoving());
    roamer.addEventListener('pointerleave', () => { if (canRoam()) nextMove = setTimeout(move, 1800); });
    roamer.addEventListener('focusin', () => {
      if (roamer.matches(':focus-visible')) stopMoving(true);
    });
    roamer.addEventListener('focusout', syncRoaming);
    const resize = new ResizeObserver(syncRoaming);
    resize.observe(panel);
    resize.observe(log);
    const visibility = new MutationObserver(syncRoaming);
    visibility.observe(panel, {attributes:true, attributeFilter:['hidden','class']});
    visibility.observe(conversation, {attributes:true, attributeFilter:['hidden']});
    document.addEventListener('visibilitychange', syncRoaming);
    log.addEventListener('scroll', syncRoaming, {passive:true});
    reduced.addEventListener('change', syncRoaming);
    syncRoaming();
  }
  window.SHUKI_MASCOT = {greet};
})();
'''
