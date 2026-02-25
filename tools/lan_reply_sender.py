# -*- coding: utf-8 -*-
"""tools/lan_reply_sender.py - utilita otpravki LAN-kvitantsii (HTTP/UDP).

Primery:
  # HTTP:
  python -m tools.lan_reply_sender --http http://HOST:PORT/lan/reply --uid JOB --state done --details '{"took_sec":12}' --sender my-node --secret ABC

  # UDP broadcast:
  python -m tools.lan_reply_sender --udp 255.255.255.255:48128 --uid JOB --state error --details '{"msg":"fail"}' --sender my-node --secret ABC

Mosty:
- Yavnyy (Ispolnitel ↔ Dispetcher): prostoy sposob soobschit rezultat.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): odna i ta zhe kvitantsiya dlya oboikh transportov.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, offlayn; secret options.

Zemnoy abzats:
Nebolshaya "ratsiya": nazhal - soobschil "gotovo" i poshel dalshe.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, socket, sys, urllib.request
from modules.lan_reply.protocol import normalize, sign  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _http_post(url: str, obj: dict, secret: str|None):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    if secret:
        req.add_header("X-Signature", sign(obj, secret))
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(resp.status, resp.read().decode("utf-8"))

def _udp_send(addr: str, obj: dict):
    host, port = addr.split(":"); port = int(port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(json.dumps(obj).encode("utf-8"), (host, port))
    sock.close()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Send LAN reply")
    ap.add_argument("--http", help="URL, naprimer http://127.0.0.1:5000/lan/reply")
    ap.add_argument("--udp", help="host:port, naprimer 255.255.255.255:48128")
    ap.add_argument("--uid", required=True)
    ap.add_argument("--state", required=True, choices=["done","error"])
    ap.add_argument("--details", default="{}")
    ap.add_argument("--sender", default="")
    ap.add_argument("--secret", default="")
    args = ap.parse_args(argv)

    try:
        details = json.loads(args.details)
    except Exception:
        print("details: plokhoy JSON", file=sys.stderr); return 2

    obj = {"schema":"ester.lan.reply/1","uid":args.uid,"state":args.state,"details":details,"sender":{"node_id":args.sender},"ts":0}
    obj = normalize(obj)
    if args.secret:
        obj["sig"] = sign(obj, args.secret)

    if args.http:
        _http_post(args.http, obj, args.secret or None)
    elif args.udp:
        _udp_send(args.udp, obj)
    else:
        print(json.dumps(obj, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b