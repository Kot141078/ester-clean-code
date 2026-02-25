# -*- coding: utf-8 -*-
"""modules/presets/bank_extras.py - Additional bankovskie presety.

MOSTY:
- (Yavnyy) Rasshiryaet standartnye PRESETS bez izmeneniya faylov yadra (cherez import v routes/presets_routes_plus.py).
- (Skrytyy #1) Use persona_style_ext.render_email dlya sovmestimosti tona.
- (Skrytyy #2) Validatsiya faktov i korotkie, konkretnye formulirovki, ne menyayuschie smysl.

ZEMNOY ABZATs:
Pokryvaet chastye keysy: restrukturizatsiya kredita, otsrochka platezha, uvelichenie limita, osparivanie spisaniya.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.persona_style_ext import render_email
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _req(j: Dict[str, Any], keys: list[str]):
    miss = [k for k in keys if not str(j.get(k) or "").strip()]
    if miss:
        raise ValueError("missing_facts:" + ",".join(miss))

def bank_credit_restructuring(f: Dict[str, Any]) -> str:
    _req(f, ["contract", "reason", "proposal"])
    body = (f"I ask you to consider the restructuring under the agreement ZZF0Z: the reason is ZZF1ZZ."
            f"Predlozhenie: {f['proposal']}.")
    return render_email("bank", "letter", body)

def bank_payment_deferral(f: Dict[str, Any]) -> str:
    _req(f, ["contract", "months"])
    note = f.get("reason")
    body = (f"I ask you to provide a deferment of payments under the agreement ZZF0Z to ZZF1ZZ TES."
            + (f" Prichina: {note}." if note else ""))
    return render_email("bank", "request", body)

def bank_card_limit_increase(f: Dict[str, Any]) -> str:
    _req(f, ["card_last4", "new_limit"])
    body = (f"Please increase the limit on the card *ZZF0Z to ZZF1ZZ."
            f"Ready to provide additional information if necessary.")
    return render_email("bank", "request", body)

def bank_charge_dispute(f: Dict[str, Any]) -> str:
    _req(f, ["amount", "date", "merchant"])
    body = (f"I ask you to challenge the write-off of ZZF0Z from ZZF1ZZ from ZZF2ZZ."
            f"The transaction was not confirmed by me; please check.")
    return render_email("bank", "letter", body)

PRESETS_EXTRA = {
    "bank.credit_restructuring": bank_credit_restructuring,
    "bank.payment_deferral": bank_payment_deferral,
    "bank.card_limit_increase": bank_card_limit_increase,
    "bank.charge_dispute": bank_charge_dispute,
}