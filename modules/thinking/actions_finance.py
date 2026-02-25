# -*- coding: utf-8 -*-
"""modules/thinking/actions_finance.py - eksheny dlya myslitelnykh konveyerov (finansy/Papa).

Mosty:
- Yavnyy: (Mysli ↔ Finansy) gotovim platezhki i proveryaem IBAN po trebovaniyu “voli”.
- Skrytyy #1: (Zabota ↔ Papa) dostup k profilyu/skanu rekvizitov.
- Skrytyy #2: (Etika ↔ Ogranicheniya) dalneyshaya otpravka - vne sistemy.

Zemnoy abzats:
Mozg poprosil - poluchili validnyy IBAN, sdelali pain.001, podsmotreli kandidaty schetov Papy.
Obedineno iz dvukh versiy: add draft_pain001 dlya chernovikov, logging dlya pamyati Ester, P2P-share dlya detsentralizatsii.

# c=a+b"""
from __future__ import annotations
import logging
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Setting up logging for the “memory” of calls/errors in Esther
logging.basicConfig(filename="data/logs/thinking_finance.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_viban(args: Dict[str, Any]):
        from modules.finance.sepa import validate_iban  # type: ignore
        iban = str(args.get("iban", ""))
        try:
            res = validate_iban(iban)
            logging.info(f"Validated IBAN '{iban}': {res['valid']}")
            return res
        except ValueError as e:
            logging.error(f"IBAN validate error: {str(e)}")
            return {"ok": False, "error": str(e)}

    register("finance.iban.validate", {"iban": "str"}, {"ok": "bool", "valid": "bool"}, 2, a_viban)

    def a_pain(args: Dict[str, Any]):
        mode = str(args.get("mode", "make")).lower()
        if mode == "draft":
            from modules.finance.sepa import draft_pain001  # type: ignore
            func = draft_pain001
        else:
            from modules.finance.sepa import make_pain001  # type: ignore
            func = make_pain001
        try:
            res = func(args or {})
            logging.info(f"Created pain001 in mode '{mode}': ok={res.get('ok')}")
            return res
        except Exception as e:
            logging.error(f"Pain001 error in mode '{mode}': {str(e)}")
            return {"ok": False, "error": str(e)}

    register("finance.sepa.pain001",
             {"debtor": "dict", "creditor": "dict", "amount": "float", "currency": "str", "purpose": "str", "end_to_end": "str", "mode": "str"},
             {"ok": "bool", "path": "str"}, 30, a_pain)

    def a_pp_get(args: Dict[str, Any]):
        from modules.papa.resolver import get_profile  # type: ignore
        try:
            profile = get_profile()
            logging.info("Got papa profile")
            return {"ok": True, "profile": profile}
        except Exception as e:
            logging.error(f"Papa profile get error: {str(e)}")
            return {"ok": False, "error": str(e)}

    register("papa.profile.get", {}, {"ok": "bool", "profile": "dict"}, 1, a_pp_get)

    def a_pp_scan(args: Dict[str, Any]):
        from modules.papa.resolver import scan_accounts  # type: ignore
        roots = list(args.get("roots") or ["data"])
        try:
            res = scan_accounts(roots)
            logging.info(f"Scanned papa accounts in {roots}: count={res.get('count')}")
            return res
        except Exception as e:
            logging.error(f"Papa accounts scan error: {str(e)}")
            return {"ok": False, "error": str(e)}

    register("papa.accounts.scan", {"roots": "list"}, {"ok": "bool", "count": "int"}, 20, a_pp_scan)

    def a_pp_share(args: Dict[str, Any]):
        from modules.papa.resolver import get_profile  # type: ignore
        target = str(args.get("target", ""))
        if not target:
            return {"ok": False, "error": "no_target"}
        try:
            import json, urllib.request
            profile = get_profile()
            body = json.dumps({"profile": profile}).encode("utf-8")
            req = urllib.request.Request(f"http://{target}/p2p/papa/share", data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            logging.info(f"Shared papa profile to {target}")
            return {"ok": True}
        except Exception as e:
            logging.error(f"Papa profile share error to {target}: {str(e)}")
            return {"ok": False, "error": str(e)}

    register("papa.profile.share", {"target": "str"}, {"ok": "bool"}, 10, a_pp_share)

# _reg()
# Expansion idea: to synthesize payments from Yudzhe, send payin001 to the cloud LLM for audit (eg, chess complianke).
# I implement it in finance_yuje.po: a_pine() + HTTP then Yuje, if you say so.