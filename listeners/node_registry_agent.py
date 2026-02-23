# -*- coding: utf-8 -*-
"""
listeners/node_registry_agent.py — agent avto-registratsii uzla.

Povedenie:
  • Kazhdye REGISTRY_TICK_SEC sobiraet capabilities -> sokhranyaet v REGISTRY_DIR/nodes/<id>.json.
  • Esli naydena portable-USB i REGISTRY_USB_EXPORT=1 — eksportiruet na USB/ESTER/nodes/.
  • (Opts.) REGISTRY_UDP_ENABLE=1 — shlet UDP-mayak s node_id i kratkoy metainfoy (best-effort).

Mosty:
- Yavnyy (Inventarizatsiya ↔ Rasprostranenie): uzel sam soobschaet «kto ya i chto umeyu».
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): periodicheskie slepki s ts, offlayn-sovmestimost cherez USB.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, AB-predokhranitel, set — tolko lokalnaya/opts.

Zemnoy abzats:
Kak tablichka na dveri tsekha: regulyarno obnovlyaemaya, plyus kopiya prikolota k perenosnomu schitu (USB).

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, socket, time
from pathlib import Path

from modules.registry.capabilities import build_capabilities  # type: ignore
from modules.registry.node_catalog import save_self_capabilities, export_to_usb  # type: ignore
from modules.portable.env import detect_portable_root  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _udp_beacon(payload: dict) -> None:
    if os.getenv("REGISTRY_UDP_ENABLE","0") != "1": return
    try:
        port = int(os.getenv("REGISTRY_UDP_PORT","48127"))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(json.dumps(payload).encode("utf-8"), ("255.255.255.255", port))
        s.close()
    except Exception:
        pass

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester Node Registry Agent")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--period", type=int, default=int(os.getenv("REGISTRY_TICK_SEC","30")))
    args = ap.parse_args(argv)

    try:
        while True:
            cap = build_capabilities()
            res = save_self_capabilities(cap)
            usb = detect_portable_root(None)
            exported = None
            if usb and os.getenv("REGISTRY_USB_EXPORT","1") == "1":
                exported = export_to_usb(usb, cap)
            _udp_beacon({"schema":"ester.cap.beacon/1","node_id":cap["node_id"],"ts":cap["ts"],"class":cap["hw"]["class"]})
            print(json.dumps({"ts": int(time.time()), "mod":"registry", "saved": bool(res.get("ok")), "usb": bool(exported)}), flush=True)
            if not args.loop: break
            time.sleep(max(5, int(args.period)))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b