# -*- coding: utf-8 -*-
"""
modules/presets/bank_extras.py — Dopolnitelnye bankovskie presety.

MOSTY:
- (Yavnyy) Rasshiryaet standartnye PRESETS bez izmeneniya faylov yadra (cherez import v routes/presets_routes_plus.py).
- (Skrytyy #1) Ispolzuet persona_style_ext.render_email dlya sovmestimosti tona.
- (Skrytyy #2) Validatsiya faktov i korotkie, konkretnye formulirovki, ne menyayuschie smysl.

ZEMNOY ABZATs:
Pokryvaet chastye keysy: restrukturizatsiya kredita, otsrochka platezha, uvelichenie limita, osparivanie spisaniya.

# c=a+b
"""
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
    body = (f"Proshu rassmotret restrukturizatsiyu po dogovoru {f['contract']}: prichina — {f['reason']}. "
            f"Predlozhenie: {f['proposal']}.")
    return render_email("bank", "letter", body)

def bank_payment_deferral(f: Dict[str, Any]) -> str:
    _req(f, ["contract", "months"])
    note = f.get("reason")
    body = (f"Proshu predostavit otsrochku platezhey po dogovoru {f['contract']} na {f['months']} mes."
            + (f" Prichina: {note}." if note else ""))
    return render_email("bank", "request", body)

def bank_card_limit_increase(f: Dict[str, Any]) -> str:
    _req(f, ["card_last4", "new_limit"])
    body = (f"Proshu uvelichit limit po karte *{f['card_last4']} do {f['new_limit']}. "
            f"Gotov predostavit dopolnitelnye svedeniya pri neobkhodimosti.")
    return render_email("bank", "request", body)

def bank_charge_dispute(f: Dict[str, Any]) -> str:
    _req(f, ["amount", "date", "merchant"])
    body = (f"Proshu osporit spisanie {f['amount']} ot {f['date']} u {f['merchant']}. "
            f"Tranzaktsiya ne podtverzhdalas mnoy; proshu provesti proverku.")
    return render_email("bank", "letter", body)

PRESETS_EXTRA = {
    "bank.credit_restructuring": bank_credit_restructuring,
    "bank.payment_deferral": bank_payment_deferral,
    "bank.card_limit_increase": bank_card_limit_increase,
    "bank.charge_dispute": bank_charge_dispute,
}