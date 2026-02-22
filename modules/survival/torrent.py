# -*- coding: utf-8 -*-
"""
modules/survival/torrent.py — generator .torrent (bencode): single/multi-file, SHA1 pieces.

Mosty:
- Yavnyy: (Bandl ↔ P2P) prevraschaem arkhiv/direktoriyu v torrenty dlya samorasprostraneniya.
- Skrytyy #1: (Profile ↔ Prozrachnost) vypusk torrenta fiksiruetsya.
- Skrytyy #2: (P2P Bloom ↔ Set) kheshi faylov mozhno zaranee obyavit v bloom, chtoby ne dublirovat.

Zemnoy abzats:
Eto kak nakleit shtrikhkod i dobavit v razdachu: lyuboy uzel podtyanet to, chto nuzhno — bystro i bez tsentra.

# c=a+b
"""
from __future__ import annotations
import os, time, hashlib, math, json
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT_DIR=os.getenv("SURVIVAL_TORRENT_DIR","data/survival/torrents")
PIECE_LEN=int(os.getenv("SURVIVAL_PIECE_LEN","262144") or "262144")

def _ensure():
    os.makedirs(OUT_DIR, exist_ok=True)

def _bencode(x)->bytes:
    if isinstance(x, int):
        return b"i"+str(x).encode()+b"e"
    if isinstance(x, bytes):
        return str(len(x)).encode()+b":"+x
    if isinstance(x, str):
        s=x.encode("utf-8"); return str(len(s)).encode()+b":"+s
    if isinstance(x, list):
        return b"l"+b"".join(_bencode(i) for i in x)+b"e"
    if isinstance(x, dict):
        # klyuchi dolzhny byt bayty po alfavitu
        out=[]
        for k in sorted(x.keys(), key=lambda k: (k if isinstance(k, bytes) else str(k).encode())):
            kb=k if isinstance(k, bytes) else str(k).encode()
            out.append(_bencode(kb)+_bencode(x[k]))
        return b"d"+b"".join(out)+b"e"
    raise TypeError("bencode type")

def _sha1_file(path: str, piece_len: int)->bytes:
    pieces=[]
    with open(path,"rb") as f:
        while True:
            chunk=f.read(piece_len)
            if not chunk: break
            pieces.append(hashlib.sha1(chunk).digest())
    return b"".join(pieces)

def _walk(path: str)->List[Dict[str,Any]]:
    items=[]
    if os.path.isfile(path):
        items.append({"path": path, "rel": os.path.basename(path), "length": os.path.getsize(path)})
    else:
        base=path
        for root,_,names in os.walk(path):
            for n in names:
                fp=os.path.join(root,n)
                rel=os.path.relpath(fp, base)
                items.append({"path": fp, "rel": rel.replace("\\","/"), "length": os.path.getsize(fp)})
    return items

def create(path: str, trackers: List[str]|None=None)->Dict[str,Any]:
    _ensure()
    if not os.path.exists(path):
        return {"ok": False, "error":"not_found"}
    items=_walk(path)
    info={}
    if os.path.isfile(path) and len(items)==1:
        info={
            "name": os.path.basename(path),
            "length": items[0]["length"],
            "piece length": PIECE_LEN,
            "pieces": _sha1_file(path, PIECE_LEN)
        }
    else:
        # multi-file
        pieces=[]
        # dlya prostoty — skleivaem fayly posledovatelno v «virtualnyy potok»
        import io
        buf=io.BytesIO()
        for it in items:
            with open(it["path"],"rb") as f:
                while True:
                    b=f.read(1<<20)
                    if not b: break
                    buf.write(b)
        buf.seek(0)
        while True:
            chunk=buf.read(PIECE_LEN)
            if not chunk: break
            pieces.append(hashlib.sha1(chunk).digest())
        info={
            "name": os.path.basename(path.rstrip("/\\")),
            "files": [{"path":[p for p in it["rel"].split("/")], "length": it["length"]} for it in items],
            "piece length": PIECE_LEN,
            "pieces": b"".join(pieces)
        }
    metainfo={
        "announce": (trackers or ["udp://tracker.opentrackr.org:1337/announce"])[0],
        "creation date": int(time.time()),
        "info": info
    }
    # zapis .torrent
    base=os.path.basename(path)
    out=os.path.join(OUT_DIR, f"{base}.torrent")
    with open(out,"wb") as f:
        f.write(_bencode(metainfo))
    # profile
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("survival_torrent_create", {"target": base, "piece_len": PIECE_LEN}, "survival://torrent")
    except Exception:
        pass
    return {"ok": True, "path": out, "target": base}
# c=a+b