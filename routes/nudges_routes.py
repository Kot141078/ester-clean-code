# -*- coding: utf-8 -*-
"""
routes/nudges_routes.py - nudges s optsionalnoy stilizatsiey teksta, retrayami i vsem, chto my dobavili ranee.

MOSTY:
- (Yavnyy) Esli NUDGES_USE_STYLED=1 → otpravka cherez messaging.styled_broadcast.send_styled_broadcast().
- (Skrytyy #1) Pri NUDGES_USE_STYLED=0 - prezhniy put messaging.broadcast.send_broadcast() (polnaya obratnaya sovmestimost).
- (Skrytyy #2) Sokhranyaem avtogashenie po Outcome, eksport CSV, eskalatsionnye mappingi, alerty, retrai, «umnuyu tishinu».

ZEMNOY ABZATs:
Kogda nuzhno - zvuchim «po-chelovecheski». Kogda ne nuzhno - rabotaem kak ranshe. V oboikh sluchayakh - akkuratno i bez shuma.

# c=a+b
"""
from __future__ import annotations

import html, time, os, io
from typing import Any, Dict, List, Tuple
from fastapi import APIRouter, FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse

from nudges import store
from nudges.engine import plan as plan_nudges
from nudges.pending_csv import export_pending_csv
from nudges.csv import export_log_csv
from nudges.retry import analyze_and_requeue

# dva otpravschika - vyberem v rantayme po ENV
_USE_STYLED = (os.getenv("NUDGES_USE_STYLED","0") == "1")
if _USE_STYLED:
    from messaging.styled_broadcast import send_styled_broadcast as _send
else:
    from messaging.broadcast import send_broadcast as _send

from messaging.optin_store import set_silence_until
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/nudges/event")
async def nudges_event(payload: Dict[str, Any]):
    evt_type = payload.get("event_type")
    entity_id = payload.get("entity_id")
    ts = float(payload.get("ts") or time.time())
    if not evt_type or not entity_id:
        return JSONResponse({"ok": False, "error": "event_type and entity_id required"}, status_code=400)

    if evt_type == "OutcomeReported":
        store.skip_pending_by_entity(entity_id, reason="outcome")
        ev_id = store.add_event(evt_type, entity_id, ts, payload.get("payload") or {})
        return JSONResponse({"ok": True, "event_id": ev_id, "enqueued": 0})

    ev_id = store.add_event(evt_type, entity_id, ts, payload.get("payload") or {})
    ev = store.read_event(ev_id)
    plans = plan_nudges(ev)
    nmax = int(os.getenv("NUDGES_MAX_PER_EVENT","5") or "5")
    n = 0
    for p in plans[:nmax]:
        n += 1 if store.enqueue(ev_id, p["due_ts"], p["key"], p["kind"], p["intent"]) else 0
    return JSONResponse({"ok": True, "event_id": ev_id, "enqueued": n})

@router.post("/nudges/flush")
async def nudges_flush():
    flush_start = time.time()
    pending = store.list_pending(limit=500, due_only=True)
    buckets: Dict[Tuple[str,str], List[Tuple[int,str,int]]] = {}
    for pid, ev_id, cts, due, key, kind, intent, status in pending:
        buckets.setdefault((kind,intent), []).append((pid,key,ev_id))

    escalation_keys = set(store.list_escalation_keys())
    post_silence_min = int(os.getenv("NUDGES_POST_ESC_SILENCE_MIN","15") or "15")
    sent_total = skipped_total = 0

    for (kind, intent), items in buckets.items():
        keys = [k for _,k,_ in items]
        # otpravka (styled ili obychnaya)
        res = _send(keys, intent, adapt_kind=kind)  # signatura sovmestima
        sent_total += int(res.get("sent",0)); skipped_total += int(res.get("skipped",0))

        for pid,key,ev_id in items:
            store.mark(pid, "sent", "")
            status = "ok" if os.getenv("DEV_DRYRUN","0") != "1" else "ok:dryrun"
            store.log_send(key, kind, intent, status=status, http_status=200, event_id=ev_id)

        if kind == "lawyer" and any(k in escalation_keys for k in keys) and post_silence_min > 0:
            now = time.time()
            silence_until = now + post_silence_min*60
            for k in keys:
                if k in escalation_keys: continue
                try: set_silence_until(k, silence_until)
                except Exception: pass

    requeued = analyze_and_requeue(flush_start)
    return JSONResponse({"ok": True, "sent": sent_total, "skipped": skipped_total, "buckets": len(buckets), "retry_requeued": requeued})

@router.get("/nudges/alerts")
async def nudges_alerts():
    m = store.board_metrics()
    limit = int(os.getenv("NUDGES_OVERDUE_ALERT","20") or "20")
    overheated = m.get("overdue_due",0) >= limit
    return JSONResponse({"ok": True, "overdue_due": m.get("overdue_due",0), "limit": limit, "overheated": overheated, "ts": m.get("ts")})

@router.get("/admin/nudges/pending.csv")
async def admin_export_pending():
    data = export_pending_csv()
    return StreamingResponse(io.BytesIO(data), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=pending.csv"})

@router.get("/admin/nudges/log.csv")
async def admin_export_log():
    data = export_log_csv()
    return StreamingResponse(io.BytesIO(data), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=nudges_log.csv"})

@router.post("/admin/nudges/escalate_map")
async def admin_escalate_map(tag: str = Form(...), contact_key: str = Form(...)):
    store.map_escalation(tag.strip(), contact_key.strip())
    return RedirectResponse(url="/admin/nudges", status_code=303)

@router.post("/admin/nudges/escalate_unmap")
async def admin_escalate_unmap(tag: str = Form(...)):
    with store._conn() as c:
        c.execute("DELETE FROM nudges_escalations WHERE tag=?", (tag.strip(),))
    return RedirectResponse(url="/admin/nudges", status_code=303)

_HTML_ESC = """
<section>
<h3>Eskalatsionnye tegi</h3>
<form method="post" action="/admin/nudges/escalate_map">
  <div class="row">
    <label>tag: <input name="tag" required placeholder="manager"></label>
    <label>contact_key: <input name="contact_key" required placeholder="telegram:99"></label>
    <button type="submit">Save</button>
  </div>
</form>
<table><thead><tr><th>tag</th><th>contact_key</th><th>updated_ts</th><th>action</th></tr></thead>
<tbody>
{rows_esc}
</tbody></table>
<div class="row" style="margin-top:8px">
  <a href="/admin/nudges/pending.csv">Eksport pending.csv</a>
  <a href="/admin/nudges/log.csv" style="margin-left:12px">Eksport nudges_log.csv</a>
  <a href="/nudges/alerts" style="margin-left:12px">Alerty</a>
  <span style="margin-left:12px">Stil: <b>{styled}</b></span>
</div>
</section>
"""

from fastapi.responses import HTMLResponse

@router.get("/admin/nudges.ext", response_class=HTMLResponse)
async def admin_nudges_ext():
    rows = []
    for tag, key, uts in store.list_escalations():
        rows.append(f"<tr><td>{html.escape(tag)}</td><td>{html.escape(key)}</td><td>{int(uts)}</td>"
                    f"<td><form method='post' action='/admin/nudges/escalate_unmap'><input type='hidden' name='tag' value='{html.escape(tag)}'><button type='submit'>Udalit</button></form></td></tr>")
    return HTMLResponse(_HTML_ESC.format(rows_esc="\n".join(rows), styled=("ON" if _USE_STYLED else "OFF")))

def mount_nudges(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app
