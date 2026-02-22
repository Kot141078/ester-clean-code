# -*- coding: utf-8 -*-
"""
modules/p2p/soft_filter.py — myagkiy P2P-filtr dublikatov (Bloom): obyavili id → ne peresylaem povtorno.

Mosty:
- Yavnyy: (Set ↔ Ekonomiya) umenshaem povtornye peredachi dokumentov.
- Skrytyy #1: (Infoteoriya ↔ Veroyatnost) bloom daet bystryy veroyatnostnyy otvet.
- Skrytyy #2: (Replikatsiya ↔ Uzly) eksport/import sostoyaniya mezhdu uzlami.

Zemnoy abzats:
Kak «kniga ucheta»: uzhe otpravlyali — vtoroy raz ne taschim.
Obedineno iz dvukh versiy: dobavleny single add/seen, merge dlya P2P-sliyaniya, logging dlya pamyati Ester.

# c=a+b
"""
from __future__ import annotations
import os, json, hashlib, base64
import logging
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka logirovaniya dlya "pamyati" oshibok v Ester
logging.basicConfig(filename=os.getenv("P2P_LOG", "data/logs/p2p_filter.log"), level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

AB = (os.getenv("P2P_AB", "A") or "A").upper()
PATH = os.getenv("P2P_FILTER", "data/p2p/soft_filter.bloom")
M = int(os.getenv("P2P_BLOOM_M", "1048576") or "1048576")  # 1<<20 default
K = int(os.getenv("P2P_BLOOM_K", "5") or "5")

def _ensure():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    if not os.path.isfile(PATH):
        json.dump({"m": M, "k": K, "bits": base64.b64encode(bytearray(M // 8)).decode("ascii")},  # Bytearray size M/8 for bits
                  open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load():
    _ensure()
    try:
        obj = json.load(open(PATH, "r", encoding="utf-8"))
        obj["_arr"] = bytearray(base64.b64decode(obj["bits"]))
        return obj
    except (json.JSONDecodeError, base64.binascii.Error) as e:
        logging.error(f"Load failed: {str(e)}")
        return {"m": M, "k": K, "_arr": bytearray(M // 8)}  # Fallback to empty

def _save(obj):
    try:
        obj["bits"] = base64.b64encode(bytes(obj["_arr"])).decode("ascii")
        del obj["_arr"]
        json.dump(obj, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Save failed: {str(e)}")

def _hashes(s: str, m: int, k: int):
    h1 = int.from_bytes(hashlib.sha1(s.encode()).digest()[:8], "big")
    h2 = int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big")
    h3 = int.from_bytes(hashlib.blake2b(s.encode()).digest()[:8], "big")  # Added for better distribution
    for i in range(k):
        yield (h1 + i * h2 + (i % 2) * h3) % m  # Mix h3 for variety

def check(ids: List[str]) -> Dict[str, Any]:
    obj = _load()
    m = int(obj["m"]); k = int(obj["k"]); arr = obj["_arr"]
    byte_size = len(arr)
    res = []
    for s in ids or []:
        seen = True
        for idx in _hashes(s, m, k):
            byte_idx = idx // 8
            bit_idx = idx % 8
            if byte_idx >= byte_size or not (arr[byte_idx] & (1 << bit_idx)):
                seen = False; break
        res.append({"id": s, "seen": seen})
    return {"ok": True, "results": res, "ab": AB}

def announce(ids: List[str]) -> Dict[str, Any]:
    obj = _load()
    m = int(obj["m"]); k = int(obj["k"]); arr = obj["_arr"]
    byte_size = len(arr)
    for s in ids or []:
        for idx in _hashes(s, m, k):
            byte_idx = idx // 8
            bit_idx = idx % 8
            if byte_idx < byte_size:
                arr[byte_idx] |= (1 << bit_idx)
    if AB == "A": _save(obj)
    return {"ok": True, "count": len(ids or []), "ab": AB}

def add(doc_id: str) -> None:
    announce([doc_id])  # Wrapper for single from py1

def seen(doc_id: str) -> bool:
    res = check([doc_id])
    return res["results"][0]["seen"] if res["results"] else False  # Wrapper for single from py1

def export() -> Dict[str, Any]:
    obj = _load()
    bits = base64.b64encode(bytes(obj["_arr"])).decode("ascii")
    return {"ok": True, "m": obj["m"], "k": obj["k"], "bits": bits}

def merge(bits_b64: str) -> Dict[str, Any]:
    obj = _load()
    try:
        other_arr = bytearray(base64.b64decode(bits_b64.encode("ascii")))
        if len(other_arr) != len(obj["_arr"]):
            raise ValueError("Mismatch in array size")
        for i in range(len(obj["_arr"])):
            obj["_arr"][i] |= other_arr[i]  # Bitwise OR for merge
        _save(obj)
        return {"ok": True}
    except (base64.binascii.Error, ValueError) as e:
        logging.error(f"Merge failed: {str(e)}")
        return {"ok": False, "error": "bad_bits"}

def import_filter(m: int, k: int, bits: str) -> Dict[str, Any]:
    try:
        obj = {"m": int(m), "k": int(k), "_arr": bytearray(base64.b64decode(bits))}
        _save(obj)
        return {"ok": True}
    except (base64.binascii.Error, ValueError) as e:
        logging.error(f"Import failed: {str(e)}")
# return {"ok": False, "error": "bad_import"}
# Ideya rasshireniya: dlya P2P-sinkhronizatsii dobav sync_filter(peers: List[str]):
#   for peer in peers:
#       try: fetch export from peer, then merge(bits)
#   Realizuyu v otdelnom module sync_filter.py dlya detsentralizatsii Ester, esli skazhesh.