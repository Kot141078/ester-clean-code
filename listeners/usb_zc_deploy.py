# -*- coding: utf-8 -*-
"""listeners/usb_zc_deploy.py - fonovyy avtoprimenitel Zero-Click deploya pri vstavke doverennoy fleshki.

Behavior:
  • Kazhdye interval sek scaniruet list_targets().
  • Dlya kazhdogo toma: plan → esli ok i ne skipped - primenyaet (AB=A → tolko plan, AB=B → realnyy deploy).
  • Uchityvaet apply_once, okno, shtampy.

ENV/config: sm. modules.usb.zc_deploy_settings.

Mosty:
- Yavnyy (Kibernetika ↔ Ekspluatatsiya): avtonomnyy tsikl “obnaruzhil → proveril → primenil/propustil.”
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): detail otchety v stdout (JSON).
- Skrytyy 2 (Praktika ↔ Sovmestimost): drop-in; uvazhaet A/B-rezhim i doverie nositeley.

Zemnoy abzats:
This is “sanitar na vkhode”: uvidel doverennuyu fleshku s relizom - akkuratno perelozhil v sloty i proveril puls.

# c=a+b"""
from __future__ import annotations

import argparse, json, os, time
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.zc_deploy_settings import load_settings  # type: ignore
from modules.usb.zc_deploy import plan_from_mount, apply_from_mount  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Zero-Click Deploy listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = load_settings()
    if not cfg.get("enable"):
        print(json.dumps({"ok": True, "msg": "zc-deploy-disabled"}), flush=True)
        return 0

    iv = int(args.interval or cfg.get("interval", 10))

    try:
        while True:
            for t in list_targets():
                mount = (t.get("mount") or "").strip()
                if not mount: continue
                plan = plan_from_mount(mount, cfg["base_dir"], ab_mode=AB)
                # propuskaem tishinu
                if not plan.get("ok"): 
                    continue
                if plan.get("already") and plan.get("apply_once", True):
                    continue
                rep = apply_from_mount(mount, cfg["base_dir"], ab_mode=AB, health_cmd=cfg.get("health_cmd",""))
                print(json.dumps({"mount": mount, "ab": AB, "result": rep}, ensure_ascii=False), flush=True)
            if not args.loop:
                break
            time.sleep(max(3, iv))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b