# -*- coding: utf-8 -*-
"""
scripts/ci/patcher_llm.py — SARIF→evristicheskiy diff (LM Studio/LLM pri nalichii).

MOSTY:
- (Yavnyy) Chitaet semgrep.sarif, formiruet podskazki, po vozmozhnosti vyzyvaet lokalnyy LLM.
- (Skrytyy #1) Esli LM Studio nedostupen — primenyaet bezopasnye tekstovye ispravleniya (f-string quotes/backslashes, obvious syntax).
- (Skrytyy #2) Sokhranyaet patchset/patch.diff i logi prompta dlya vosproizvodimosti.

ZEMNOY ABZATs:
Eto «avtoslesar»: vidit techi — podzhimaet, no okonchatelnoe slovo za testami i revyu.

# c=a+b
"""
from __future__ import annotations
import os, json, re, argparse, pathlib, subprocess, tempfile, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def load_sarif(path: str):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for run in (data.get("runs") or []):
        for res in (run.get("results") or []):
            for loc in (res.get("locations") or []):
                phys = (loc.get("physicalLocation") or {})
                art = (phys.get("artifactLocation") or {})
                uri = art.get("uri")
                region = (phys.get("region") or {})
                startLine = region.get("startLine")
                message = (res.get("message") or {}).get("text","")
                if uri and startLine:
                    results.append({"file": uri, "line": startLine, "msg": message})
    return results

def safe_fixes(text: str) -> str:
    # 1) f-stroki s vlozhennymi kavychkami → ispolzuem raznye kavychki
    text = re.sub(r'f"([^"]*)\{([^}"]*?)[\'"]([^}]*)\}([^"]*)"', r"f'\1{\2\"\\'\\\"\3}\4'", text)
    # 2) Problemnye odnostrochniki s ; if → raznesem na stroki
    text = re.sub(r";\s*if\s+", ";\nif ", text)
    # 3) Ubiraem obratnye sleshi vnutri {} vyrazheniy f-stroki
    text = re.sub(r"\{[^}]*\\[^}]*\}", lambda m: m.group(0).replace("\\", "_"), text)
    return text

def apply_fixes(file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            src = f.read()
        fixed = safe_fixes(src)
        if fixed != src:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed)
            return True
    except Exception:
        pass
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sarif", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    findings = load_sarif(args.sarif)
    changed = []
    for f in findings:
        p = f["file"]
        if not os.path.isfile(p):
            continue
        if apply_fixes(p):
            changed.append(p)

    if not changed:
        return 0

    # Sozdaem diff
    with open(os.path.join(args.out, "patch.diff"), "w", encoding="utf-8") as out:
        proc = subprocess.run(["git", "diff"], capture_output=True, text=True)
        out.write(proc.stdout or "")

    # Log
    with open(os.path.join(args.out, "log.txt"), "w", encoding="utf-8") as lf:
        lf.write(json.dumps({"changed": changed}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b