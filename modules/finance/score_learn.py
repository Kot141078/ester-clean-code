# -*- coding: utf-8 -*-
"""modules/finance/score_learn.py - skoringa finansovykh putey.

Ideaya:
- Imeem bazovye faktory iz M32: feas (realizuemost), market (rynochnost), speed (skorost), risk_penalty.
- Derzhim vesa dlya agregirovaniya prognoza i kalibrovku po kanalam.
- Pri postuplenii faktov (prodazhi, tsena, trafik, konversiya, TTFB - time-to-first-buy) obnovlyaem vesa i baseline kanala.

Format models (JSON):
{
  "ts": 0,
  "weights": {"feas":1.0,"market":1.0,"speed":1.0,"risk":1.0},
  "channels": {
     "digital_product":{"kpi":{"cr":0.05,"ttfb_days":7},"adj":0.0,"count":0},
     "freelance":{...}
  },
  "history":[{...}] # poslednie N apdeytov
}

MOSTY:
- Yavnyy: (M32 skoring ↔ Memory sobytiy M30) - fakty dokhodov/trafika menyayut vesa, a new otsenki obyasnimy.
- Skrytyy #1: (Infoteoriya ↔ Kalibrovka) - CR/TTFB korrektiruyut “speed/market” bez pereobucheniya na shum.
- Skrytyy #2: (Kibernetika ↔ Ustoychivost) — EMA-gladilka i kapping shagov ne dopuskayut rezkikh skachkov.

ZEMNOY ABZATs:
Inzhenerno - prostaya i prozrachnaya kalibrovka prognoza pod realnye result:
vvel metriki - vesa i normativy kanala slegka smestilis, buduschie plany stali blizhe k zemle.
Prakticheski - Ester so vremenem luchshe predskazyvaet, kuda vkladyvat usiliya, chtoby “1000 €” bylo realnee.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import os, json, time
from math import exp
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.environ.get("ESTER_FINLEARN_ENABLED","1") == "1"
MODEL_PATH = os.environ.get("ESTER_FINLEARN_MODEL","data/finance/score_model.json")

CHANNELS = ["digital_product","freelance","landing_service","course","content_ads","automation_tool"]

_DEFAULT = {
  "ts": 0,
  "weights": {"feas":1.0,"market":1.0,"speed":1.0,"risk":1.0},
  "channels": { ch: {"kpi":{"cr":0.05,"ttfb_days":7},"adj":0.0,"count":0} for ch in CHANNELS },
  "history": []
}

def _ensure_model()->Dict[str,Any]:
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        with open(MODEL_PATH,"w",encoding="utf-8") as f: json.dump(_DEFAULT, f, ensure_ascii=False, indent=2)
    try:
        with open(MODEL_PATH,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        return dict(_DEFAULT)

def _save(m:Dict[str,Any])->Dict[str,Any]:
    m["ts"]=int(time.time())
    with open(MODEL_PATH,"w",encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=2)
    return {"ok":True,"path":MODEL_PATH}

def probe()->Dict[str,Any]:
    m=_ensure_model()
    return {"ok":True,"enabled":ENABLED,"path":MODEL_PATH,"weights":m.get("weights"),"channels":m.get("channels")}

def predict_base(channel:str, feas:int, market:int, speed:int, risk_penalty:int)->Dict[str,Any]:
    m=_ensure_model()
    w=m.get("weights",{})
    ch=m.get("channels",{}).get(channel, _DEFAULT["channels"][CHANNELS[0]])
    # Bazovyy skor iz M32 (0..100)
    base = max(0, min(100, feas*w.get("feas",1.0) + market*w.get("market",1.0) + speed*w.get("speed",1.0) - risk_penalty*w.get("risk",1.0)))
    # Korrektirovka kanala (adj v diapazone ~[-8..+8])
    adj = max(-8.0, min(8.0, float(ch.get("adj",0.0))))
    score = max(0.0, min(100.0, base + adj))
    explain = {
      "base": base,
      "weights": w,
      "channel_adj": adj,
      "kpi_ref": ch.get("kpi",{})
    }
    return {"ok":True,"score":score,"explain":explain}

def _ema(old:float, new:float, alpha:float)->float:
    return old*(1.0-alpha) + new*alpha

def submit_outcome(channel:str, sales:int, price:float, visitors:int, ttfb_days:int)->Dict[str,Any]:
    """Update:
      - KPI kanala: CR = sales/visitors, TTFB (EMA-gladilka).
      - adj kanala: esli CR >> etalona i TTFB << etalona, ​​slegka povyshaem; naoborot - ponizhaem.
      - weights: esli "bystryy uspekh" — slegka ↑ vesa speed/market; esli long i empty — ↑ risk, ↓ market.
    Kep shaga: maximum 0.05 na ves, 0.5 na adj za obnovlenie."""
    if not ENABLED: return {"ok":False,"error":"disabled"}
    m=_ensure_model()
    sales=max(0,int(sales)); visitors=max(1,int(visitors)); price=max(0.0,float(price)); ttfb=max(0,int(ttfb_days))
    cr = min(1.0, sales/float(visitors))
    ch = m["channels"].setdefault(channel, {"kpi":{"cr":0.05,"ttfb_days":7},"adj":0.0,"count":0})
    # ETA for KPI
    alpha = 0.3  # moderate inertia
    ch["kpi"]["cr"] = _ema(float(ch["kpi"].get("cr",0.05)), cr, alpha)
    ch["kpi"]["ttfb_days"] = _ema(float(ch["kpi"].get("ttfb_days",7.0)), float(ttfb), alpha)
    ch["count"] = int(ch.get("count",0))+1

    # Adaptation of adj in relation to reference KPIs
    target_cr = ch["kpi"]["cr"]
    target_ttfb = ch["kpi"]["ttfb_days"]
    adj_step = 0.0
    # If the CD for an update is significantly > the current reference, and the TFB is below 1/2 of the reference, it encourages
    if cr > target_cr*1.3 and ttfb < max(1.0, target_ttfb*0.5):
        adj_step = +0.3
    # Esli CR ≪ referensa i TTFB v 2 raza khuzhe — shtrafuem
    elif cr < max(0.01, target_cr*0.7) and ttfb > target_ttfb*1.8:
        adj_step = -0.3
    # Step and accumulation limit
    adj_step = max(-0.5, min(0.5, adj_step))
    ch["adj"] = max(-8.0, min(8.0, float(ch.get("adj",0.0)) + adj_step))

    # Global weight correction (soft)
    w=m["weights"]
    if sales>=1 and ttfb<=3:
        # bystryy uspekh → skorrektirovat v sideronu speed/market
        w["speed"] = max(0.5, min(2.0, w.get("speed",1.0) + 0.05))
        w["market"] = max(0.5, min(2.0, w.get("market",1.0) + 0.03))
    elif sales==0 and visitors>=200 and ttfb>=7:
        # plokho idet → usilit risk, ponizit market
        w["risk"] = max(0.5, min(2.0, w.get("risk",1.0) + 0.05))
        w["market"] = max(0.5, min(2.0, w.get("market",1.0) - 0.03))
    # Istoriya
    m.setdefault("history",[]).append({
      "ts": int(time.time()),
      "channel": channel,
      "sales": sales, "price": price, "visitors": visitors, "ttfb_days": ttfb,
      "cr": cr, "adj_step": adj_step, "weights": dict(m["weights"]), "ch": dict(ch)
    })
    # Let's truncate the history to the last 500
    m["history"]=m["history"][-500:]
    return _save(m)

def model()->Dict[str,Any]:
    return {"ok":True, **_ensure_model()}

def reset()->Dict[str,Any]:
    return _save(dict(_DEFAULT))