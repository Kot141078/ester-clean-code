# -*- coding: utf-8 -*-
"""
scripts/bootstrap_env.py — lokalnyy «sborschik okruzheniya».

MOSTY:
- (Yavnyy) Proveryaet klyuchevye katalogi/fayly, sozdaet nedostayuschie (data/*, logs/*, state/*).
- (Skrytyy #1) Pechataet otchet po kritichnym ENV i podsvechivaet pustye.
- (Skrytyy #2) Ne tyanet seti/pakety — offlayn-gotovyy shag dlya Portable/Closed-Box.

ZEMNOY ABZATs:
Kak pered startom avto: proverili maslo/davlenie/dvorniki — mozhno ekhat.

# c=a+b
"""
from __future__ import annotations
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DIRS = [
    "data", "data/ui", "data/runtime", "data/backups", "data/mem", "data/policy", "data/cron",
    "data/garage", "data/portfolio", "logs", "state"
]

ENV_KEYS = [
    "HOST","PORT","APP_TITLE","ESTER_DEFAULT_USER","JWT_SECRET","JWT_SECRET_KEY",
    "OPENAI_API_KEY","GEMINI_API_KEY","XAI_API_KEY","MESSAGING_DB_PATH","LMSTUDIO_ENDPOINTS"
]

def main():
    created = []
    for d in DIRS:
        try:
            os.makedirs(d, exist_ok=True)
            created.append(d)
        except Exception:
            pass
    report = {}
    for k in ENV_KEYS:
        v = os.getenv(k, "")
        report[k] = {"present": bool(v.strip()), "value_preview": (v[:4] + "..." if v else "")}
    path = os.path.join("data", "bootstrap_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"dirs": created, "env": report}, f, ensure_ascii=False, indent=2)
    print(f"[bootstrap] ok, report: {path}")

if __name__ == "__main__":
    main()
# c=a+b