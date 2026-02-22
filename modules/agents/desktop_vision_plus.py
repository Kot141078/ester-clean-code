# -*- coding: utf-8 -*-
"""
modules/agents/desktop_vision_plus.py — OCR/annotatsii/teplokarty.

Vozmozhnosti:
- OCR (esli dostupny Pillow+pytesseract), inache graceful-degradation: vozvraschaem pustoy spisok bez oshibki.
- Poisk teksta: klyuchevye slova/regulyarki, blizhayshiy boks, tsentr → koordinata klika.
- Annotatsiya: risuem boksy/podsvetku i sokhranyaem fayl (PNG) v ESTER_DVPP_OUTDIR.
- Teplokarta: grubaya setka uverennosti po sovpadeniyam (bez heavy-CV).

MOSTY:
- Yavnyy: (Zrenie ↔ Drayver OS) — «klik po tekstu» s dokazatelstvom (annotirovannyy kadr).
- Skrytyy #1: (Infoteoriya ↔ Obyasnimost) — OCR-sloi/tsitaty na kadre ↓ entropiya nedoveriya.
- Skrytyy #2: (Kibernetika ↔ Nadezhnost) — ostavlyaem «sled» kadra v zhurnale pamyati.

ZEMNOY ABZATs:
Inzhenerno — izvlechenie teksta s koordinatami i prostaya vizualizatsiya; praktichno — «nazhmi na knopku, gde napisano OK», s sokhranennym kadrom do/posle kak dokazatelstvom.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, time, re, json, math, random
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUTDIR = os.environ.get("ESTER_DVPP_OUTDIR","/tmp")
LANGS  = os.environ.get("ESTER_DVPP_LANG","eng+rus")
ENABLED= os.environ.get("ESTER_DVPP_ENABLED","1") == "1"

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    _PIL=True
except Exception:
    _PIL=False

try:
    import pytesseract  # type: ignore
    _TESS=True
except Exception:
    _TESS=False

def probe()->Dict[str,Any]:
    return {"ok":True,"enabled":ENABLED,"pil":_PIL,"tesseract":_TESS,"outdir":OUTDIR,"langs":LANGS}

def _ocr_boxes(path:str)->List[Dict[str,Any]]:
    if not (ENABLED and _PIL and _TESS): return []
    img=Image.open(path)
    data=pytesseract.image_to_data(img, lang=LANGS, output_type='dict')  # type: ignore
    out=[]
    n=len(data.get("text",[]))
    for i in range(n):
        txt=data["text"][i] or ""
        if not txt.strip(): continue
        x,y,w,h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        conf=float(data.get("conf",[0]*n)[i] or 0.0)
        out.append({"text":txt, "box":[x,y,w,h], "conf": conf/100.0})
    return out

def ocr(path:str)->Dict[str,Any]:
    if not os.path.exists(path): return {"ok":False,"error":"image_not_found","path":path}
    boxes=_ocr_boxes(path)
    return {"ok":True,"items":boxes,"count":len(boxes)}

def _match_score(text:str, key:str)->float:
    t=text.strip().lower(); k=key.strip().lower()
    if not t or not k: return 0.0
    if t==k: return 1.0
    if k in t: return 0.7 + 0.3*(len(k)/max(1,len(t)))
    return 0.0

def find_text(path:str, key:str, regex:bool=False)->Dict[str,Any]:
    if not os.path.exists(path): return {"ok":False,"error":"image_not_found","path":path}
    boxes=_ocr_boxes(path)
    if not boxes:
        return {"ok":False,"error":"no_ocr_engine_or_empty"}

    best=None
    if regex:
        pat=re.compile(key, re.I)
        for b in boxes:
            if pat.search(b["text"] or ""):
                score=0.8 + 0.2*min(1.0,b.get("conf",0))
                if (best is None) or (score > best["score"]):
                    best={"text":b["text"],"box":b["box"],"score":score}
    else:
        for b in boxes:
            s=_match_score(b["text"], key) * (0.8 + 0.2*min(1.0,b.get("conf",0)))
            if s>0 and ((best is None) or (s>best["score"])):
                best={"text":b["text"],"box":b["box"],"score":s}

    if not best:
        return {"ok":False,"error":"text_not_found","key":key}

    x,y,w,h = best["box"]
    cx,cy = x+w//2, y+h//2
    return {"ok":True,"key":key,"text":best["text"],"point":[cx,cy],"box":[x,y,w,h],"confidence":round(best["score"],3)}

def _ensure_outdir()->None:
    try: os.makedirs(OUTDIR, exist_ok=True)
    except Exception: pass

def annotate(path:str, boxes:List[Dict[str,Any]], save_as:str|None=None, title:str="")->Dict[str,Any]:
    """
    boxes: [{"box":[x,y,w,h], "label":"...", "color":"auto"}]
    """
    if not _PIL: 
        # otdaem «virtualnuyu» annotatsiyu kak JSON
        return {"ok":True,"virtual":True,"items":boxes,"note":"Pillow not available"}
    img=Image.open(path).convert("RGB")
    dr=ImageDraw.Draw(img)
    for b in boxes:
        x,y,w,h = b["box"]
        dr.rectangle((x,y,x+w,y+h), outline=(255,0,0), width=2)
        if b.get("label"):
            dr.text((x,y-12), b["label"], fill=(255,255,0))
    _ensure_outdir()
    fn = save_as or os.path.join(OUTDIR, f"ester_annot_{int(time.time())}.png")
    img.save(fn)
    return {"ok":True,"path":fn}

def heatmap(path:str, hits:List[Tuple[int,int,float]])->Dict[str,Any]:
    """
    hits: [(x,y,confidence), ...] — risuem poluprozrachnye tochki.
    """
    if not _PIL:
        return {"ok":True,"virtual":True,"hits":hits}
    base=Image.open(path).convert("RGBA")
    overlay=Image.new("RGBA", base.size, (0,0,0,0))
    dr=ImageDraw.Draw(overlay)
    for x,y,c in hits:
        r=max(6, int(12*c))
        dr.ellipse((x-r,y-r,x+r,y+r), fill=(255,0,0,int(80+120*c)))
    out=Image.alpha_composite(base, overlay).convert("RGB")
    _ensure_outdir()
    fn=os.path.join(OUTDIR, f"ester_heat_{int(time.time())}.png")
    out.save(fn)
    return {"ok":True,"path":fn}

def find_text_and_annotate(path:str, key:str)->Dict[str,Any]:
    r=find_text(path, key, regex=False)
    if not r.get("ok"):
        return r
    box=r["box"]; x,y,w,h=box
    ann=annotate(path, [{"box":box,"label":f"{key} ({r['confidence']:.2f})"}])
    hm=heatmap(path, [(x+w//2,y+h//2, r["confidence"])])
    return {"ok":True,"click_point":r["point"], "box":box, "confidence":r["confidence"], "annot_path":ann.get("path"), "heatmap_path":hm.get("path")}