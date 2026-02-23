# -*- coding: utf-8 -*-
"""
Generator owner-JWT dlya Ester.

Sovmestim s dvumya versiyami modules.security.jwt_owner.generate_owner_jwt:

1) Staraya signatura:
       generate_owner_jwt(sub: str, roles: list[str], ttl_days: int, save_path: str) -> dict

2) Novaya signatura:
       generate_owner_jwt(cfg: dict | None = None) -> dict | str
   gde cfg mozhet soderzhat:
       {
         "sub": ...,
         "roles": [...],
         "ttl_days": ...,
         "save_path": ...
       }

Skript sam opredelyaet, kak vyzyvat funktsiyu.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import inspect
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.security.jwt_owner import generate_owner_jwt
except Exception as e:  # zemlya: esli modul ne importiruetsya — ne zapuskaem raketu bez topliva
    raise SystemExit(f"[gen_owner_jwt] Ne udalos importirovat modules.security.jwt_owner: {e}")


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sub",
        default=os.getenv("ESTER_OWNER_SUB", "owner"),
        help="sub (subject) dlya tokena (po umolchaniyu 'owner')",
    )
    p.add_argument(
        "--roles",
        nargs="*",
        default=None,
        help="Spisok roley (po umolchaniyu owner admin)",
    )
    p.add_argument(
        "--ttl",
        type=int,
        default=None,
        help="Srok zhizni v dnyakh (esli ne zadan, beretsya JWT_TTL_DAYS ili 365)",
    )
    p.add_argument(
        "--save",
        default=os.path.join("data", "owner_jwt.token"),
        help="Fayl dlya sokhraneniya tokena",
    )
    p.add_argument(
        "--print-only",
        action="store_true",
        help="Pechatat tolko token (bez obertki JSON)",
    )
    return p.parse_args(argv)


def call_generate(sub: str, roles, ttl_days: int | None, save_path: str):
    # znacheniya po umolchaniyu
    if not roles:
        roles = ["owner", "admin"]
    if ttl_days is None:
        try:
            ttl_days = int(os.getenv("JWT_TTL_DAYS", "365"))
        except ValueError:
            ttl_days = 365

    # gotovim konfig dlya novoy signatury
    cfg = {
        "sub": sub,
        "roles": roles,
        "ttl_days": ttl_days,
        "save_path": save_path,
    }

    # analiziruem signaturu generate_owner_jwt
    try:
        sig = inspect.signature(generate_owner_jwt)
        params = list(sig.parameters.values())
    except Exception:
        # ne poluchilos posmotret signaturu — probuem staryy stil
        params = []

    # Variant 1: novaya signatura (0 ili 1 argument)
    if len(params) <= 1:
        try:
            res = generate_owner_jwt(cfg) if len(params) == 1 else generate_owner_jwt()
        except TypeError:
            # na sluchay, esli realizatsiya ozhidaet imenno cfg
            res = generate_owner_jwt(cfg)
    # Variant 2: staraya signatura (4 pozitsionnykh)
    elif len(params) >= 4:
        res = generate_owner_jwt(sub, roles, ttl_days, save_path)
    else:
        # strannaya signatura — pytaemsya peredat cfg kak edinstvennyy argument
        res = generate_owner_jwt(cfg)

    # Normalizuem otvet: dict s polem token
    if isinstance(res, str):
        return {"token": res, "sub": sub, "roles": roles, "ttl_days": ttl_days, "path": save_path}
    if isinstance(res, dict):
        if "token" not in res and "jwt" in res:
            res["token"] = res.get("jwt")
        return res

    # fallback
    raise RuntimeError("generate_owner_jwt vernul neozhidannyy tip: %r" % (type(res),))


def main(argv=None) -> int:
    a = parse_args(argv or sys.argv[1:])
    info = call_generate(a.sub, a.roles, a.ttl, a.save)

    tok = info.get("token", "")

    # sokhranyaem v fayl (esli funktsiya vnutri esche ne sokhranila)
    try:
        path = a.save
        if path and tok:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(tok.strip())
    except Exception:
        # ne kritichno dlya raboty
        pass

    if a.print_only:
        print(tok)
    else:
        print(json.dumps(info, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())