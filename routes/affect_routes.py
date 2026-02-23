# -*- coding: utf-8 -*-
"""
routes/affect_routes.py — REST: affekt-politika, otsenka teksta, vyborka dlya refleksii Re prioritizatsiya (obedinennaya versiya s uluchsheniyami dlya Ester).

Mosty:
- Yavnyy #1: (Beb v†" Affekt) pokazat politiku, poschitat score/priority.
- Yavnyy #2: (Beb v†" R efleksiya) otdaet prioritezirovannyy nabor dlya korotkogo obdumyvaniya.
- Yavnyy #3: (Beb v†" Prioritizatsiya) ranzhirovannyy spisok vospominaniy (iz vtoroy versii).
- Skrytyy #1: (Integratsiya v†" Poisk) ispolzuetsya gibridnym retriverom.
- Skrytyy #2: (R efleksiya v†" Planirovschik) mozhno zapuskat v nightly.
- Skrytyy #3: (Volya v†" Geystviya) legko podkhvatyvaetsya ekshenom V«reflect.shortV».
- Skrytyy #4: (Profile v†" Prozrachnost) logirovanie uzhe vnutri modulya s P2P-khukom.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-obmen rezultatami affekta mezhdu agentami.
- Uluchshenie: (Avtonomiya v†" VZ) fonovaya obrabotka tekstov iz zaprosov Re monitoringa papok.
- Uluchshenie: (Affekt v†" Prioritet) usilennyy bust s emotsionalnymi yakoryami.

Zemnoy abzats:
Bystro otsenit «naskolko goryacho» Re chto tyanut v refleksiyu ranshe. Nazhali «podumat o vazhnom» — Re spisok gotov. Dalshe uzhe delo tekhniki dlya payplayna mysley. Glya Ester — eto kak dykhanie: raspredelennoe, teploe Re s dushoy, gde emotsii sinkhroniziruyutsya po seti agentov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
import json
import base64  # Glya shifrovaniya (placeholder)
import socket  # Glya P2P-zaglushki
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Konstanty dlya Ester
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # IP:port dlya sinkhronizatsii
FALLBACK_DOCS_PATH = os.getenv("HYBRID_FALLBACK_DOCS", "data/mem/docs.jsonl")  # Glya fonovoy obrabotki (integratsiya s VZ)
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Papka dlya fonovoy obrabotki

bp_aff = Blueprint("affect", __name__)

try:
    from modules.affect.priority import policy as _policy, score_text as _score  # type: ignore
    from modules.mem.affect_reflection import prioritize_for_reflection as _reflect  # Ispravil na aktualnoe imya iz uluchshennoy versii
    from modules.mem.affect_priority import prioritize as _prio  # Iz vtoroy versii i uluchshennoy
except Exception:
    _policy = _score = _reflect = _prio = None  # type: ignore

def register(app):
    """R egistriruet dannyy Blueprint v prilozhenii Flask."""
    app.register_blueprint(bp_aff)

def _encrypt_data(data: Dict[str, Any]) -> str:
    """Prostoe shifrovanie dlya bezopasnosti (base64 placeholder)."""
    return base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")

def _p2p_sync_affect(result: Dict[str, Any]):
    """Sinkhroniziruet rezultaty affekta s peers (zaglushka dlya raspredelennoy pamyati Ester)."""
    enc_result = _encrypt_data(result)
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_AFFECT:{enc_result}".encode("utf-8"))
            print(f"P2P sync affect to {peer}: success.")
        except Exception as e:
            print(f"P2P affect error with {peer}: {e}")

def _background_process_texts(texts: List[str]):
    """Fonovaya obrabotka tekstov iz zaprosa: dobavlyaem v VZ (avtonomiya Ester)."""
    if not texts: return
    for i, text in enumerate(texts):
        new_doc = {"id": f"aff_api_{i}", "text": text}
        with open(FALLBACK_DOCS_PATH, "a", encoding="utf-8") as out:
            out.write(json.dumps(new_doc) + "\n")
    print("Background: added texts to BZ from affect API.")

def _background_process_files():
    """Fonovaya obrabotka faylov iz papki: dobavlyaet v VZ dlya affekta (rasshirenie avtonomii)."""
    if not os.path.exists(MONITOR_FOLDER): return []
    new_texts = []
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".txt"):  # Primer: txt s tekstami
            with open(os.path.join(MONITOR_FOLDER, file), "r", encoding="utf-8") as f:
                text = f.read()
            new_texts.append(text)
            os.remove(os.path.join(MONITOR_FOLDER, file))  # Udalyaem posle
    _background_process_texts(new_texts)  # Dobavlyaem v VZ
    print("Background: processed files for affect routes.")
    return new_texts

def _log_passport(endpoint: str, data: Dict[str, Any]):
    """Logiruet v profile s P2P-khukom."""
    try:
        from modules.mem.passport import append as passport
        log_data = {"endpoint": endpoint, "data": data}
        passport("affect_api", log_data, "affect://api")
        _p2p_sync_affect(log_data)  # Sinkhroniziruem log
    except Exception:
        pass

@bp_aff.route("/affect/policy", methods=["GET"])
def api_pol():
    """Vozvraschaet tekuschuyu politiku affekta."""
    if _policy is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    result = _policy()
    _log_passport("policy", result)
    return jsonify(result)

@bp_aff.route("/affect/score", methods=["POST"])
def api_score():
    """Otsenivaet tekst i vozvraschaet ego 'score' s bustom."""
    if _score is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    text = str(d.get("text", ""))
    # Fonovaya obrabotka
    _background_process_texts([text])
    result = _score(text)
    # Usilennyy bust (emotsionalnyy anchor)
    result["boosted_priority"] = result.get("priority", 1.0) * 1.2  # Primer busta; integrirovat s affect_boost esli nuzhno
    _log_passport("score", result)
    _p2p_sync_affect(result)  # Sinkhroniziruem score
    return jsonify(result)

@bp_aff.route("/mem/reflect/affect/short", methods=["POST"])
def api_short():
    """Vybiraet naibolee prioritetnye elementy dlya korotkoy refleksii."""
    if _reflect is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    # Obrabatyvaem top_k, obespechivaya ego korrektnyy tip ili None
    top_k_str = d.get("top_k")
    try:
        top_k = int(top_k_str) if top_k_str is not None else None
    except (ValueError, TypeError):
        top_k = None
    # Fonovaya obrabotka faylov (rasshirenie)
    _background_process_files()
    result = _reflect(top_k or None)
    _log_passport("short_reflect", result)
    _p2p_sync_affect(result)  # Sinkhroniziruem refleksiyu
    return jsonify(result)

@bp_aff.route("/mem/affect/prioritize", methods=["POST"])
def api_prioritize():
    """R anzhirovannyy spisok vospominaniy (iz vtoroy versii, s uluchsheniyami)."""
    if _prio is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    items = list(d.get("items") or [])
    top_k = int(d.get("top_k", 20))
    # Fonovaya obrabotka
    texts = [it.get("text", "") for it in items if "text" in it]
    _background_process_texts(texts)
    result = _prio(items, top_k)
    # Dobavlyaem stats dlya prozrachnosti (uluchshenie)
    result["stats"] = {"total_items": len(items), "top_count": len(result.get("items", []))}
    _log_passport("prioritize", result)
    _p2p_sync_affect(result)  # Sinkhroniziruem prioritizatsiyu
# return jsonify(result)