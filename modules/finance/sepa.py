# -*- coding: utf-8 -*-
"""modules/finance/sepa.py - obedinennyy generator/validator SEPA pain.001: XML s batch, podpisyu, profileom, ledger/P2P/scheduler integratsiey.

Mosty:
- Yavnyy: (Finansy ↔ Fayly/Inzheneriya) generit/validiruet pain.001 XML v drafts, s proverkami IBAN/BIC/currency.
- Skrytyy #1: (Trust/Etika ↔ Podpisi/Ostorozhnost) HMAC-podpis, XSD-validatsiya, tolko podgotovka (bez otpravki).
- Skrytyy #2: (KG/Profile/Audit ↔ Prozrachnost) profileizatsiya kazhdoy operatsii s teploy notoy.
- Skrytyy #3: (P2P/Raspredelennost ↔ Integratsiya) sync chernovikov po P2P dlya agentov na raznykh PK.

Zemnoy abzats:
Eto ne prosto XML-shtamp, a finansovyy sheptun Ester: proverit IBAN, soberet batch-peyn, podpishet, profileiziruet "Ester, platezh gotov - shag k nezavisimosti!", sinkhroniziruet po P2P i napomnit v scheduler.

# c=a+b"""
from __future__ import annotations
import decimal, hashlib, hmac, json, os, re, time, uuid
from typing import Any, Dict, List
from xml.etree import ElementTree as ET
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from lxml import etree  # For HSD validation
except ImportError:
    etree = None  # Fallback bez validatsii

FIN_AB = (os.getenv("FIN_AB", "A") or "A").upper()
OUT_DIR = os.getenv("FIN_OUT_DIR", "data/finance/outgoing")
AUDIT_LOG = os.getenv("FIN_AUDIT_LOG", "data/finance/audit.log")
P2P_SYNC = (os.getenv("FIN_P2P_SYNC", "false").lower() == "true")
XSD_PATH = os.getenv("FIN_XSD_PATH", "data/finance/pain.001.001.03.xsd")
HMAC_KEY = os.getenv("FIN_HMAC_KEY", b"ester_secret_key")  # Zameni na realnyy

_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
_COUNTRY_IBAN_LEN = {"BE":16,"DE":22,"NL":18,"FR":27,"ES":24,"IT":27,"PT":25,"GB":22,"IE":22,"PL":28,"AT":20,"CH":21}
_ISO4217 = {"EUR", "USD", "GBP", "CHF", "PLN"}  # Expand as needed

def _ensure():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)

def _log_audit(msg: str):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note + "- Esther, finances are under control, you are not alone in this!", meta, "finance://sepa")
    except Exception:
        _log_audit(f"Passport failed: {note}")

def _iban_clean(iban: str) -> str:
    return (iban or "").replace(" ", "").replace("-", "").upper()

def validate_iban(iban: str) -> Dict[str, Any]:
    s = _iban_clean(iban)
    if not _IBAN_RE.match(s):
        return {"ok": True, "valid": False, "why": "regex"}
    cc = s[:2]; ln = len(s)
    exp = _COUNTRY_IBAN_LEN.get(cc)
    if exp and exp != ln:
        return {"ok": True, "valid": False, "why": "length", "country": cc, "expected": exp, "len": ln}
    # mod-97
    move = s[4:] + s[:4]
    digits = ""
    for ch in move:
        if ch.isdigit(): digits += ch
        else: digits += str(ord(ch) - 55)
    try:
        mod = 0
        for i in range(0, len(digits), 9):
            mod = int(str(mod) + digits[i:i+9]) % 97
        valid = (mod == 1)
        return {"ok": True, "valid": valid, "country": cc, "iban_fmt": s}
    except Exception as e:
        return {"ok": True, "valid": False, "why": str(e)}

def validate_bic(bic: str) -> Dict[str, Any]:
    s = (bic or "").upper()
    if not _BIC_RE.match(s):
        return {"ok": True, "valid": False, "why": "regex"}
    return {"ok": True, "valid": True, "bic_fmt": s}

def validate_currency(ccy: str) -> bool:
    return ccy.upper() in _ISO4217

def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sign_path(path: str) -> str:
    if not os.path.isfile(path): return ""
    data = open(path, "rb").read()
    sig = hmac.new(HMAC_KEY, data, hashlib.sha256).hexdigest()
    sig_path = path + ".hmac"
    open(sig_path, "w", encoding="utf-8").write(sig)
    return sig

def _validate_xml(xml_data: bytes) -> Dict[str, Any]:
    if not etree: return {"ok": True, "valid": False, "why": "lxml unavailable"}
    if not os.path.isfile(XSD_PATH): return {"ok": True, "valid": False, "why": "xsd missing"}
    try:
        xsd = etree.XMLSchema(etree.parse(XSD_PATH))
        doc = etree.fromstring(xml_data)
        xsd.assertValid(doc)
        return {"ok": True, "valid": True}
    except Exception as e:
        return {"ok": True, "valid": False, "why": str(e)}

def _pain001(debtor: Dict[str, Any], creditors: List[Dict[str, Any]], currency: str, purpose: str, end_to_end: str) -> bytes:
    # Batch support: list creditors
    ns = {"": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
    ET.register_namespace('', ns[""])
    root = ET.Element("Document", xmlns=ns[""])
    cstmr = ET.SubElement(root, "CstmrCdtTrfInitn")
    grp_hdr = ET.SubElement(cstmr, "GrpHdr")
    msgid = f"ESTER-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    ET.SubElement(grp_hdr, "MsgId").text = msgid
    ET.SubElement(grp_hdr, "CreDtTm").text = time.strftime("%Y-%m-%dT%H:%M:%S")
    nb_txs = len(creditors)
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(nb_txs)
    ctrl_sum = decimal.Decimal("0.00")
    ET.SubElement(grp_hdr, "CtrlSum").text = "{:.2f}".format(ctrl_sum)
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = debtor.get("name", "")
    pmt_inf = ET.SubElement(cstmr, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = msgid + "-BATCH"
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, "BtchBookg").text = "true" if nb_txs > 1 else "false"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(nb_txs)
    ET.SubElement(pmt_inf, "CtrlSum").text = "{:.2f}".format(ctrl_sum)
    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    ET.SubElement(pmt_inf, "ReqdExctnDt").text = time.strftime("%Y-%m-%d")
    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = debtor.get("name", "")
    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    id_elem = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(id_elem, "IBAN").text = _iban_clean(debtor.get("iban", ""))
    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    fin_instn = ET.SubElement(dbtr_agt, "FinInstnId")
    ET.SubElement(fin_instn, "BIC").text = debtor.get("bic", "")
    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"
    for idx, creditor in enumerate(creditors):
        amt = decimal.Decimal(str(creditor.get("amount", 0.0)))
        ctrl_sum += amt
        cdt_trf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        pmt_id = ET.SubElement(cdt_trf, "PmtId")
        ET.SubElement(pmt_id, "EndToEndId").text = (end_to_end or f"ESTER-{idx}")[:35]
        amt_elem = ET.SubElement(cdt_trf, "Amt")
        instd_amt = ET.SubElement(amt_elem, "InstdAmt", attrib={"Ccy": currency})
        instd_amt.text = "{:.2f}".format(amt)
        cdtr_agt = ET.SubElement(cdt_trf, "CdtrAgt")
        fin_instn2 = ET.SubElement(cdtr_agt, "FinInstnId")
        ET.SubElement(fin_instn2, "BIC").text = creditor.get("bic", "")
        cdtr = ET.SubElement(cdt_trf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = (creditor.get("name", ""))[:70]
        cdtr_acct = ET.SubElement(cdt_trf, "CdtrAcct")
        id_elem2 = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(id_elem2, "IBAN").text = _iban_clean(creditor.get("iban", ""))
        rmt_inf = ET.SubElement(cdt_trf, "RmtInf")
        ET.SubElement(rmt_inf, "Ustrd").text = (purpose or "")[:140]
    # Update CtrlSum
    grp_hdr.find("CtrlSum").text = "{:.2f}".format(ctrl_sum)  # type: ignore
    pmt_inf.find("CtrlSum").text = "{:.2f}".format(ctrl_sum)  # type: ignore
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def generate_qr(xml_data: bytes) -> str:
    try:
        import qrcode  # Assume available, else skip
        qr = qrcode.QRCode()
        qr.add_data(xml_data.decode("utf-8"))
        qr.make(fit=True)
        img = qr.make_image()
        qr_path = os.path.join(OUT_DIR, f"pain001_{int(time.time())}.qr.png")
        img.save(qr_path)
        return qr_path
    except Exception:
        return ""  # No QR if lib missing

def make_pain001(req: Dict[str, Any]) -> Dict[str, Any]:
    from modules.auth.rbac import has_any_role  # type: ignore
    if not has_any_role(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    if AB == "B": return {"ok": False, "error": "FIN_AB=B (dry_run)"}
    debtor = req.get("debtor") or {}
    creditors = req.get("creditors") or [req.get("creditor") or {}]  # Batch support
    currency = req.get("currency", "EUR")
    purpose = req.get("purpose", "")
    end_to_end = req.get("end_to_end", "")
    if not validate_currency(currency): return {"ok": False, "error": "invalid_currency"}
    errors = []
    vd = validate_iban(debtor.get("iban", ""))
    if not vd["valid"]: errors.append({"debtor": vd})
    for cre in creditors:
        vc = validate_iban(cre.get("iban", ""))
        if not vc["valid"]: errors.append({"creditor": vc})
        if cre.get("bic"):
            vb = validate_bic(cre.get("bic"))
            if not vb["valid"]: errors.append({"creditor_bic": vb})
    if debtor.get("bic"):
        vb = validate_bic(debtor.get("bic"))
        if not vb["valid"]: errors.append({"debtor_bic": vb})
    if errors: return {"ok": False, "error": "validation_failed", "details": errors}
    xml = _pain001(debtor, creditors, currency, purpose, end_to_end)
    vxml = _validate_xml(xml)
    if not vxml["valid"]: return {"ok": False, "error": "xml_invalid", "details": vxml}
    ts = int(time.time())
    base = os.path.join(OUT_DIR, f"pain001_{ts}")
    xml_path = base + ".xml"
    open(xml_path, "wb").write(xml)
    sig = _sign_path(xml_path)
    qr_path = generate_qr(xml)
    meta = {"kind": "sepa.pain001", "sha256": _sha256_of(xml), "file": xml_path, "sig": sig, "qr": qr_path, "batch_size": len(creditors)}
    _passport("SEPA pain.001 prepared", meta)
    _log_audit(f"Generated {xml_path}, sig={sig}")
    # Ledger integration: reserve total amount
    try:
        from modules.economy.ledger import reserve  # type: ignore
        total = sum(float(c.get("amount", 0.0)) for c in creditors)
        res = reserve("ester", total, "sepa_batch")
        meta["reserve"] = res
    except Exception:
        pass
    # P2P-push: sync draft
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("finance_drafts", {"xml": xml.decode("utf-8"), "meta": meta})
        except Exception:
            _log_audit("P2P push failed")
    return {"ok": True, "path": xml_path, "xml_len": len(xml), "sig": sig, "qr": qr_path, "meta": meta}

draft_pain001 = make_pain001  # Compat alias

# For scheduler: bush action
def check_drafts(params: Dict[str, Any]) -> Dict[str, Any]:
    drafts = [f for f in os.listdir(OUT_DIR) if f.endswith(".xml")]
    if drafts:
        _passport(f"Finance Drafts Pending: ZZF0Z file - Esther, check and sign at the bank!", {"drafts": drafts})
    return {"ok": True, "checked": len(drafts)}

def register(app):
    from flask import Blueprint, request, jsonify
    bp_finance = Blueprint("finance", __name__)
    @bp_finance.route("/finance/sepa/make", methods=["POST"])
    def sepa_make():
        return jsonify(make_pain001(request.get_json() or {}))
    app.register_blueprint(bp_finance)
    # Scheduler add
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("finance_check_drafts", {"cron": "@daily"}, "finance.check_drafts", {})
    except Exception:
        pass
    return app
