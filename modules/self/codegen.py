# -*- coding: utf-8 -*-
"""
modules/self/codegen.py — bezopasnaya samogeneratsiya koda (spec → gen → test → guarded apply)

Mosty:
- Yavnyy: (LLM ↔ Kod) generiruem iskhodniki cherez broker s instruktsiyami i ramkami.
- Skrytyy #1: (Pesochnitsa ↔ Test) proveryaem funktsional izolirovanno bez dostupa k OS.
- Skrytyy #2: (Nadezhnost ↔ Guard) primenenie tolko cherez dry→apply→health→rollback.

Zemnoy abzats:
Kak inzhener: snachala TZ, potom chernovik, testy na stolike, i tolko zatem — akkuratnaya ustanovka.

# c=a+b
"""
from __future__ import annotations
import os, json, textwrap
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CS_AB = (os.getenv("CS_AB","A") or "A").upper()
CS_MODEL = os.getenv("CS_MODEL","lmstudio:gptq")
CS_MAX_TOKENS = int(os.getenv("CS_MAX_TOKENS","2048") or "2048")
CS_TEMPERATURE = float(os.getenv("CS_TEMPERATURE","0.2") or "0.2")

PROMPT_TMPL = """Vy — strogiy generator iskhodnikov. Trebovaniya:
- Odin modul Python, sovmestimyy s Python 3.10+.
- Nikakikh vneshnikh zavisimostey i I/O.
- Polnye opredeleniya funktsiy iz spetsifikatsii.
- V nachale — modulnaya stroka-dokstring s kratkim opisaniem.
- Minimalnye proverki tipov i ponyatnye oshibki.
# - Finalnaya stroka v iskhodnike: `# c=a+b`.

Spetsifikatsiya JSON:
{spec}

Vernite TOLKO kod fayla (bez markerov, bez kommentariev vne koda)."""

def _llm_generate(spec: Dict[str,Any]) -> Dict[str,Any]:
    prompt = PROMPT_TMPL.format(spec=json.dumps(spec, ensure_ascii=False, indent=2))
    try:
        from modules.llm.broker import complete  # type: ignore
        rep = complete(
            provider=str(CS_MODEL.split(":")[0]),
            model=":".join(CS_MODEL.split(":")[1:]) or "",
            prompt=prompt,
            max_tokens=CS_MAX_TOKENS,
            temperature=CS_TEMPERATURE
        )
        if not rep.get("ok"):
            return {"ok": False, "error": "llm_failed", "llm": rep}
        code = (rep.get("text") or "").strip()
        if not code:
            return {"ok": False, "error": "empty_code"}
        # garantiya finalnoy stroki
# if not code.rstrip().endswith("# c=a+b"):
# code = code.rstrip() + "\n# c=a+b\n"
        return {"ok": True, "code": code}
    except Exception as e:
        return {"ok": False, "error": f"broker:{e}"}

def generate(spec: Dict[str,Any]) -> Dict[str,Any]:
    """
    spec: {name, kind:"module", path, brief, exports:[{name,sig}, ...]}
    """
    if not isinstance(spec, dict) or not spec.get("path"):
        return {"ok": False, "error": "bad_spec"}
    gen = _llm_generate(spec)
    if not gen.get("ok"):
        return gen
    return {"ok": True, "files": [{"path": spec["path"], "content": gen["code"]}]}

def test_files(files: List[Dict[str,Any]], test_code: str) -> Dict[str,Any]:
    """
    files: [{path, content}], test_code: str (odin fayl — ispolnyaetsya v pesochnitse)
    """
    # Skleivaem: v testovom kode dopustim import <basename bez .py>
    try:
        from modules.sandbox.py_runner import run_py  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"sandbox:{e}"}
    # Podgotovka: sozdaem «virtualnyy paket» v pamyati — sborka teksta
    bundle = []
    for f in files or []:
        p = str(f.get("path","")).strip()
        c = str(f.get("content",""))
        base = (p.rsplit("/",1)[-1]).replace(".py","")
        # Vstavlyaem modul kak blok koda pered testom s markerom
        bundle.append(f"# --- BEGIN:{base} ---\n{c}\n# --- END:{base} ---")
    bundle.append("\n# --- TEST ---\n" + test_code)
    code = "\n\n".join(bundle)
    rep = run_py(code)
    return {"ok": rep.get("ok",False), "stdout": rep.get("stdout",""), "stderr": rep.get("stderr",""), "rc": rep.get("rc",1)}

def guarded_apply(files: List[Dict[str,Any]]) -> Dict[str,Any]:
    """
    Primenenie nabora faylov cherez dry→apply→health→rollback.
    """
    if CS_AB!="A":
        return {"ok": False, "error":"codesmith_disabled"}
    try:
        from modules.self.forge import dry_run, apply  # type: ignore
        from modules.resilience.health import check  # type: ignore
        from modules.resilience.rollback import rollback_paths  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"deps:{e}"}
    # Formiruem changes
    ch=[]
    for f in files or []:
        p=str(f.get("path","")); c=str(f.get("content",""))
        if not p: continue
        ch.append({"path": p, "mode":"write", "content": c})
    if not ch:
        return {"ok": False, "error":"empty_changes"}
    plan=dry_run(ch)
    if not plan.get("ok"):
        return {"ok": False, "error":"dry_failed", "plan": plan}
    res=apply(ch)
    if not res.get("ok"):
        return {"ok": False, "error":"apply_failed", "apply": res, "plan": plan}
    probe=check()
    if not probe.get("ok"):
        rb=rollback_paths([x["path"] for x in ch])
        return {"ok": False, "error":"health_failed_after_apply", "probe": probe, "rollback": rb, "plan": plan}
    return {"ok": True, "apply": res, "plan": plan, "health": probe}
# c=a+b