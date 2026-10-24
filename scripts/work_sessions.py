"""Linked work: existing task -> timed Calendar reservation -> original result -> Files review.

Only explicit UI actions call Calendar. Receipts reuse chat_actions.jsonl; results reuse
the review-inbox ledger. No task/frontmatter, AI consent or archived writing is changed.
"""
import hashlib
import json
import time
from datetime import datetime, timedelta

import calendar_utils
import dashboard_chat_actions as actions
import dashboard_icons
import shuki_notifications
from shuki_core import vault as core_vault


def records():
    return {k: v for k, v in actions._records().items() if v.get("kind") == "work_session"}


def append(record):
    actions.LOG.parent.mkdir(parents=True, exist_ok=True)
    with actions.LOG.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def event_id(key):
    return "shukitask" + hashlib.sha256(key.encode()).hexdigest()


def checked_time(payload):
    value = actions._text(payload, "start", 16, True)
    start = datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=core_vault.JST)
    duration = payload.get("duration")
    if type(duration) is not int or not 5 <= duration <= 240:
        raise ValueError("Choose a duration from 5 to 240 minutes")
    end = start + timedelta(minutes=duration)
    if end.date() != start.date() or start <= datetime.now(core_vault.JST):
        raise ValueError("Choose a future session ending on the same day (Japan time)")
    return start, end


def availability(start, end, key, service):
    busy = calendar_utils.get_decision_availability(start, end, service=service)
    # All-day reminders do not reserve working time, matching the existing card behavior.
    return [e for e in busy if e.get("id") != event_id(key)
            and e.get("status") != "cancelled" and e.get("transparency") != "transparent"
            and "dateTime" in e.get("start", {})
            and not any(a.get("self") and a.get("responseStatus") == "declined"
                        for a in e.get("attendees", []))]


def reserve(record, service):
    """Stable external identity reconciles a lost insert response before any retry."""
    from googleapiclient.errors import HttpError

    identity = event_id(record["key"])
    start = datetime.fromisoformat(record["start"])
    end = datetime.fromisoformat(record["end"])

    def matches(event):
        return (event.get("id") == identity and event.get("status") != "cancelled"
                and event.get("summary") == record["title"]
                and event.get("start", {}).get("dateTime")
                and event.get("end", {}).get("dateTime")
                and datetime.fromisoformat(event["start"]["dateTime"]) == start
                and datetime.fromisoformat(event["end"]["dateTime"]) == end
                and event.get("extendedProperties", {}).get("private", {}).get("shuki_work") == record["key"])

    try:
        found = service.events().get(calendarId="primary", eventId=identity).execute()
    except HttpError as error:
        if error.resp.status != 404:
            raise
    else:
        if not matches(found):
            raise ValueError("The existing reservation changed or was cancelled; review it in Calendar")
        return identity
    if start <= datetime.now(core_vault.JST):
        raise ValueError("The selected time has passed; review the original reservation in Calendar")
    if availability(start, end, record["key"], service):
        raise ValueError("This time is now busy. Choose another time; no reservation was created")
    body = {"id": identity, "summary": record["title"],
            "start": {"dateTime": record["start"], "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": record["end"], "timeZone": "Asia/Tokyo"},
            "extendedProperties": {"private": {"shuki_work": record["key"]}}}
    try:
        service.events().insert(calendarId="primary", body=body, sendUpdates="none").execute()
    except HttpError as error:
        if error.resp.status != 409:
            raise
    confirmed = service.events().get(calendarId="primary", eventId=identity).execute()
    if not matches(confirmed):
        raise ValueError("Reservation could not be verified; keep this request and check Calendar")
    return identity


def get(task, read_source, review_inbox):
    out = []
    for record in records().values():
        if record.get("path") != task["path"]:
            continue
        # References are checked again on every read, even for previously accepted records.
        item = dict(record)
        item["contexts"] = []
        for path in record.get("context_paths", []):
            try:
                item["contexts"].append(read_source(path))
            except ValueError:
                pass  # Do not leak titles or paths of newly excluded sources.
        item.pop("context_paths", None)
        filename = "work_" + hashlib.sha256(record["key"].encode()).hexdigest() + ".json"
        item["review_ready"] = ((review_inbox / filename).exists()
                                or (review_inbox / "processed" / filename).exists())
        out.append(item)
    return {"task": task, "sessions": sorted(out, key=lambda r: r["start"], reverse=True)}


def handle(payload, read_source, review_inbox):
    """HTTP adapter injects the same guarded source resolver used for reads and writes."""
    if not isinstance(payload, dict):
        return 400, {"error": "Expected an object"}
    try:
        task = read_source(payload.get("path"), task=True)
        op = payload.get("op")
        if op == "get":
            return 200, get(task, read_source, review_inbox)
        key = actions._text(payload, "key", 79, True)
        if not key.startswith("work:") or not actions.KEY_RE.fullmatch(key):
            raise ValueError("Invalid reservation identity")
        with actions._LOCK:
            collision = actions._records().get(key)
            if collision and collision.get("kind") != "work_session":
                raise ValueError("Action identity is already in use")
            previous = records().get(key)
            if previous and previous.get("path") != task["path"]:
                raise ValueError("Reservation does not belong to this task")
            if op == "result":
                if not previous or previous.get("status") != "confirmed":
                    raise ValueError("A confirmed reservation is required")
                text = payload.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > 6000:
                    raise ValueError("Write a result of up to 6000 characters")
                if previous.get("result") and previous["result"]["text"] != text:
                    raise ValueError("This result is already saved; the original cannot be overwritten")
                result = previous.get("result") or {"text": text, "at": time.time(), "processing": "record"}
                record = dict(previous, result=result)
                append(record)  # Preserve original writing even if review delivery fails.
                # Explicit Save for review creates one ordinary Files-review ledger, no AI dispatch.
                filename = "work_" + hashlib.sha256(key.encode()).hexdigest() + ".json"
                ledger = review_inbox / filename
                processed = review_inbox / "processed" / filename
                if not ledger.exists() and not processed.exists():
                    shuki_notifications.atomic_json(ledger, {
                        "source": "work_session", "kind": "Work session result", "icon": "check",
                        "title": task["title"], "task_path": task["path"], "work_key": key,
                        "summary": "A work-session result is ready. Open the session to review the original writing. Task status is unchanged.",
                        "processing": "record", "ts": result["at"], "notification": "important_result"})
                return 200, {"ok": True, "session": next(r for r in get(task, read_source, review_inbox)["sessions"] if r["key"] == key),
                             "review": "/files?work_review=1"}
            if op not in ("check", "reserve"):
                raise ValueError("Unknown work-session action")
            if previous:
                if previous.get("status") == "confirmed":
                    return 200, {"ok": True, "already": True, "session": next(r for r in get(task, read_source, review_inbox)["sessions"] if r["key"] == key)}
                record = previous  # Retry only the exact persisted intent; never substitute new fields.
                for path in record.get("context_paths", []):
                    read_source(path)
                if record["revision"] != task["revision"]:
                    raise ValueError("The task changed. Check Calendar before making a new reservation")
            else:
                if task["status"] not in ("todo", "in-progress", "on-hold"):
                    raise ValueError("Only an unfinished task can be scheduled")
                if payload.get("revision") != task["revision"]:
                    raise ValueError("The task changed. Reopen the plan before continuing")
                criterion = actions._text(payload, "criterion", 500, True)
                paths = payload.get("context_paths", [])
                if not isinstance(paths, list) or len(paths) > 3 or any(not isinstance(p, str) for p in paths):
                    raise ValueError("Select up to three context notes")
                contexts = [read_source(p) for p in dict.fromkeys(paths)]
                start, end = checked_time(payload)
                record = {"kind": "work_session", "key": key, "path": task["path"],
                          "title": task["title"], "revision": task["revision"],
                          "criterion": criterion, "due": task.get("due", ""),
                          "start": start.isoformat(), "end": end.isoformat(),
                          "context_paths": [c["path"] for c in contexts], "status": "pending",
                          "at": datetime.now(core_vault.JST).isoformat(timespec="seconds")}
            service = calendar_utils.get_calendar_service()
            start, end = datetime.fromisoformat(record["start"]), datetime.fromisoformat(record["end"])
            if op == "check":
                hits = availability(start, end, key, service)
                return 200, {"conflicts": [{"title": e.get("summary") or "Busy"} for e in hits]}
            if not previous:
                append(record)  # Intent survives a crash or a lost external response.
            identity = reserve(record, service)
            record = dict(record, id=identity, status="confirmed")
            append(record)
            return 200, {"ok": True, "session": next(r for r in get(task, read_source, review_inbox)["sessions"] if r["key"] == key)}
    except ValueError as error:
        return 400, {"error": str(error)}
    except calendar_utils.CalendarNotConnected:
        return 503, {"error": "Google Calendar is not connected. The task is unchanged."}
    except Exception as error:
        return 502, {"error": "The operation was not confirmed. Keep this request and retry only after checking the connection.",
                     "detail": type(error).__name__}


JS = r'''(() => {
'use strict';
if(window.shukiWorkOpen)return;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const href=p=>'/files?p='+encodeURIComponent(p);
const icons=__WORK_ICONS__;
const style=document.createElement('style');
style.textContent=`
.ws-open,.ws-open body{overflow:hidden}
.ws-open #detail-panel,.ws-open #detail-overlay{opacity:0;pointer-events:none}
.ws-dialog{box-sizing:border-box;position:fixed;inset:0;margin:auto;width:min(600px,calc(100% - 48px));height:fit-content;max-width:none;max-height:min(760px,calc(100dvh - 48px));overflow:hidden;padding:0;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg);font:14px/1.5 var(--font-ui,system-ui);box-shadow:0 16px 48px color-mix(in srgb,var(--fg) 16%,transparent)}
.ws-dialog[open]{display:flex;flex-direction:column}.ws-dialog::backdrop{background:color-mix(in srgb,var(--bg) 72%,transparent)}
.ws-dialog *{box-sizing:border-box;min-width:0}.ws-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px;border-bottom:1px solid var(--line);flex-shrink:0}
.ws-dialog h2{font-size:1rem;line-height:1.4;margin:0;font-weight:650}.ws-dialog h3{font-size:1rem;line-height:1.5;margin:0;font-weight:650}
#ws-body{overflow-y:auto;overscroll-behavior:contain;padding:16px;min-height:0}.ws-dialog p{margin:0 0 8px}.ws-task{margin-bottom:16px;overflow-wrap:anywhere}.ws-task .ws-note{margin:4px 0 0}
.ws-dialog input,.ws-dialog textarea,.ws-dialog select,.ws-dialog button{font:inherit;max-width:100%;border:1px solid var(--control-line,var(--line));border-radius:8px;background:var(--surface-control,var(--card));color:var(--fg)}
.ws-dialog input,.ws-dialog textarea{width:100%;min-height:40px;padding:8px 10px}.ws-dialog input{height:40px}.ws-dialog textarea{min-height:88px;resize:vertical}.ws-dialog label{display:block;margin:0 0 6px;font-size:.8125rem;font-weight:550}
.ws-field{margin-bottom:16px}.ws-row{display:grid;grid-template-columns:minmax(0,1fr)96px;gap:12px}.ws-row .ws-field{margin-bottom:16px}
.ws-dialog button{position:relative;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:32px;padding:4px 10px;cursor:pointer;background:var(--card);border-color:var(--line);line-height:1.4}
.ws-dialog button::before,.ws-dialog .ws-link::before{content:'';position:absolute;inset:-7px -1px}.ws-dialog button:hover:not(:disabled),.ws-dialog .ws-link:hover{background:var(--surface-control,var(--bg));border-color:var(--control-line,var(--muted));transform:none}
.ws-dialog button:disabled{opacity:.55;cursor:wait}.ws-dialog .ws-close{width:28px;height:28px;min-height:28px;padding:0;border-color:transparent;background:none;flex-shrink:0}.ws-dialog .ws-close::before{inset:-9px}
.ws-dialog svg{width:16px;height:16px;flex-shrink:0}.ws-actions{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:6px 0}
.ws-footer{display:flex;align-items:center;flex-wrap:wrap;justify-content:flex-end;gap:12px;padding:12px 16px 16px;border-top:1px solid var(--line);background:var(--card);flex-shrink:0}.ws-footer:empty{display:none}.ws-dialog .ws-footer button{min-height:40px;padding:8px 12px}.ws-dialog .ws-footer button::before{inset:-3px -1px}
.ws-dialog .ws-primary{background:var(--accent);color:var(--ws-button-ink);border-color:var(--accent);font-weight:600}.ws-dialog .ws-primary:hover:not(:disabled){background:var(--accent);border-color:var(--accent);filter:brightness(.96)}
.ws-note{color:var(--muted);font-size:.8125rem}.ws-empty{padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--bg)}.ws-empty p:last-child{margin:0}
.ws-session{border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:12px;overflow-wrap:anywhere}.ws-session h3{font-size:.875rem;margin-bottom:4px}.ws-session .ws-actions{margin:12px 0 0}
.ws-dialog .ws-link{position:relative;display:flex;align-items:center;gap:8px;min-height:32px;padding:4px 8px;border:1px solid var(--line);border-radius:8px;color:var(--fg);text-decoration:none;font-size:.8125rem;line-height:1.5;overflow-wrap:anywhere;background:var(--card)}.ws-links{display:grid;gap:12px;padding:6px 0}
.ws-dialog details{border-top:1px solid var(--line);margin-top:12px;padding-top:4px}.ws-dialog summary{display:flex;align-items:center;gap:8px;min-height:44px;list-style:none;cursor:pointer;font-size:.8125rem;font-weight:550}.ws-dialog summary::-webkit-details-marker{display:none}.ws-dialog summary svg{color:var(--muted)}.ws-dialog details[open]>summary svg{transform:rotate(180deg)}
.ws-dialog :focus-visible{outline:2px solid var(--accent);outline-offset:3px}.ws-dialog h2:focus{outline:none}
.ws-review{padding:12px;border:1px solid var(--accent);border-radius:8px;background:var(--surface-highlight,var(--bg))}.ws-review h3{margin-bottom:12px}.ws-review p{white-space:pre-wrap}.ws-result{white-space:pre-wrap;overflow-wrap:anywhere}
.ws-alert{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8125rem;color:var(--muted);flex-shrink:0}.ws-dialog #ws-status{padding:0 16px 12px;margin:0;max-height:84px;overflow:auto}.ws-dialog #ws-status:empty{display:none}.ws-dialog[data-error=true] #ws-status{color:var(--danger)}
.ws-sources button{display:flex;width:100%;min-height:44px;text-align:left;justify-content:flex-start;margin:8px 0}.ws-selected{font-size:.8125rem;margin:8px 0}
@media(max-width:700px){.ws-dialog{inset:auto 0 0;margin:0;width:100%;max-height:calc(100dvh - 16px);border-radius:12px 12px 0 0;border-bottom:0}.ws-header{padding:12px 16px}#ws-body{padding:12px}.ws-dialog #ws-status{padding:0 12px 12px}.ws-footer{padding:12px;padding-bottom:max(12px,env(safe-area-inset-bottom))}.ws-footer .ws-primary{flex:1}.ws-task{margin-bottom:12px}}
@media(max-width:360px){.ws-row{grid-template-columns:minmax(0,1fr)}.ws-row .ws-field:last-child{max-width:120px}}
@media(prefers-reduced-motion:reduce){.ws-dialog *{animation:none!important;transition:none!important}}
`;
document.head.append(style);
const dialog=document.createElement('dialog');dialog.className='ws-dialog';dialog.setAttribute('aria-labelledby','ws-title');
dialog.innerHTML='<header class="ws-header"><h2 id="ws-title" tabindex="-1">Work session</h2><button type="button" class="ws-close" aria-label="Close work session">'+icons.cross+'</button></header><div id="ws-body"></div><p id="ws-status" class="ws-alert" role="status" aria-live="polite"></p><footer class="ws-footer" id="ws-footer"></footer>';
document.body.append(dialog);
const body=dialog.querySelector('#ws-body'),status=dialog.querySelector('#ws-status'),footer=dialog.querySelector('#ws-footer');
function render(content,actions='',title='Work session'){body.innerHTML=content;footer.innerHTML=actions;dialog.querySelector('#ws-title').textContent=title;body.scrollTop=0;dialog.querySelector('#ws-title').focus({preventScroll:true});}
const link=(url,label,icon='doc')=>'<a class="ws-link" href="'+esc(url)+'">'+icons[icon]+'<span>'+esc(label)+'</span></a>';
const summary=label=>'<summary>'+icons['chevron-down']+esc(label)+'</summary>';
const taskSummary=()=>'<div class="ws-task"><h3>'+esc(data.task.title)+'</h3><p class="ws-note">Deadline: '+esc(data.task.due||'not set')+'</p></div>';
function buttonInk(){const probe=document.createElement('span');probe.style.color='var(--accent)';dialog.append(probe);const nums=getComputedStyle(probe).color.match(/[\d.]+/g).slice(0,3).map(Number);probe.remove();const l=nums.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});const y=l[0]*.2126+l[1]*.7152+l[2]*.0722;dialog.style.setProperty('--ws-button-ink',y>.179?'black':'white');}

let data,path,key,draft,contexts=[],opener,busy=false,serial=0;
const button=(id,text,primary=false)=>'<button type="button" data-ws="'+id+'"'+(primary?' class="ws-primary"':'')+'>'+text+'</button>';
async function api(payload){const r=await fetch('/work-sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,...payload})});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function setBusy(value){busy=value;dialog.querySelectorAll('button,input,textarea,select').forEach(e=>e.disabled=value);}
async function run(fn){if(busy)return;dialog.dataset.error='false';status.textContent='Working…';setBusy(true);try{await fn();}catch(e){dialog.dataset.error='true';status.textContent=e.message;}finally{setBusy(false);}}
function dates(s){return new Date(s.start).toLocaleString('en-GB',{timeZone:'Asia/Tokyo'})+' – '+new Date(s.end).toLocaleTimeString('en-GB',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit'})+' JST';}
function listing(){
 status.textContent='';
 const session=s=>'<section class="ws-session"><h3>'+esc(dates(s))+'</h3><p class="ws-note">'+esc(s.status==='confirmed'?'Reservation confirmed':'Reservation not confirmed. Check Calendar before retrying.')+'</p><p><strong>Done means:</strong> '+esc(s.criterion)+'</p>'
 +(s.contexts?.length?'<details>'+summary('Supporting notes ('+s.contexts.length+')')+'<div class="ws-links">'+s.contexts.map(c=>link(href(c.path),c.title)).join('')+'</div></details>':'')
 +(s.result?'<p class="ws-result">'+esc(s.result.text)+'</p><p class="ws-note">Original result saved. Task status is unchanged.</p>'+(s.review_ready?'<div class="ws-links">'+link('/files?work_review=1','Review results in Files','inbox')+'</div>':'<div class="ws-actions">'+button('deliver:'+s.key,'Retry sending saved result to review')+'</div>'):'<div class="ws-actions">'+(s.status==='confirmed'?button('result:'+s.key,'Record a result'):button('retry:'+s.key,'Retry this exact reservation'))+'</div>')+'</section>';
 render(taskSummary()+(data.sessions.length?session(data.sessions[0])+(data.sessions.length>1?'<details>'+summary('Earlier sessions ('+(data.sessions.length-1)+')')+data.sessions.slice(1).map(session).join('')+'</details>':''):'<div class="ws-empty"><p><strong>Make room for this task</strong></p><p class="ws-note">Choose a time, keep useful notes close, and record what happened.</p></div>')
 +'<details>'+summary('Task details')+'<div class="ws-links">'+link(href(path),'Read the task in Files')+link('/board?work_task='+encodeURIComponent(path),'Task status controls','check')+'</div></details>',
 ['todo','in-progress','on-hold'].includes(data.task.status)?button('plan','Plan a work session',true):'');
}
function plan(reset=true){
 if(reset){key='work:'+Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');contexts=[];draft=null;}
 const now=new Date(Date.now()+86400000),jst=new Date(now.getTime()+9*3600000).toISOString().slice(0,10);
 render(taskSummary()+'<div class="ws-row"><div class="ws-field"><label for="ws-start">Work date and start · Japan time</label><input id="ws-start" type="datetime-local" value="'+esc(draft?.start||jst+'T18:30')+'"></div>'
 +'<div class="ws-field"><label for="ws-duration">Minutes</label><input id="ws-duration" type="number" min="5" max="240" value="'+esc(draft?.duration||30)+'"></div></div>'
 +'<div class="ws-field"><label for="ws-criterion">Session completion criterion</label><textarea id="ws-criterion" maxlength="500">'+esc(draft?.criterion??data.task.completion_criteria??'')+'</textarea></div>'
 +'<details>'+summary('Add supporting notes (optional, up to three)')+'<label for="ws-search">Find a note</label><input id="ws-search" type="search"><div class="ws-actions">'+button('search','Search')+'</div><div class="ws-sources" id="ws-search-results"></div><div class="ws-selected" id="ws-contexts">'+esc(contexts.map(c=>c.title).join(', '))+'</div><div class="ws-actions">'+button('clear-context','Clear selected notes')+'</div></details>',
 button('list','Back')+button('check','Review time',true),'Plan a work session');
 status.textContent='Only the title and time go to Calendar. Notes stay in SHUKI.';
}
function review(){
 render('<div class="ws-review"><h3>Review the reservation</h3><p><strong>'+esc(data.task.title)+'</strong></p><p>'+esc(draft.start.replace('T',' '))+' JST · '+draft.duration+' minutes</p><p>Task deadline: '+esc(data.task.due||'not set')+(data.task.due&&draft.start.slice(0,10)>data.task.due?' · this session is after the deadline. The deadline stays unchanged.':'')+'</p><p><strong>Done means:</strong> '+esc(draft.criterion)+'</p>'
 +(contexts.length?'<details>'+summary('Supporting notes ('+contexts.length+')')+'<div class="ws-links">'+contexts.map(c=>link(href(c.path),c.title)).join('')+'</div></details>':'')+'</div>',
 button('edit-plan','Edit plan')+button('reserve','Reserve this session',true),'Confirm work time');
 status.textContent='Availability checked. Review before reserving.';
}
window.shukiWorkOpen=async(taskPath)=>{
 if(busy)return;opener=document.activeElement;path=taskPath;const token=++serial;render('<p>Loading selected task…</p>');status.textContent='';if(!dialog.open){dialog.showModal();document.documentElement.classList.add('ws-open');}buttonInk();
 await run(async()=>{try{const d=await api({op:'get'});if(token!==serial)return;data=d;listing();}
 catch(error){if(token===serial){data=null;render('<p>This task could not be opened for a work session.</p>',button('close','Back'),'Work session unavailable');}throw error;}});
};
function closeWork(){document.documentElement.classList.remove('ws-open');dialog.close();}
dialog.querySelector('.ws-close').onclick=closeWork;
// Native Escape restores focus before the close event, so reveal the source first.
dialog.addEventListener('cancel',()=>document.documentElement.classList.remove('ws-open'));
dialog.addEventListener('close',()=>{
 serial++;document.documentElement.classList.remove('ws-open');const target=opener;
 // Let the native modal release focus and reveal its source panel before restoring it.
 requestAnimationFrame(()=>{if(!dialog.open&&target?.isConnected&&!target.disabled)target.focus({preventScroll:true});});
});
dialog.addEventListener('click',e=>{if(e.target===dialog&&!busy){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeWork();}});
dialog.addEventListener('click',e=>{
 const b=e.target.closest('[data-ws]');if(!b||busy)return;
 const action=b.dataset.ws;
 if(action==='close'){closeWork();return;}
 if(action==='edit-plan'){plan(false);return;}
 if(action==='clear-context'){contexts=[];body.querySelector('#ws-contexts').textContent='';return;}
 if(action.startsWith('deliver:')){run(async()=>{const s=data.sessions.find(s=>s.key===action.slice(8));await api({op:'result',key:s.key,text:s.result.text});data=await api({op:'get'});listing();status.textContent='Saved original delivered to Files review.';});return;}
 if(action==='list'){listing();return;}
 if(action==='plan'){plan();return;}
 if(action==='search'){run(async()=>{const q=body.querySelector('#ws-search').value.trim();if(!q)throw Error('Enter a note title.');const r=await fetch('/files/search?q='+encodeURIComponent(q));if(!r.ok)throw Error('Could not search notes.');const d=await r.json();const dest=body.querySelector('#ws-search-results');dest.innerHTML='';for(const item of d.items||[]){if(!item.path&&!item.href)continue;let p=item.path;if(!p){const u=new URL(item.href,location.origin);if(u.origin!==location.origin||u.pathname!=='/files')continue;p=u.searchParams.get('p');}if(!p||contexts.some(c=>c.path===p))continue;const pick=document.createElement('button');pick.type='button';pick.textContent=item.title;pick.onclick=()=>{if(contexts.some(c=>c.path===p))return;if(contexts.length>=3){status.textContent='Select at most three notes.';return;}contexts.push({path:p,title:item.title});body.querySelector('#ws-contexts').textContent='Selected: '+contexts.map(c=>c.title).join(', ');pick.disabled=true;};dest.append(pick);}status.textContent='Choose a note; opening this search never sends it to AI.';});return;}
 if(action==='check'){run(async()=>{draft={op:'check',key,revision:data.task.revision,start:body.querySelector('#ws-start').value,duration:Number(body.querySelector('#ws-duration').value),criterion:body.querySelector('#ws-criterion').value.trim(),context_paths:contexts.map(c=>c.path)};const d=await api(draft);if(d.conflicts?.length)throw Error('This time is busy: '+d.conflicts.map(c=>c.title).join(', '));review();});return;}
 if(action==='reserve'||action.startsWith('retry:')){run(async()=>{const payload=action==='reserve'?{...draft,op:'reserve'}:{op:'reserve',key:action.slice(6)};await api(payload);data=await api({op:'get'});listing();status.textContent='Reservation confirmed. The task is unchanged.';});return;}
 if(action.startsWith('result:')){key=action.slice(7);render(taskSummary()+'<div class="ws-field"><label for="ws-result">What actually happened?</label><textarea id="ws-result" maxlength="6000"></textarea></div><p class="ws-note">Your original writing stays as written. No AI processing. Saving does not complete the task.</p>',button('list','Cancel')+button('save-result','Save result for review',true),'Record a result');status.textContent='';return;}
 if(action==='save-result'){run(async()=>{const text=body.querySelector('#ws-result').value;if(!text.trim())throw Error('Write a result before saving.');await api({op:'result',key,text});data=await api({op:'get'});listing();status.textContent='Result saved for review in Files. Use the existing task status control when its completion criterion is met.';});}
});
document.addEventListener('click',e=>{const b=e.target.closest('[data-work-task]');if(b){e.preventDefault();window.shukiWorkOpen(b.dataset.workTask);}});
const initial=new URLSearchParams(location.search).get('work');if(initial)window.shukiWorkOpen(initial);
})();'''.replace('__WORK_ICONS__', json.dumps({name: dashboard_icons.ui_icon_svg(name, 16)
                                          for name in ('cross', 'chevron-down', 'doc', 'check', 'inbox')}))
