# -*- coding: utf-8 -*-
"""Generator owner-JWT dlya Ester.

Sovmestim s dvumya versiyami modules.security.jwt_owner.generate_owner_jwt:

1) Staraya signatura:
       generate_owner_jwt(sub: str, roles: list[str], ttl_days: int, save_path: str) -> dict

2) Novaya signatura:
       generate_owner_jwt(cfg: dict | None = None) -> dict | str
   where cfg mozhet soderzhat:
       {
         "sub": ...,
         "roles": [...],
         "ttl_days": ...,
         "save_path": ...
       }

Skript sam opredelyaet, kak vyzyvat funktsiyu."""

from __future__ import annotations

import os
import sys
import json
import argparse
import inspect
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.security.jwt_owner import generate_owner_jwt
except Exception as e:  # earth: if the module is not imported, we do not launch the rocket without fuel
    raise SystemExit(f"yugen_ovner_zhvtsch Failed to import modules.security.zhvt_ovner: ZZF0Z")


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sub",
        default=os.getenv("ESTER_OWNER_SUB", "owner"),
        help="sub (subject) for token (default)",
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
        help="Lifetime in days (if not specified, take ZVT_TTL_DAYS or 365)",
    )
    p.add_argument(
        "--save",
        default=os.path.join("data", "owner_jwt.token"),
        help="File to save the token",
    )
    p.add_argument(
        "--print-only",
        action="store_true",
        help="Print only the token (without the JSION wrapper)",
    )
    return p.parse_args(argv)


def call_generate(sub: str, roles, ttl_days: int | None, save_path: str):
    # default values
    if not roles:
        roles = ["owner", "admin"]
    if ttl_days is None:
        try:
            ttl_days = int(os.getenv("JWT_TTL_DAYS", "365"))
        except ValueError:
            ttl_days = 365

    # preparing the config for the new signature
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
            # in case the implementation awaits the sfg
            res = generate_owner_jwt(cfg)
    # Option 2: old signature (4 positional)
    elif len(params) >= 4:
        res = generate_owner_jwt(sub, roles, ttl_days, save_path)
    else:
        # strange signature - we are trying to pass sfg as the only argument
        res = generate_owner_jwt(cfg)

    # Normalizes response: dist with token field
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

    # save to a file (if the function inside has not yet been saved)
    try:
        path = a.save
        if path and tok:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(tok.strip())
    except Exception:
        # not critical for work
        pass

    if a.print_only:
        print(tok)
    else:
        print(json.dumps(info, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())