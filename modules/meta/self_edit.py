# -*- coding: utf-8 -*-
"""Self-Edit - bezopasnaya samoredaktura koda Ester s A/B-slotom, bekapom i avtokatbekom.

Mosty:
- Yavnyy: (Kodovaya baza ↔ QA) — dry-run diffy, proverka sintaksisa i validatsiya routov pered primeneniem.
- Skrytyy 1: (A/B ↔ Nadezhnost) - v slote A razreshen tolko prosmotr izmeneniy; slot B primenyaet, no s bekapom i avtokatbekom pri provale.
- Skrytyy 2: (Dokumentatsiya/Portal ↔ UX) — log pravok i statusy dostupny UI i khranyatsya v state.

Zemnoy abzats:
This is “umnaya ruchka-sterka”: snachala pokazyvaet, chto pomenyaet, i tolko v “smelom” rezhime deystvitelno pishet.
Esli chto-to poshlo ne tak - otkatyvaet i ostavlyaet zametku, chtoby rukami ne lovit bagi."""
from __future__ import annotations

import os, re, json, time, shutil, importlib.util, types, traceback
from pathlib import Path
from typing import Dict, Any, List, Tuple

from modules.meta.ab_warden import ab_switch, get_ab_mode
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
SE_DIR = STATE_DIR / "self_edit"
SE_DIR.mkdir(parents=True, exist_ok=True)
LOG = SE_DIR / "log.jsonl"
BACKUPS = SE_DIR / "backups"

ALLOWED_ROOTS = [Path.cwd() / "modules", Path.cwd() / "routes", Path.cwd() / "templates", Path.cwd() / "register_all.py", Path.cwd() / "tools"]

def _safe_path(p: str) -> Tuple[bool, Path, str]:
    """Path checking: inside allowed directories, without traversals."""
    raw = Path(p)
    if raw.is_absolute():
        return False, raw, "absolute_path_forbidden"
    pp = (Path.cwd() / raw).resolve()
    # razreshaem konkretnyy fayl register_all.py i vse pod modules/routes/templates/tools
    if (pp == Path.cwd() / "register_all.py") or any(str(pp).startswith(str(root.resolve())) for root in ALLOWED_ROOTS if isinstance(root, Path)):
        if pp.exists():
            return True, pp, "ok"
        else:
            # edit only existing files (without creating)
            return False, pp, "not_exists"
    return False, pp, "outside_allowed_roots"

def _unified_diff(a: str, b: str, path: str) -> str:
    import difflib
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    return "".join(difflib.unified_diff(a_lines, b_lines, fromfile=f"{path} (old)", tofile=f"{path} (new)"))

def _apply_regex(src: str, pattern: str, repl: str, multiple: bool) -> Tuple[str, int]:
    flags = re.DOTALL | re.MULTILINE
    if multiple:
        new, n = re.subn(pattern, repl, src, flags=flags)
        return new, n
    # odno zameschenie
    rx = re.compile(pattern, flags)
    match = rx.search(src)
    if not match:
        return src, 0
    return src[:match.start()] + rx.sub(repl, src, count=1), 1

def _log(entry: Dict[str, Any]) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _check_syntax(py_text: str, file_path: Path) -> Tuple[bool, str]:
    try:
        compile(py_text, str(file_path), "exec")
        return True, "ok"
    except Exception as e:
        return False, f"syntax_error:{type(e).__name__}:{e}"

def _run_verify_routes() -> Tuple[bool, str]:
    """We launch tools/verify_rutes.po as a module and returns a return code/message."""
    try:
        spec = importlib.util.find_spec("tools.verify_routes")
        if spec is None:
            return True, "no_verify_module"  # v otsutstvie lintera ne blokiruem
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(mod)  # type: ignore
        rc = mod.main()  # type: ignore
        return (rc == 0), f"verify_rc={rc}"
    except Exception as e:
        return False, f"verify_exception:{type(e).__name__}:{e}"

def dry_run(label: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Returns diffs without writing. Always allowed (A and B).
    Unit format: yuZF0Z, ...sch"""
    results: List[Dict[str, Any]] = []
    for e in (edits or [])[:10]:
        ok, fp, reason = _safe_path(str(e.get("path","")))
        if not ok:
            results.append({"path": str(fp), "ok": False, "error": reason})
            continue
        try:
            src = fp.read_text(encoding="utf-8")
            new, n = _apply_regex(src, str(e.get("pattern","")), str(e.get("replacement","")), bool(e.get("multiple", False)))
            diff = _unified_diff(src, new, str(fp))
            results.append({"path": str(fp), "ok": True, "matches": n, "diff": diff})
        except Exception as ex:
            results.append({"path": str(fp), "ok": False, "error": f"{type(ex).__name__}:{ex}"})
    return {"ok": True, "label": label, "slot": get_ab_mode("SELFEDIT"), "results": results}

def apply(label: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Applies changes in slot B with auto-catback for checks.
    In slot A - forced drain-rune."""
    with ab_switch("SELFEDIT") as slot:
        if slot == "A":
            res = dry_run(label, edits)
            res["note"] = "slot A: dry-run only"
            return res

        ts = time.time()
        bdir = BACKUPS / time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
        bdir.mkdir(parents=True, exist_ok=True)
        touched: List[Path] = []
        per_file: List[Dict[str, Any]] = []
        try:
            # 1) prepare new versions and local syntax checks
            prepared: List[Tuple[Path, str, str]] = []
            for e in (edits or [])[:10]:
                ok, fp, reason = _safe_path(str(e.get("path","")))
                if not ok:
                    per_file.append({"path": str(fp), "ok": False, "error": reason}); continue
                src = fp.read_text(encoding="utf-8")
                new, n = _apply_regex(src, str(e.get("pattern","")), str(e.get("replacement","")), bool(e.get("multiple", False)))
                if n == 0:
                    per_file.append({"path": str(fp), "ok": False, "error": "no_match"}); continue
                ok_syn, syn_msg = _check_syntax(new if fp.suffix==".py" else "pass", fp)
                if not ok_syn and fp.suffix==".py":
                    per_file.append({"path": str(fp), "ok": False, "error": syn_msg}); continue
                prepared.append((fp, src, new))
                per_file.append({"path": str(fp), "ok": True, "matches": n})
            if not prepared:
                _log({"ts": ts, "label": label, "slot": slot, "status": "no_changes"})
                return {"ok": False, "label": label, "slot": slot, "error": "no_changes"}

            # 2) make backups and write new files
            for fp, src, new in prepared:
                rel = fp.relative_to(Path.cwd())
                backup_fp = bdir / rel
                backup_fp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, backup_fp)
                fp.write_text(new, encoding="utf-8")
                touched.append(fp)

            # 3) route verification (and indirectly imports)
            ok_verify, vmsg = _run_verify_routes()
            if not ok_verify:
                raise RuntimeError(f"verify_failed:{vmsg}")

            # 4) uspekh
            rec = {"ts": ts, "label": label, "slot": slot, "status": "applied", "files": [str(p) for p in touched]}
            _log(rec)
            return {"ok": True, **rec}

        except Exception as e:
            # 5) avtkatbek
            for fp in touched:
                rel = fp.relative_to(Path.cwd())
                bfp = bdir / rel
                try:
                    if bfp.exists():
                        shutil.copy2(bfp, fp)
                except Exception:
                    pass
            rec = {"ts": ts, "label": label, "slot": slot, "status": "rolled_back", "err": f"{type(e).__name__}:{e}", "trace": traceback.format_exc()[-500:]}
            _log(rec)
            return {"ok": False, **rec}

# finalnaya stroka
# c=a+b