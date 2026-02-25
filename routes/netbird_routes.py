# -*- coding: utf-8 -*-
"""routes/netbird_routes.py - sluzhebnye proverki dostupnosti Ester po overleynoy seti (NetBird/Tailscale/Re pr.).

Prefixes: /ops

Ruchki:
  GET /ops/netbird-check
      Klyuchi:
        ?target=IP:port - tsel TCP-podklyucheniya (po umolchaniyu iz ENV NETBIRD_CHECK_TARGET)
        ?path=/healthz — HTTP-put dlya zaprosa k NETBIRD_OVERLAY_BASE (esli zadan)
      Answer:
        {
          "ok": true/false,
          "tcp": {"target":"100.64.0.2:8080","ok":true,"err":""},
          "http": {"url":"http://100.64.0.2:8080/healthz","status":200,"ok":true,"err":""},
          "ifaces": ["lo","eth0","wg0","wt0","netbird0"],
          "notes": [...]
        }

  GET /ops/netbird-ifaces
      Bozvraschaet spisok setevykh interfeysov Re bazovye metadannye (Linux: /proc/net/dev).

Ogranichenie dostupa: tolko lokalnaya set (127.0.0.1/::1/192.168.*), chtoby ne raskryvat topologiyu vovne.

ENV:
  NETBIRD_ENABLED=1 — vklyuchaet smyslovye proverki (ne prepyatstvuet dostupu k endpoyntam)
  NETBIRD_CHECK_TARGET=100.64.0.2:8080 — TCP-tsel po umolchaniyu
  NETBIRD_OVERLAY_BASE=http://100.64.0.2:8080 - bazovyy URL Ester po overleyu; pri nalichii dergaem /healthz (ili ?path=)
  NETBIRD_HTTP_TIMEOUT=2 — taymaut HTTP/TCP (sek)

Zemnoy abzats (inzheneriya):
This is “tester linii”: korotkaya proverka, what overleynyy interfeys zhiv (viden), TCP do tseli ustanavlivaetsya, and HTTP-uzel otvechaet.
R abotaet bez vneshnikh zavisimostey, chitaet /proc/net/dev kak “indikator nalichiya” interfeysa (wg0/wt0/netbird0 Re pr.).

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): diagnosticheskiy kanal obratnoy svyazi - podtverzhdaem rabotosposobnost "nervnogo volokna" (overley).
- Skrytyy 1 (Infoteoriya v†" Set): minimalnyy paket proverki (SYN/ACK + HEAD/GET) daet maximum informatsii na bayt o sostoyanii puti.
- Skrytyy 2 (Anatomiya v†" PO): kak bystryy “reflexes na bol” - prostaya proverka svyazi do vmeshatelstva “kory” (slozhnoy diagnostiki/logov).

# c=a+b"""
from __future__ import annotations

import os
import socket
from typing import Dict, List, Tuple

import requests
from flask import Blueprint, jsonify, request, abort
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("netbird_ops", __name__, url_prefix="/ops")

def _require_local() -> None:
    remote = request.remote_addr or ""
    if remote not in {"127.0.0.1", "::1"} and not remote.startswith("192.168."):
        abort(403, description="local only")

def _list_ifaces() -> List[str]:
    # No external dependencies: Linux path; on other OS it will return empty.
    ifaces: List[str] = []
    try:
        with open("/proc/net/dev", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line and not line.strip().startswith(("Inter-|", "face|")):
                    name = line.split(":")[0].strip()
                    ifaces.append(name)
    except Exception:
        pass
    return ifaces

def _tcp_check(target: str, timeout: float) -> Tuple[bool, str]:
    try:
        if ":" not in target:
            return False, "target_malformed"
        host, port_s = target.rsplit(":", 1)
        port = int(port_s)
        with socket.create_connection((host, port), timeout=timeout):
            return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}:{e}"

def _http_check(base: str, path: str, timeout: float) -> Tuple[bool, int, str]:
    try:
        url = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
        r = requests.get(url, timeout=timeout)
        return (200 <= r.status_code < 400), r.status_code, ""
    except Exception as e:
        return False, 0, f"{type(e).__name__}:{e}"

@bp.get("/netbird-check")
def netbird_check():
    _require_local()

    enabled = (os.getenv("NETBIRD_ENABLED", "1").strip().lower() in {"1", "true", "yes"})
    timeout = float(os.getenv("NETBIRD_HTTP_TIMEOUT", "2"))
    target = (request.args.get("target") or os.getenv("NETBIRD_CHECK_TARGET", "")).strip()
    base = (os.getenv("NETBIRD_OVERLAY_BASE", "")).strip()
    path = (request.args.get("path") or "/healthz").strip() or "/healthz"

    notes: List[str] = []
    if not enabled:
        notes.append("NETBIRD_ENABLED=0 (checks are disabled)")

    ifaces = _list_ifaces()
    # pometim «podozritelno-overleynye» imena
    overlay_names = [n for n in ifaces if any(n.startswith(p) for p in ("wg", "wt", "nb", "netbird", "tailscale"))]

    # TCP
    tcp_ok = None
    tcp_err = ""
    if target:
        ok, err = _tcp_check(target, timeout=timeout)
        tcp_ok, tcp_err = ok, err
    else:
        notes.append("target not set (NETBIRD_CHECK_TARGET or ?target=)")

    # HTTP
    http_ok = None
    http_status = 0
    http_err = ""
    if base:
        ok, status, err = _http_check(base, path, timeout=timeout)
        http_ok, http_status, http_err = ok, status, err
    else:
        notes.append("NETBIRD_OVERLAY_BASE not set, HTTP check skipped")

    return jsonify({
        "ok": (bool(tcp_ok) if tcp_ok is not None else True) and (bool(http_ok) if http_ok is not None else True),
        "tcp": {"target": target, "ok": tcp_ok, "err": tcp_err},
        "http": {"url": (base.rstrip("/") + path) if base else "", "status": http_status, "ok": http_ok, "err": http_err},
        "ifaces": ifaces,
        "overlay_ifaces": overlay_names,
        "notes": notes,
    })

@bp.get("/netbird-ifaces")
def netbird_ifaces():
    _require_local()
    return jsonify({"ok": True, "ifaces": _list_ifaces()})



def register(app):
    app.register_blueprint(bp)
    return app
