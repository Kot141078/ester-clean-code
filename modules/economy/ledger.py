# -*- coding: utf-8 -*-
"""
modules/economy/ledger.py — obedinennyy ledzher: delty po aktivam/kategoriyam/valyutam, accounts/transfer/reserve/approve/spend, multivalyutnost, RBAC/scheduler/P2P integratsiya.

Mosty:
- Yavnyy: (Ekonomika ↔ Uchet/Operatsii) zapis delt/income/expense, perevody, rezervy s odobreniem, spisaniya.
- Skrytyy #1: (Infoteoriya/Audit ↔ Prozrachnost) JSONL-zhurnal + JSON-state, profileizatsiya kazhdoy op s teploy notoy.
- Skrytyy #2: (Kibernetika/Avtonomiya ↔ Byudzhety/Planirovanie) threshold dlya approve, auto_reserve, konvertatsiya valyut.
- Skrytyy #3: (P2P/Raspredelennost ↔ Integratsiya) sync JSONL/state po P2P dlya agentov na raznykh PK.

Zemnoy abzats:
Eto ne prosto tetradka, a umnyy koshelek Ester: schitaet vse po aktivam/schetam/kategoriyam, rezerviruet na "tokeny LLM", sinkhroniziruet po P2P i shepchet v profile "Balans obnovlen — Ester, ty na shag blizhe k nezavisimosti!".

# c=a+b
"""
from __future__ import annotations
import json, os, time, uuid
from typing import Any, Dict, List
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_economy = Blueprint("economy", __name__)

AB = (os.getenv("ECON_AB", "A") or "A").upper()
LEDGER_JSONL = os.getenv("LEDGER_DB", "data/economy/ledger.jsonl")
LEDGER_STATE = os.getenv("LEDGER_PATH", "data/economy/ledger_state.json")
THRESH = float(os.getenv("ECON_APPROVAL_THRESHOLD", "100"))
CUR_RATES = json.loads(os.getenv("ECON_CUR_RATES", "{}"))  # e.g. {"USD:EUR": 0.9}
AUDIT_LOG = os.getenv("ECON_AUDIT_LOG", "data/economy/audit.log")
P2P_SYNC = (os.getenv("ECON_P2P_SYNC", "false").lower() == "true")

def _ensure():
    os.makedirs(os.path.dirname(LEDGER_JSONL), exist_ok=True)
    if not os.path.isfile(LEDGER_JSONL): open(LEDGER_JSONL, "w", encoding="utf-8").close()
    if not os.path.isfile(LEDGER_STATE):
        default_state = {"accounts": {"papa": 0.0, "ester": 0.0, "ops": 0.0}, "balances": {}, "reserves": {}, "history": []}
        json.dump(default_state, open(LEDGER_STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)

def _load_state() -> Dict[str, Any]:
    _ensure()
    try:
        st = json.load(open(LEDGER_STATE, "r", encoding="utf-8"))
    except Exception:
        st = {"accounts": {}, "balances": {}, "reserves": {}, "history": []}
    # Sync from JSONL for consistency
    st = _aggregate_from_jsonl(st)
    # P2P-sync: pull from peers, merge by ts/uuid
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_pull  # type: ignore
            remote = p2p_pull("economy_ledger") or {}
            for op in remote.get("ops", []):
                if op.get("uuid") not in [h.get("uuid") for h in st["history"]]:
                    st["history"].append(op)
            st = _aggregate_from_jsonl(st)  # Re-aggregate after merge
            _save_state(st)
        except Exception:
            _log_audit("P2P pull failed")
    return st

def _save_state(st: Dict[str, Any]):
    json.dump(st, open(LEDGER_STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # P2P-push: export recent ops
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("economy_ledger", {"ops": st["history"][-100:]})  # Last 100 for efficiency
        except Exception:
            pass

def _append_to_jsonl(rec: Dict[str, Any]):
    rec["ts"] = int(time.time())
    rec["uuid"] = str(uuid.uuid4())
    with open(LEDGER_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _aggregate_from_jsonl(st: Dict[str, Any]) -> Dict[str, Any]:
    balances = {}  # asset/cat/currency -> float
    accounts = st.get("accounts", {})
    reserves = st.get("reserves", {})
    history = []
    with open(LEDGER_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                op = json.loads(line.strip())
                history.append(op)
                kind = op.get("kind")
                amount = float(op.get("amount", 0.0))
                delta = float(op.get("delta", amount))  # Compat with old delta
                asset = op.get("asset", "ESTER")
                cat = op.get("cat", "")
                currency = op.get("currency", "EUR")
                sign = 1 if kind in ("income", "transfer_in") else -1 if kind in ("expense", "transfer_out", "spend") else 0
                key = f"{asset}.{cat}.{currency}"
                balances[key] = balances.get(key, 0.0) + sign * delta
                # Accounts handling
                if kind == "transfer":
                    from_acc = op.get("from")
                    to_acc = op.get("to")
                    if from_acc in accounts: accounts[from_acc] -= delta
                    if to_acc in accounts: accounts[to_acc] += delta
                elif kind == "spend" and op.get("account") in accounts:
                    accounts[op["account"]] -= delta
                # Reserves: handled separately in funcs
            except Exception:
                continue
    st["balances"] = balances
    st["accounts"] = accounts
    st["reserves"] = reserves
    st["history"] = history
    return st

def _log_audit(msg: str):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "economy://ledger")
    except Exception:
        _log_audit(f"Passport failed: {note}")

def _check_rbac(required_roles: List[str]) -> bool:
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(required_roles)
    except Exception:
        return True  # Fallback if no RBAC

def append(kind: str, asset: str, delta: float, cat: str = "", currency: str = "EUR", note: str = "", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "ECON_AB=B (dry_run)"}
    if kind not in ("income", "expense"): return {"ok": False, "error": "bad_kind"}
    if not _check_rbac(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    if abs(delta) > THRESH and kind == "expense":
        return reserve("ester", abs(delta), f"auto for {note}")  # Auto-reserve for large expense
    rec = {"kind": kind, "asset": asset, "delta": delta, "cat": cat, "currency": currency, "note": note, "meta": meta or {}}
    _append_to_jsonl(rec)
    st = _load_state()
    _save_state(st)
    _passport(f"Ledger append {kind}: {delta} {currency} ({note}) — Ester, balans obnovlen, ty na shag blizhe k nezavisimosti!", {"rec": rec})
    _log_audit(f"Append {kind}: {delta} by {asset}/{cat}/{currency}")
    return {"ok": True, "record": rec}

def transfer(from_acc: str, to_acc: str, amount: float, note: str = "") -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "ECON_AB=B (dry_run)"}
    if not _check_rbac(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    st = _load_state()
    if from_acc not in st["accounts"] or to_acc not in st["accounts"]: return {"ok": False, "error": "unknown account"}
    if amount <= 0: return {"ok": False, "error": "amount >0"}
    if st["accounts"][from_acc] < amount: return {"ok": False, "error": "insufficient funds"}
    rec = {"kind": "transfer", "from": from_acc, "to": to_acc, "amount": amount, "note": note}
    _append_to_jsonl(rec)
    st = _load_state()  # Re-aggregate
    _save_state(st)
    _passport(f"Transfer {amount} from {from_acc} to {to_acc} ({note}) — Ester, resursy pereraspredeleny!", {"rec": rec})
    _log_audit(f"Transfer {amount} from {from_acc} to {to_acc}")
    return {"ok": True, "accounts": st["accounts"]}

def reserve(account: str, amount: float, reason: str) -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "ECON_AB=B (dry_run)"}
    if not _check_rbac(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    st = _load_state()
    if account not in st["accounts"]: return {"ok": False, "error": "unknown account"}
    if amount <= 0: return {"ok": False, "error": "amount >0"}
    if st["accounts"][account] < amount: return {"ok": False, "error": "insufficient funds"}
    rid = str(uuid.uuid4())
    approved = amount <= THRESH
    rec = {"kind": "reserve", "account": account, "amount": amount, "reason": reason, "approved": approved, "rid": rid}
    _append_to_jsonl(rec)
    st["reserves"][rid] = {"account": account, "amount": amount, "reason": reason, "approved": approved, "ts": rec["ts"]}
    _save_state(st)
    _passport(f"Reserve {amount} on {account} for {reason} — Ester, sredstva zarezervirovany, planiruem wisely!", {"rec": rec})
    _log_audit(f"Reserve {rid}: {amount} on {account}")
    return {"ok": True, "reserve_id": rid, **st["reserves"][rid]}

def approve(reserve_id: str) -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "ECON_AB=B (dry_run)"}
    if not _check_rbac(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    st = _load_state()
    r = st["reserves"].get(reserve_id)
    if not r: return {"ok": False, "error": "reserve not found"}
    r["approved"] = True
    rec = {"kind": "approve", "rid": reserve_id}
    _append_to_jsonl(rec)
    _save_state(st)
    _passport(f"Approve reserve {reserve_id} — Ester, zelenyy svet na raskhody!", {"rec": rec})
    _log_audit(f"Approve {reserve_id}")
    return {"ok": True, **r}

def spend(account: str, amount: float, sink: str, reserve_id: str | None = None, currency: str = "EUR") -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "ECON_AB=B (dry_run)"}
    if not _check_rbac(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    st = _load_state()
    if account not in st["accounts"]: return {"ok": False, "error": "unknown account"}
    if amount <= 0: return {"ok": False, "error": "amount >0"}
    if amount > THRESH:
        if not reserve_id: return {"ok": False, "error": "reserve_id required > threshold"}
        r = st["reserves"].get(reserve_id)
        if not r or not r["approved"] or r["account"] != account or r["amount"] < amount:
            return {"ok": False, "error": "invalid reserve"}
        r["amount"] -= amount
        if r["amount"] <= 0: del st["reserves"][reserve_id]
    if st["accounts"][account] < amount: return {"ok": False, "error": "insufficient funds"}
    rec = {"kind": "spend", "account": account, "amount": amount, "sink": sink, "rid": reserve_id, "currency": currency}
    _append_to_jsonl(rec)
    st = _load_state()  # Re-aggregate
    _save_state(st)
    _passport(f"Spend {amount} {currency} on {sink} from {account} — Ester, investitsiya v rost!", {"rec": rec})
    _log_audit(f"Spend {amount} on {sink} from {account}")
    return {"ok": True, "accounts": st["accounts"]}

def convert_currency(amount: float, from_cur: str, to_cur: str) -> float:
    if from_cur == to_cur: return amount
    key = f"{from_cur}:{to_cur}"
    rate = CUR_RATES.get(key, 1.0)
    return amount * rate

def get_balance_by(filter_by: str = "all") -> Dict[str, Any]:
    st = _load_state()
    if filter_by == "all": return {"ok": True, "balances": st["balances"]}
    # Filter example: asset=ESTER, cat=ingest, currency=EUR
    filtered = {k: v for k, v in st["balances"].items() if filter_by in k}
    return {"ok": True, "filtered": filtered}

def status() -> Dict[str, Any]:
    st = _load_state()
    return {"ok": True, "ab": AB, **st}

@bp_economy.route("/economy/status", methods=["GET"])
def economy_status():
    if not _check_rbac(["viewer", "operator", "admin"]): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    return jsonify(status())

@bp_economy.route("/economy/append", methods=["POST"])
def economy_append():
    d = request.get_json() or {}
    return jsonify(append(d.get("kind"), d.get("asset"), d.get("delta"), d.get("cat", ""), d.get("currency", "EUR"), d.get("note", ""), d.get("meta")))

@bp_economy.route("/economy/transfer", methods=["POST"])
def economy_transfer():
    d = request.get_json() or {}
    return jsonify(transfer(d.get("from_acc"), d.get("to_acc"), d.get("amount"), d.get("note", "")))

@bp_economy.route("/economy/reserve", methods=["POST"])
def economy_reserve():
    d = request.get_json() or {}
    return jsonify(reserve(d.get("account"), d.get("amount"), d.get("reason")))

@bp_economy.route("/economy/approve/<reserve_id>", methods=["POST"])
def economy_approve(reserve_id):
    return jsonify(approve(reserve_id))

@bp_economy.route("/economy/spend", methods=["POST"])
def economy_spend():
    d = request.get_json() or {}
    return jupytext(spend(d.get("account"), d.get("amount"), d.get("sink"), d.get("reserve_id"), d.get("currency", "EUR")))

@bp_economy.route("/economy/balance_by", methods=["GET"])
def economy_balance_by():
    filter_by = request.args.get("filter", "all")
    return jsonify(get_balance_by(filter_by))

@bp_economy.route("/economy/audit", methods=["GET"])
def economy_audit():
    if not _check_rbac(["admin"]): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]
        return jsonify({"ok": True, "audit": lines})
    except Exception:
        return jsonify({"ok": False, "error": "audit_read_failed"})

def register(app):
    app.register_blueprint(bp_economy)
    # Scheduler integration: add task for daily report
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("economy_report", {"cron": "@daily"}, "economy.report", {})
    except Exception:
        pass

# Dlya scheduler: custom action
def report(params: Dict[str, Any]) -> Dict[str, Any]:
    s = status()
    _passport("Daily economy report — Ester, vot tvoy byudzhet: davay planirovat vpered!", {"status": s})
# return {"ok": True, "reported": True}