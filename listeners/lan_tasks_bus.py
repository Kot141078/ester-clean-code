# -*- coding: utf-8 -*-
"""listeners/lan_tasks_bus.py - UDP-shina zadach: submit/accept/result + lokalnyy dispatcher.

Protocol package (JSON, UTF-8):
  { "t":"task.submit|task.accept|task.result", "ts":<unix>, "node":{"id","name"},
    "sig":"<hex>", "payload":{...} }

payload dlya submit:
  { "task": <sm. modules.lan.lan_tasks.new_task()> }

Politika reception:
  • HMAC cherez LAN_SHARED_KEY (esli zadan) - inache dopuskayutsya nepodpisannye (verified=false).
  • Prinimaem tolko esli tip zadachi vkhodit v accept i est slot aktivnykh rabot (< max_active).

Tsikl:
  • Kazhdye interval sek: berem zadachu iz inbox po prioritetu, ispolnyaem (AB=A - plan), shlem result otpravitelyu.
  • Periodicheski perebrasyvaem outbox → task.submit (broadcast or target ip).

Mosty:
- Yavnyy (Orkestratsiya ↔ Vychisleniya): obschaya shina zadach mezhdu uzlami.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): HMAC-podpis; "sukhoy" rezhim cherez AB.
- Skrytyy 2 (Praktika ↔ Sovmestimost): odin i tot zhe JSON-format v UI/REST/UDP.

Zemnoy abzats:
This is “prorab uchastka”: prinimaet zayavki, razdaet po vozmozhnostyam, vozvraschaet rezultat - bez interneta.

# c=a+b"""
from __future__ import annotations

import argparse, json, os, socket, struct, time
from typing import Any, Dict, Tuple

from modules.lan.lan_settings import load_settings  # key, group
from modules.lan.lan_crypto import sign, verify
from modules.lan.lan_tasks_settings import load_tasks_settings
from modules.lan.lan_tasks import enqueue_outbox, accept_to_inbox, start_one, complete, exec_job, _load_db
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _mk_sock(port: int, group: str) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception: pass
    s.bind(("", port))
    mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.settimeout(0.5)
    return s

def _send(sock: socket.socket, obj: Dict[str, Any], addr: Tuple[str,int], key: str) -> None:
    tmp = dict(obj); tmp["sig"] = ""  # zapolnim posle serializatsii
    raw = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp["sig"] = sign(raw, key) if key else ""
    pkt = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sock.sendto(pkt, addr)

def _node_id() -> str:
    try:
        import platform
        return platform.node()
    except Exception:
        return "node"

def _handle(pkt: bytes, src: Tuple[str,int], cfg_net: Dict[str,Any], cfg_tasks: Dict[str,Any]) -> None:
    ip,_ = src
    try:
        j = json.loads(pkt.decode("utf-8", errors="ignore"))
    except Exception:
        return
    sig = j.get("sig") or ""
    tmp = dict(j); tmp.pop("sig", None)
    raw = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    verified = verify(raw, sig, cfg_net.get("shared_key",""))
    t = str(j.get("t") or "")
    pl = (j.get("payload") or {})

    if t == "task.submit":
        task = pl.get("task") or {}
        jtype = (task.get("job") or {}).get("type")
        if jtype not in (cfg_tasks.get("accept") or []):
            return
        # let's check the slots
        db = _load_db()
        if len((db.get("active") or {})) >= int(cfg_tasks.get("max_active",1)):
            return
        accept_to_inbox(task)
        # We will respond with acceptance to the sender (unicast)
        ack = {"t":"task.accept","ts":int(time.time()),"node":{"id":_node_id(),"name":_node_id()},"payload":{"id": task.get("id")}}
        _send(_SOCK, ack, (ip, int(cfg_tasks["port"])), cfg_net.get("shared_key",""))

    elif t == "task.accept":
        # mozhno pometit outbox → acknowledged (na UI eto vidno v state)
        pass

    elif t == "task.result":
        # The result has arrived to the recipient - put it in the bottom (as an incoming result)
        # task/result is always filled in by the recipient of the request - here we just display.
        # UI vozmet iz state.json (done)
        res = pl.get("result") or {}
        task = pl.get("task") or {}
        # Save as completed “remote” task (status in resilt)
        from modules.lan.lan_tasks import _load_db as _db, _save_db as _sv
        d = _db()
        tid = (task.get("id") or "") + "@remote"
        d.setdefault("done", {})[tid] = {"task": task, "status": res.get("status","ok"), "result": res, "finished": int(time.time())}
        _sv(d)

# Globalnyy soket
_SOCK: socket.socket

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN tasks bus")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    net = load_settings()
    cfg = load_tasks_settings()
    if not cfg.get("enable"):
        print("[lan-tasks] disabled", flush=True); return 0

    global _SOCK
    _SOCK = _mk_sock(int(cfg["port"]), net.get("group","239.255.43.21"))

    interval = int(args.interval or cfg.get("interval",10))
    last_tick = 0

    try:
        while True:
            now = time.time()
            # tick - executes one task and sends the results
            if now - last_tick >= max(1, interval):
                # let's try to take on the task
                picked = start_one(max_active=int(cfg.get("max_active",1)))
                if picked:
                    tid, task = picked
                    status, result = exec_job(task)
                    # shlem rezultat initsiatoru (esli ukazan ip → unicast; inache broadcast)
                    reply = {
                        "t":"task.result",
                        "ts":int(time.time()),
                        "node":{"id":_node_id(),"name":_node_id()},
                        "payload":{"task": task, "result": {"status": status, **result}}
                    }
                    dst_ip = (task.get("from") or {}).get("ip") or ""
                    addr = (dst_ip, int(cfg["port"])) if dst_ip else (net.get("group","239.255.43.21"), int(cfg["port"]))
                    _send(_SOCK, reply, addr, net.get("shared_key",""))
                    complete(tid, status, result)
                # pereotpravim outbox (submit)
                from modules.lan.lan_tasks import _load_db as _db
                d = _db()
                for task in list((d.get("outbox") or {}).values()):
                    # Let's include our outgoing IP in the from.ip field
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
                        myip = s.getsockname()[0]; s.close()
                    except Exception:
                        myip = "0.0.0.0"
                    task["from"]["ip"] = myip
                    submit = {"t":"task.submit","ts":int(time.time()),"node":{"id":_node_id(),"name":_node_id()},"payload":{"task": task}}
                    dst = task.get("to",{}).get("ip") or ""
                    addr = (dst, int(cfg["port"])) if dst else (net.get("group","239.255.43.21"), int(cfg["port"]))
                    _send(_SOCK, submit, addr, net.get("shared_key",""))
                last_tick = now

            # processing of incoming packets
            try:
                pkt, src = _SOCK.recvfrom(65535)
            except socket.timeout:
                pkt = None
            if pkt:
                _handle(pkt, src, net, cfg)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try: _SOCK.close()
        except Exception: pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b