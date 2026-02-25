# -*- coding: utf-8 -*-
"""tools/publish/github_publish.py - push “public-safe” kataloga v GitHub.

MOSTY:
- (Yavnyy) push_repo(workdir) — commit soderzhimoe i pushit v GITHUB_REPO/GITHUB_BRANCH.
- (Skrytyy #1) Ispolzuet prostoy `git` cherez subprocess (bez vneshnikh python-bibliotek).
- (Skrytyy #2) Offlayn-gotov: esli git/tokenov net — vernet podskazki vmesto padeniya.

ZEMNOY ABZATs:
Kak “finalnyy shag upakovki”: podpisali, polozhili v obschiy shkaf, otmetili kleymom vetki.

# c=a+b"""
from __future__ import annotations
import os, subprocess, time, shutil
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)

def push_repo(workdir: str) -> Dict[str, Any]:
    repo = os.getenv("GITHUB_REPO","")
    if not repo:
        return {"ok": False, "error": "GITHUB_REPO not set (format: owner/name)"}
    branch = os.getenv("GITHUB_BRANCH","public-safe")
    token = os.getenv("GITHUB_TOKEN","")
    author = os.getenv("GIT_AUTHOR_NAME","Ester")
    email = os.getenv("GIT_AUTHOR_EMAIL","ester@example.local")

    if not shutil.which("git"):
        return {"ok": False, "error": "git is not available in PATH"}

    _run(["git","init"], cwd=workdir)
    _run(["git","config","user.name", author], cwd=workdir)
    _run(["git","config","user.email", email], cwd=workdir)
    _run(["git","add","-A"], cwd=workdir)
    _run(["git","commit","-m", f"public export {int(time.time())}"], cwd=workdir)

    if token:
        remote = f"https://{token}:x-oauth-basic@github.com/{repo}.git"
    else:
        remote = f"https://github.com/{repo}.git"
    _run(["git","branch","-M", branch], cwd=workdir)
    _run(["git","remote","remove","origin"], cwd=workdir)
    _run(["git","remote","add","origin", remote], cwd=workdir)
    r = _run(["git","push","-u","origin", branch, "--force"], cwd=workdir)

    ok = (r.returncode == 0)
    return {"ok": ok, "branch": branch, "repo": repo, "stdout": r.stdout[-2000:]}
# c=a+b