# -*- coding: utf-8 -*-
"""
listeners/usb_hotask.py — avto-reaktsiya na vstavku fleshki: auto/ask odin vopros.

Povedenie:
  • Kazhdye USB_HOTASK_POLL_SEC: ischet novye tochki montirovaniya.
  • Reshaet action: "update" (esli est ESTER/portable/self) ili "build".
  • MODE=auto — zapuskaet build_on_usb srazu; MODE=ask — kladet pending i (opts.) shlet uvedomlenie v Telegram.
  • Cooldown zaschischaet ot povtorov dlya odnoy fleshki.

ENV:
  USB_HOTASK_MODE=auto|ask
  USB_HOTASK_COOLDOWN_SEC=300
  USB_HOTASK_TG_NOTIFY=0

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Portable): minimalnyy friction pri perenose kopii.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): logi JSON, edinaya ochered pending.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, dry-rezhim, Telegram-notis po zhelaniyu.

Zemnoy abzats:
Eto «dezhurnyy u vorot»: vidit novuyu fleshku, zadaet odin vopros (ili deystvuet sam) i vse delaet bez suety.

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path

from modules.portable.env import find_usb_mounts  # type: ignore
from modules.portable.builder import build_on_usb, plan_build  # type: ignore
from modules.portable.hotask_state import was_recently_seen, mark_seen, add_pending, add_log  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _has_self(usb_root: Path) -> bool:
    return (usb_root / "ESTER" / "portable" / "self").exists()

def _maybe_tg_notify(mount: str, action: str, pid: str) -> None:
    if os.getenv("USB_HOTASK_TG_NOTIFY","0") != "1": return
    try:
        from modules.telegram.settings import load_settings  # type: ignore
        from modules.telegram.api import tg_send_message     # type: ignore
        cfg = load_settings()
        tok = cfg.get("token"); chat = (cfg.get("chats") or {}).get("last_chat")
        if not tok or not chat: return
        txt = f"[Ester] USB Hot-Ask: mount={mount} action={action}. Podtverdi v UI (/admin/portable) ili ustanovi USB_HOTASK_MODE=auto."
        tg_send_message(tok, int(chat), txt)
    except Exception:
        pass

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Hot-Ask Listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--period", type=int, default=int(os.getenv("USB_HOTASK_POLL_SEC","4")))
    args = ap.parse_args(argv)

    cooldown = int(os.getenv("USB_HOTASK_COOLDOWN_SEC","300"))
    mode = (os.getenv("USB_HOTASK_MODE") or "auto").strip().lower()

    try:
        while True:
            mounts = find_usb_mounts()
            for m in mounts:
                ms = str(m)
                if was_recently_seen(ms, cooldown): 
                    continue
                action = "update" if _has_self(m) else "build"
                if mode == "auto":
                    # vypolnyaem srazu
                    res = build_on_usb(m, {})
                    add_log("auto", {"mount": ms, "action": action, "ab": AB, "result": res})
                    mark_seen(ms)
                else:
                    # zadadim vopros (pending)
                    p = add_pending(ms, action, mode)
                    _maybe_tg_notify(ms, action, p.get("id",""))
                    add_log("ask", {"mount": ms, "action": action, "ab": AB, "pending_id": p.get("id")})
                    mark_seen(ms)
            print(json.dumps({"ts": int(time.time()), "mod":"usb_hotask", "mode": mode, "seen_count": len(mounts)}), flush=True)
            if not args.loop: break
            time.sleep(max(2, int(args.period)))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b