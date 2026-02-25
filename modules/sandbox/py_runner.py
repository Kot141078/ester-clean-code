# -*- coding: utf-8 -*-
"""modules/sandbox/py_runner.py - bezopasnyy izolirovannyy zapusk Python-skriptov v podprotsesse.

Mosty:
- Yavnyy: (Kod ↔ Test/Samorazvitie) universalnyy runner dlya guarded_apply, Fleet i CodeSmith+.
- Skrytyy #1: (Bezopasnost ↔ Ogranicheniya) taymaut, izolyatsiya (-I), proverka na banned, vremennaya papka bez setevykh vyzovov.
- Skrytyy #2: (Audit ↔ Prozrachnost) vozvraschaet stdout/stderr/rc/dt dlya loga i analiza.

Zemnoy abzats:
Kak kapsula dlya eksperimentov: kladem kod vnutr, zapuskaem izolirovanno, s taymerom i uborkoy - bystro, chisto i bez riska dlya osnovnoy sistemy Ester.

# c=a+b"""
from __future__ import annotations
import os, time, subprocess, uuid, tempfile, textwrap
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("SANDBOX_AB", "A") or "A").upper()
TMP = os.getenv("PY_RUNNER_TMP", "data/sandbox")
DEFAULT_TIMEOUT = int(os.getenv("SANDBOX_T_SEC", "10") or "10")

def _banned_check(code: str) -> str | None:
    """Checks for prohibited tokens (best-effort security)."""
    banned = (
        "import os", "import sys", "import subprocess",
        "open(", "socket", "requests", "urllib"
    )
    for b in banned:
        if b in code:
            return f"banned_token:{b}"
    return None

def run_py(code: str, timeout_sec: int = DEFAULT_TIMEOUT) -> Dict[str, any]:
    """Executes pothon code in an isolated subprocess(-I), with timeout and auditing.
    Returns ZZF0Z."""
    if AB != "A":
        return {"ok": False, "error": "sandbox_disabled"}
    
    code = textwrap.dedent(code or "")
    ban_err = _banned_check(code)
    if ban_err:
        return {"ok": False, "error": ban_err, "stdout": "", "stderr": "", "rc": 1, "dt": 0.0}
    
    os.makedirs(TMP, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TMP) as td:
        fn = os.path.join(td, f"run_{uuid.uuid4().hex[:8]}.py")
        with open(fn, "w", encoding="utf-8") as f:
            f.write(code)
        
        t0 = time.time()
        try:
            p = subprocess.Popen(
                ["python", "-I", fn],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = p.communicate(timeout=timeout_sec)
            rc = p.returncode
            ok = (rc == 0)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except Exception:
                pass
            out = ""; err = "timeout"
            ok = False; rc = 124
        except Exception as e:
            out = ""; err = str(e)
            ok = False; rc = 1
        
        dt = time.time() - t0
# return {"ok": ok, "stdout": out, "stderr": err, "rc": rc, "dt": dt}