"""Shared, read-only command palette. Skills populate drafts; never auto-send."""
import json


def render(pages, skills):
    commands = [dict(label=label, href=href, kind="Page") for label, href in pages]
    commands += [dict(label=s["label"], name=s["name"], kind="Skill",
                      search=s.get("search", ""), description=s.get("description", ""))
                 for s in skills]
    return HTML.replace("__COMMANDS__", json.dumps(commands, ensure_ascii=False).replace("<", "\\u003c"))


HTML = r'''<style>
#command-trigger {min-width:44px;min-height:44px;display:inline-flex;align-items:center;justify-content:center}
#command-palette {padding:0;border:1px solid var(--line);border-radius:12px;background:var(--card);
 color:var(--fg);width:min(640px,calc(100vw - 24px));max-height:80dvh;margin:10dvh auto;
 font-family:var(--font-ui);box-shadow:0 12px 40px color-mix(in srgb,var(--fg) 15%,transparent)}
#command-palette::backdrop {background:color-mix(in srgb,var(--bg) 75%,transparent)}
.command-head {display:flex;align-items:center;gap:8px;padding:12px;border-bottom:1px solid var(--line)}
#command-query {flex:1;min-width:0;min-height:44px;background:var(--bg);color:var(--fg);
 border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit}
#command-palette button {font:inherit;color:inherit;cursor:pointer}
#command-close {min-width:44px;min-height:44px;background:var(--card);border:1px solid var(--line);border-radius:8px}
#command-status {padding:8px 12px;font-size:.78rem;color:var(--muted)}
#command-results {max-height:55dvh;overflow-y:auto;padding:0 8px 8px}
.command-result {display:flex;gap:10px;align-items:center;width:100%;min-height:44px;text-align:left;
 padding:10px 8px;background:transparent;border:1px solid transparent;border-radius:8px;overflow-wrap:anywhere}
.command-result small {color:var(--muted);min-width:42px;font-size:.72rem}
.command-result:hover,.command-result:focus-visible {background:var(--bg);border-color:var(--accent)}
#command-palette :focus-visible,#command-trigger:focus-visible {outline:2px solid var(--accent);outline-offset:2px}
</style>
<dialog id="command-palette" aria-label="Find pages, skills, tasks and notes">
 <div class="command-head"><input id="command-query" type="search" autocomplete="off"
 aria-label="Search pages, skills, tasks and notes" placeholder="Find a page, skill, task or note…">
 <button type="button" id="command-close" aria-label="Close search">Esc</button></div>
 <p id="command-status" role="status" aria-live="polite"></p><div id="command-results"></div>
</dialog>
<script>
(() => {
 const commands = __COMMANDS__, dialog = document.getElementById('command-palette');
 const input = document.getElementById('command-query'), list = document.getElementById('command-results');
 const status = document.getElementById('command-status');
 let previous, generation = 0, timer, controller;
 function close() {
   generation++;clearTimeout(timer);controller?.abort();dialog.close();previous?.focus();
 }
 function open() {
   if (dialog.open) {close();return;}
   previous = document.activeElement;dialog.showModal();input.value='';input.focus();search();
 }
 document.getElementById('command-trigger').addEventListener('click',open);
 document.getElementById('command-close').addEventListener('click',close);
 dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 dialog.addEventListener('click',e => {if(e.target===dialog) {
   const r=dialog.getBoundingClientRect();
   if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom) close();
 }});
 document.addEventListener('keydown',e => {
   if((e.ctrlKey||e.metaKey)&&!e.altKey&&e.key.toLowerCase()==='k') {e.preventDefault();open();}
 });
 function render(items) {
   list.replaceChildren();
   items.forEach(item => {
     const button=document.createElement('button');button.type='button';button.className='command-result';
     const kind=document.createElement('small');kind.textContent=item.kind;
     const label=document.createElement('span');label.textContent=item.label;
     button.append(kind,label);button.title=item.description||item.label;
     button.onclick=() => {
       if(item.name) {
         if(typeof openChat!=='function') {status.textContent='Chat is unavailable. Reload to retry.';return;}
         close();openChat(item.label,'/'+item.name+' ');
       } else {close();location.assign(item.href);}
     };
     list.appendChild(button);
   });
 }
 async function search() {
   const version=++generation;controller?.abort();clearTimeout(timer);
   const query=input.value.trim(), words=query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
   const local=commands.filter(c => words.every(w =>
     [c.label,c.name,c.search,c.description].join(' ').toLocaleLowerCase().includes(w))).slice(0,24);
   render(local);status.textContent=query.length<2?'Pages and skills · type 2 characters to search tasks and notes.':'Searching tasks and notes…';
   if(query.length<2) return;
   timer=setTimeout(async () => {
     const requestController=new AbortController();controller=requestController;
     const abortTimer=setTimeout(()=>requestController.abort(),10000);
     try {
       const response=await fetch('/files/search?q='+encodeURIComponent(query),{signal:requestController.signal,cache:'no-store'});
       if(!response.ok) throw Error('HTTP '+response.status);
       const data=await response.json();if(!Array.isArray(data.items)) throw Error('Invalid search response');
       if(version!==generation||!dialog.open) return;
       const found=data.items.filter(x=>typeof x.href==='string'&&x.href.startsWith('/files?p='))
         .map(x=>({label:x.title,href:x.href,kind:x.kind==='task'?'Task':'Note'}));
       render([...local,...found]);status.textContent=(local.length+found.length)+' results';
     } catch(error) {
       if(version===generation&&dialog.open) status.textContent='Task/note search unavailable. Pages and skills remain available; edit the query to retry.';
     } finally {clearTimeout(abortTimer);}
   },200);
 }
 input.addEventListener('input',search);
 dialog.addEventListener('keydown',e => {
   // Search inputs consume Escape to clear themselves before dialog cancellation.
   if(e.key==='Escape') {e.preventDefault();e.stopPropagation();close();return;}
   const buttons=[...list.querySelectorAll('button')], current=buttons.indexOf(document.activeElement);
   if(e.key==='ArrowDown'||e.key==='ArrowUp') {
     e.preventDefault();
     if(!buttons.length) return;
     if(e.key==='ArrowUp'&&current<=0) input.focus();
     else buttons[Math.min(buttons.length-1,e.key==='ArrowDown'?current+1:current-1)].focus();
   } else if(e.key==='Enter'&&e.target===input) {e.preventDefault();buttons[0]?.click();}
 });
})();
</script>'''
