# -*- coding: utf-8 -*-
"""
tools/dotenv_sanitize.py — otchistka .env i otchet po krivym strokam.

MOSTY:
- Yavnyy: (Fayl .env ↔ Servis) bystro poluchit chistuyu versiyu bez ruchnogo kovyryaniya.
- Skrytyy #1: (CI/Smoke ↔ Kontrol) mozhno vshit v smoke, chtoby lovit isporchennye kommenty.
- Skrytyy #2: (Win/PS ↔ *nix) kross‑platformennaya utilita, odin fayl.

ZEMNOY ABZATs:
Skript delaet .env.sanitized s validnymi KEY=VALUE i skladyvaet podozritelnye stroki v .env.bad_lines — udobno dlya dalneyshey pravki.

c=a+b
"""
from __future__ import annotations
import argparse, pathlib, re, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def parse_env(text: str):
    good, bad = [], []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(('#',';')):
            continue
        if "=" not in line:
            bad.append((i, raw)); continue
        k,v = line.split("=",1)
        k = k.strip()
        if not KEY_RE.match(k):
            bad.append((i, raw)); continue
        v = v.strip()
        if len(v)>=2 and v[0]==v[-1] and v[0] in "\"'":
            v = v[1:-1]
        good.append(f"{k}={v}")
    return good, bad

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--env", default=".env")
    args = p.parse_args()
    path = pathlib.Path(args.env)
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    good, bad = parse_env(text)
    out_good = path.with_suffix(".sanitized")
    out_bad  = path.with_name(path.name + ".bad_lines")
    out_good.write_text("\n".join(good), encoding="utf-8")
    out_bad.write_text("\n".join(f"{ln}: {raw}" for ln,raw in bad), encoding="utf-8")
    print(f"[ok] sanitized -> {out_good}")
    print(f"[ok] bad lines -> {out_bad}")
if __name__ == "__main__":
    main()
# c=a+b