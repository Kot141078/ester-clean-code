# -*- coding: utf-8 -*-
"""listeners/lan_reply_listener.py - UDP-priemnik LAN-kvitantsiy (optsionalno).

Behavior:
  • Esli LAN_REPLY_UDP_ENABLE=1 — slushaem UDP port LAN_REPLY_UDP_PORT.
  • Pri poluchenii JSON: normalizuem, proveryaem podpis (esli sekret), kladem v inboks i pytaemsya primenit k ocheredi.

Mosty:
- Yavnyy (Set ↔ Podtverzhdenie): legkiy transport bez HTTP.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): logi o prieme/oshibkakh.
- Skrytyy 2 (Praktika ↔ Sovmestimost): UDP best-effort; oshibki ne fatalny, yadro ne trogaem.

Zemnoy abzats:
Eto “radiostantsiya tsekha”: dostatochno skazat “Gotovo, naryad takoy-to” - dispetcher uslyshit.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, socket, time
from modules.lan_reply.protocol import normalize, verify  # type: ignore
from modules.lan_reply.inbox import save_receipt, add_log  # type: ignore
from modules.hybrid.dispatcher_adapter import apply_receipt  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN-Reply UDP listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--port", type=int, default=int(os.getenv("LAN_REPLY_UDP_PORT","48128")))
    args = ap.parse_args(argv)

    secret = os.getenv("LAN_REPLY_SECRET") or None
    if os.getenv("LAN_REPLY_UDP_ENABLE","0") != "1":
        print(json.dumps({"ts": int(time.time()), "mod":"lan_reply_udp", "status":"disabled"}), flush=True)
        return 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(args.port)))
    sock.settimeout(1.0)
    print(json.dumps({"ts": int(time.time()), "mod":"lan_reply_udp", "status":"listening", "port": args.port}), flush=True)

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                if not args.loop: break
                continue
            try:
                obj = json.loads(data.decode("utf-8"))
                obj = normalize(obj)
                if not verify(obj, secret, None):
                    add_log("udp_bad_sig", {"from": addr[0], "obj": obj})
                    continue
                save_receipt(obj)
                res = apply_receipt(obj)
                add_log("udp_applied", {"from": addr[0], "obj": obj, "apply": res})
            except Exception as e:
                add_log("udp_error", {"err": str(e)})
            if not args.loop: break
    except KeyboardInterrupt:
        pass
    finally:
        try: sock.close()
        except Exception: pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b