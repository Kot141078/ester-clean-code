# -*- coding: utf-8 -*-
"""modules/agents/desktop_vision.py - zrenie rabochego stola (yakorya UI, poisk, “navedi-klikni”).

Vozmozhnosti:
- Register yakorey (anchors): imya → {roi?, template_path?} v JSON-fayle.
- Poisk yakorya na screenshote: esli Pillow dostupen - prostoe sopostavlenie shablona (SSD);
  inache - evristika po ROI ili vozvraschaem “ne naydeno” bez oshibok.
- Postprotsess: tsentr boksa, otchet, trassirovka v pamyat.

Formatyyakorey:
  {
    "name": "ok_button",
    "roi": [x,y,w,h],            # optsionalno: ozhidaemaya oblast
    "template": "data/img/ok.png" # optsionalno: shablon
  }

MOSTY:
- Yavnyy: (Drayver OS ↔ Zrenie) — shagi {capture→find→click} stanovyatsya obyasnimymi.
- Skrytyy #1: (Infoteoriya ↔ Robastnost) — ROI i shablony snizhayut entropiyu poiska.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) - dry-run po umolchaniyu, prozrachnyy otchet.

ZEMNOY ABZATs:
Inzhenerno - “raskroy” skrinshota, naydi “anchor”, verni koordinatu tsentra i doverie.
Prakticheski - Ester mozhet “uvidet knopku” i natselit deystvie (klik) s poyasneniem.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_ANCHORS_PATH = os.environ.get("ESTER_DV_ANCHORS","rules/desktop_anchors.json")
_DV_ENABLED = os.environ.get("ESTER_DV_ENABLED","1") == "1"

try:
    from PIL import Image  # type: ignore
    _PIL=True
except Exception:
    _PIL=False

def _load_json(path:str)->Any:
    if not os.path.exists(path): return None
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        return None

def _save_json(path:str, obj:Any)->None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def anchors_list()->Dict[str,Any]:
    obj=_load_json(_ANCHORS_PATH) or {"anchors":[]}
    return {"ok":True,"path":_ANCHORS_PATH,"anchors":obj.get("anchors",[])}

def anchors_add(name:str, roi:List[int]|None=None, template_path:str|None=None)->Dict[str,Any]:
    j=_load_json(_ANCHORS_PATH) or {"anchors":[]}
    if any(a.get("name")==name for a in j["anchors"]):
        return {"ok":True,"exists":True,"path":_ANCHORS_PATH}
    rec={"name":name}
    if roi: rec["roi"]=[int(x) for x in roi]
    if template_path: rec["template"]=template_path
    j["anchors"].append(rec)
    _save_json(_ANCHORS_PATH, j)
    return {"ok":True,"path":_ANCHORS_PATH,"anchor":rec}

def anchors_remove(name:str)->Dict[str,Any]:
    j=_load_json(_ANCHORS_PATH) or {"anchors":[]}
    j["anchors"]=[a for a in j["anchors"] if a.get("name")!=name]
    _save_json(_ANCHORS_PATH, j)
    return {"ok":True}

def _ssd_score(img, tpl, x0, y0)->float:
    # simple sum of squared differences (no normalization)
    w,h=tpl.size
    if x0+w>img.size[0] or y0+h>img.size[1]: return float("inf")
    patch=img.crop((x0,y0,x0+w,y0+h))
    # uskorim do L (grayscale)
    patch=patch.convert("L"); tpl=tpl.convert("L")
    p=patch.tobytes(); t=tpl.tobytes()
    # SSD as the sum (puisch-tyusch)^2
    s=0
    for a,b in zip(p,t):
        d=(a-b); s+=d*d
    return float(s)

def _find_template(img, tpl)->Tuple[int,int,float]:
    best=(0,0,float("inf"))
    step=max(1, min(img.size)//200)  # a rough step so as not to “burn the CNC”; stability > accuracy
    W,H=img.size; w,h=tpl.size
    for y in range(0, H-h, step):
        for x in range(0, W-w, step):
            s=_ssd_score(img, tpl, x, y)
            if s<best[2]:
                best=(x,y,s)
    x,y,score=best
    conf=0.0 if score==float("inf") else max(0.0, min(1.0, 1.0/(1.0+score/(255.0*255.0*w*h))))
    return x+w//2, y+h//2, conf

def detect(image_path:str, anchor_name:str)->Dict[str,Any]:
    if not _DV_ENABLED:
        return {"ok":False,"error":"disabled_by_env"}
    A=anchors_list().get("anchors",[])
    rec=next((a for a in A if a.get("name")==anchor_name), None)
    if not rec:
        return {"ok":False,"error":"anchor_not_found"}
    if not os.path.exists(image_path):
        return {"ok":False,"error":"image_not_found","path":image_path}

    # mode without SAW - give ROY if specified, otherwise file-safe
    if not _PIL:
        if rec.get("roi"):
            x,y,w,h = rec["roi"]
            return {"ok":True,"anchor":anchor_name,"point":[x+w//2,y+h//2],"box":[x,y,w,h],"confidence":0.5,"engine":"roi"}
        return {"ok":False,"error":"no_engine_no_roi"}

    img=Image.open(image_path).convert("RGB")
    box=None; center=None; conf=0.0

    # 1) if SWARM is specified, cut out the search area
    if rec.get("roi"):
        x,y,w,h = rec["roi"]
        x=max(0,x); y=max(0,y); w=max(1,w); h=max(1,h)
        sx,sy,ex,ey = x,y,x+w,y+h
        crop = img.crop((sx,sy,ex,ey))
    else:
        sx,sy=0,0
        crop=img

    # 2) if a template is specified, search for a match
    if rec.get("template") and os.path.exists(rec["template"]):
        tpl=Image.open(rec["template"]).convert("RGB")
        cx,cy,conf=_find_template(crop, tpl)
        center=[sx+cx, sy+cy]
        box=[center[0]-tpl.size[0]//2, center[1]-tpl.size[1]//2, tpl.size[0], tpl.size[1]]
        engine="template"
    else:
        # false: if only ROY, take the center of ROY
        if rec.get("roi"):
            x,y,w,h = rec["roi"]
            center=[x+w//2, y+h//2]; box=[x,y,w,h]; conf=0.42; engine="roi"
        else:
            return {"ok":False,"error":"no_template_no_roi"}

    return {"ok":True,"anchor":anchor_name,"point":center,"box":box,"confidence":round(float(conf),3),"engine":engine}

def probe()->Dict[str,Any]:
    return {"ok":True,"enabled":_DV_ENABLED,"anchors_path":_ANCHORS_PATH,"pil":_PIL}

def add_sample()->Dict[str,Any]:
    # add training anchor (ROY for the “center” of the screen approximately)
    anchors_add("ok_button", roi=[100,100,160,60], template_path=None)
    return {"ok":True,"added":"ok_button"}