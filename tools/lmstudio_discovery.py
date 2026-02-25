# -*- coding: utf-8 -*-
"""CLI: LM Studio Discovery - offlayn scanirovanie i dopisyvanie aliasov v recommend.env.

Mosty (yavnyy):
- (CLI ↔ UI) Te zhe deystviya dostupny iz terminala i admin-paneli, chto snizhaet zavisimost from one interfeysa.

Mosty (skrytye):
- (Nadezhnost ↔ Operatsii) Dry-run po umolchaniyu (A) umenshaet veroyatnost oshibochnoy zapisi.
- (Infrastruktura ↔ Ekonomika) Stdlib-podkhod (bez pip) uproschaet ekspluatatsiyu na “chistykh” mashinakh.

Zemnoy abzats:
Utilita pozvolyaet v oflayne bystro poluchit spisok lokalnykh LM Studio (porty, modeli) i predlozhennye aliasy,
a takzhe primenit ikh (v rezhime B) k faylu ESTER/portable/recommend.env.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()
IS_DRY = AB_MODE != "B"

DEFAULT_PORTS = [1234]
EXTRA_PORTS = [
    int(p.strip()) for p in (os.getenv("LMSTUDIO_EXTRA_PORTS") or "").split(",") if p.strip().isdigit()
]
SCAN_PORTS = sorted(set(DEFAULT_PORTS + EXTRA_PORTS))

RECOMMEND_ENV = Path("ESTER/portable/recommend.env")
RECOMMEND_ENV.parent.mkdir(parents=True, exist_ok=True)

def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _read_recommend_env(env_path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def _append_new_pairs(env_path: Path, new_pairs: Dict[str, str]) -> Tuple[List[str], List[str]]:
    existing = _read_recommend_env(env_path)
    to_add = {k: v for k, v in new_pairs.items() if k not in existing}

    if IS_DRY:
        return sorted(to_add), sorted(set(new_pairs) - set(to_add))

    with env_path.open("a", encoding="utf-8") as f:
        if env_path.stat().st_size and not str(env_path.read_text(encoding="utf-8"))[-1] == "\n":
            f.write("\n")
        for k in sorted(to_add):
            f.write(f"{k}={new_pairs[k]}\n")

    return sorted(to_add), sorted(set(new_pairs) - set(to_add))

def _candidate_dirs() -> List[Path]:
    home = Path.home()
    env_dirs = [
        Path(p.strip()) for p in (os.getenv("LMSTUDIO_SCAN_DIRS") or "").split(";") if p.strip()
    ]
    candidates = [
        home / ".cache" / "lm-studio" / "models",
        home / ".config" / "LM Studio" / "models",
        home / "AppData" / "Roaming" / "LM Studio" / "models",
        Path.cwd() / "models",
    ]
    return [p for p in env_dirs + candidates if p.exists()]

def _scan_models() -> List[Dict[str, str]]:
    res: List[Dict[str, str]] = []
    for root in _candidate_dirs():
        for p in root.rglob("*.gguf"):
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            res.append({"path": str(p), "size": size})
    # Dedup
    unique = {}
    for m in res:
        unique[m["path"]] = m
    return list(unique.values())

def _scan_servers() -> List[Dict[str, object]]:
    servers = []
    for port in SCAN_PORTS:
        base = f"http://127.0.0.1:{port}"
        alive = _port_open("127.0.0.1", port)
        servers.append({"base": base, "alive": alive, "models": []})
    return servers

def _propose_aliases(servers: List[Dict[str, object]]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    friendly_given = False
    for srv in servers:
        base = str(srv["base"])
        port = base.rsplit(":", 1)[-1]
        if srv.get("alive") and not friendly_given:
            aliases["LLM_LOCAL_JARVIS"] = base
            friendly_given = True
        aliases.setdefault(f"LLM_LOCAL_{port}", base)
    return aliases

def discover() -> Dict[str, object]:
    """If there is a module.ltstudio.discovery.discover in the project, use it,
    otherwise local scanner (compatible with offline policy)."""
    try:
        from modules.lmstudio import discovery as core  # type: ignore
        if hasattr(core, "discover") and callable(core.discover):
            return core.discover()
    except Exception:
        pass
    return {"ok": True, "models": _scan_models(), "servers": _scan_servers()}

def main():
    ap = argparse.ArgumentParser(description="LM Studio offline discovery (A/B guard).")
    ap.add_argument("--scan", action="store_true", help="Skanirovat i vyvesti rezultaty")
    ap.add_argument("--apply", action="store_true", help="Sgenerirovat aliasy i (v B) dopisat v recommend.env")
    ap.add_argument("--json", action="store_true", help="Vyvod v JSON")
    ap.add_argument("--env-file", default=str(RECOMMEND_ENV), help="Put k recommend.env")
    args = ap.parse_args()

    env_path = Path(args.env_file)
    result = discover()
    servers = result.get("servers", [])
    models = result.get("models", [])
    aliases = _propose_aliases(servers)

    if args.scan or not (args.scan or args.apply):
        out = {
            "ok": True,
            "ab": AB_MODE,
            "servers": servers,
            "models_count": len(models or []),
            "suggested_aliases": aliases,
        }
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"AB={AB_MODE}")
            print("Servers:")
            for s in servers:
                print(f"  - {s['base']}  alive={s['alive']}")
            print(f"Local models found: {out['models_count']}")
            print("Suggested aliases:")
            for k in sorted(aliases):
                print(f"  {k}={aliases[k]}")

    if args.apply:
        added, skipped = _append_new_pairs(env_path, aliases)
        out = {"ok": True, "ab": AB_MODE, "applied": not IS_DRY, "added": added, "skipped_existing": skipped, "env": str(env_path)}
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"Apply (AB={AB_MODE}): applied={out['applied']}")
            print("  added:", ", ".join(out["added"]) or "-")
            print("  skipped(existing):", ", ".join(out["skipped_existing"]) or "-")

if __name__ == "__main__":
    raise SystemExit(main())
