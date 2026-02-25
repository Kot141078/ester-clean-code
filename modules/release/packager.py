# -*- coding: utf-8 -*-
"""modules/release/packager.py - snepshot koda/dannykh (manifest + tar.gz) i generatsiya .torrent metadannykh.

Mosty:
- Yavnyy: (Replikatsiya ↔ Upakovka) gotovim vosproizvodimuyu sborku.
- Skrytyy #1: (Tselostnost ↔ Podpis) manifest podpisyvaetsya HMAC i mozhet byt proveren.
- Skrytyy #2: (Set ↔ Rasprostranenie).torrent - legalnyy kanal po opt-in (bez avto-sidinga).

Zemnoy abzats:
“Soberi chemodan” - upakovali sistemu, postavili pechat, pri zhelanii sozdali torrent dlya rasprostraneniya.

# c=a+b"""
from __future__ import annotations
import os, json, tarfile, hashlib, time, math
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT = os.getenv("RELEASE_DIR","data/releases")
PIECE_KB = int(os.getenv("TORRENT_PIECE_KB","256") or "256")

def _ensure():
    os.makedirs(OUT, exist_ok=True)

def _walk(paths: List[str]) -> List[str]:
    files=[]
    for r in paths or []:
        if os.path.isfile(r): files.append(r)
        elif os.path.isdir(r):
            for base,_,fs in os.walk(r):
                for fn in fs:
                    p=os.path.join(base,fn)
                    files.append(p)
    return files

def snapshot(roots: List[str], name: str = "ester") -> Dict[str,Any]:
    _ensure()
    ts=int(time.time())
    files=_walk(roots)
    man={"name": name, "ts": ts, "files": []}
    for p in files:
        try:
            man["files"].append({"path": p, "size": os.path.getsize(p), "sha256": hashlib.sha256(open(p,"rb").read()).hexdigest()})
        except Exception:
            continue
    man_path=os.path.join(OUT, f"{name}.{ts}.manifest.json")
    json.dump(man, open(man_path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    # podpis manifesta
    try:
        from modules.trust.sign import sign_path  # type: ignore
        sign_path(man_path)
    except Exception:
        pass
    # arkhiv
    tar_path=os.path.join(OUT, f"{name}.{ts}.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for p in files:
            try: tar.add(p)
            except Exception: pass
        tar.add(man_path, arcname=os.path.basename(man_path))
        if os.path.isfile(man_path + ".sig.json"):
            tar.add(man_path + ".sig.json", arcname=os.path.basename(man_path) + ".sig.json")
    return {"ok": True, "manifest": man_path, "archive": tar_path, "count": len(man["files"])}

# ---- .torrent (bencode) ----

def _bencode_int(i: int) -> bytes:
    return b"i" + str(int(i)).encode() + b"e"

def _bencode_bytes(b: bytes) -> bytes:
    return str(len(b)).encode() + b":" + b

def _bencode_str(s: str) -> bytes:
    return _bencode_bytes(s.encode("utf-8"))

def _bencode_list(lst: List[Any]) -> bytes:
    out=b"l"
    for it in lst:
        out += _bencode(it)
    return out + b"e"

def _bencode_dict(d: Dict[str,Any]) -> bytes:
    out=b"d"
    for k in sorted(d.keys()):
        out += _bencode_str(k)
        out += _bencode(d[k])
    return out + b"e"

def _bencode(x: Any) -> bytes:
    if isinstance(x, int): return _bencode_int(x)
    if isinstance(x, bytes): return _bencode_bytes(x)
    if isinstance(x, str): return _bencode_str(x)
    if isinstance(x, list): return _bencode_list(x)
    if isinstance(x, dict): return _bencode_dict(x)
    raise TypeError("bencode type")

def make_torrent(manifest_path: str, announce: List[str]) -> Dict[str,Any]:
    _ensure()
    man=json.load(open(manifest_path,"r",encoding="utf-8"))
    # sozdaem edinyy «payload» iz spiska faylov (multi-file)
    piece_len = PIECE_KB * 1024
    pieces=b""
    buf=b""
    total_len=0
    for f in man.get("files",[]):
        p=f["path"]
        try:
            data=open(p,"rb").read()
        except Exception:
            data=b""
        total_len += len(data)
        buf += data
        while len(buf) >= piece_len:
            pieces += hashlib.sha1(buf[:piece_len]).digest()
            buf = buf[piece_len:]
    if buf:
        pieces += hashlib.sha1(buf).digest()
        buf=b""
    info = {
        "name": man.get("name","ester"),
        "piece length": piece_len,
        "pieces": pieces,
        "files": [{"length": os.path.getsize(f["path"]) if os.path.exists(f["path"]) else 0,
                   "path": f["path"].split(os.sep)} for f in man.get("files",[])]
    }
    tor = {
        "announce": announce[0] if announce else "udp://tracker.opentrackr.org:1337/announce",
        "announce-list": [announce] if announce else [],
        "creation date": int(time.time()),
        "comment": "Ester release torrent (legal, opt-in)",
        "info": info
    }
    blob = _bencode(tor)
    path = manifest_path.replace(".manifest.json",".torrent")
    open(path,"wb").write(blob)
    return {"ok": True, "torrent": path, "piece_kb": PIECE_KB, "size_total": total_len}
# c=a+b