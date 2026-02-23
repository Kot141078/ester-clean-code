# -*- coding: utf-8 -*-
"""
tools/firststart_profile.py — CLI: profil uzla, rekomendatsii i zapis recommend.env/profile.json.

Primery:
  # Pokazat profil i ENV-prevyu
  python tools/firststart_profile.py --preview

  # Zapisat ESTER/portable/profile.json + recommend.env (AB=A → dry; AB=B → zapis)
  python tools/firststart_profile.py --apply

Kody vykhoda:
  0 — uspekh (vklyuchaya dry)
  1 — oshibka (naprimer, net USB)

Mosty:
- Yavnyy (DevOps ↔ UX): te zhe deystviya, chto i v UI, dostupny v stsenariyakh/cron.
- Skrytyy 1 (Infoteoriya): odin i tot zhe determinirovannyy podbor.
- Skrytyy 2 (Praktika): zapis tolko v portable/* pri AB=B.

Zemnoy abzats:
Eto «knopka bez brauzera»: bystro poluchit ENV dlya uzla i polozhit ryadom dlya zapuska.

# c=a+b
"""
from __future__ import annotations
import argparse, json
from modules.portable.self_profile import detect_system, choose_recommendations, render_recommend_env, write_profile_and_env  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester First Start (profile & recommendations)")
    ap.add_argument("--preview", action="store_true", help="Pokazat profil i ENV-prevyu")
    ap.add_argument("--apply", action="store_true", help="Zapisat profile.json + recommend.env")
    args = ap.parse_args(argv)

    sysinfo = detect_system()
    rec = choose_recommendations(sysinfo)
    if args.preview:
        out = {
            "ok": True,
            "system": sysinfo,
            "recommend": rec,
            "env_preview": render_recommend_env(sysinfo, rec)
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.apply:
        res = write_profile_and_env(sysinfo, rec)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b