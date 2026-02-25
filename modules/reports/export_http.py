# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.export_http - eksport svodok odnim arkhivom.
Register:
- GET `/compat/reports/download.json` — manifest
- GET `/compat/reports/download.tar.gz` — tar.gz s faylami

# c=a+b"""
import os, io, tarfile, time, json
from typing import Optional, Dict, Tuple, Callable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")
AB = os.getenv("ESTER_EXPORT_AB","A").upper().strip() or "A"

def _pick_callable(mod, names) -> Optional[Callable[[], str]]:
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            return fn
    return None

def _try_get(mod_name: str, fn_names: Tuple[str, ...], fallback_text: str, filename: str) -> Tuple[str, str, bool, str]:
    """
    Vozvraschaet: (filename, content, ok, note)
    """
    try:
        mod = __import__(mod_name, fromlist=["*"])
        fn = _pick_callable(mod, fn_names)
        if fn is None:
            return (filename, fallback_text, False, f"{mod_name}: no callable among {fn_names}")
        txt = fn()
        if not isinstance(txt, str) or not txt.strip():
            return (filename, fallback_text, False, f"{mod_name}: empty content")
        return (filename, txt, True, "")
    except Exception as e:
        return (filename, fallback_text, False, f"{mod_name}: {e.__class__.__name__}")

def _collect() -> Dict[str, Dict[str, str]]:
    """We collect the content of best-effort reports."""
    items: Dict[str, Dict[str, str]] = {}
    ts = int(time.time())
    # README
    items["README.txt"] = {
        "content": "Ester export pack\ncreated_at=%d\n" % ts,
        "mime": "text/plain; charset=utf-8",
    }
    # Kandidaty: module -> (callables to try, filename, default)
    candidates = [
        ("modules.reports.system_http", ("_md",), "system.md", "# system.md\n(not available)\n"),
        ("modules.reports.rag_http", ("_md", "_md_rag"), "rag.md", "# rag.md\n(not available)\n"),
        ("modules.reports.metrics_http", ("_md",), "metrics.md", "# metrics.md\n(not available)\n"),
        # routes obychno trebuet app; zdes berem bezopasnyy degraded-kontent
        ("modules.reports.routes_http", ("_md",), "routes.md", "# routes.md\n(not available in export context)\n"),
        ("modules.selfcheck.http", ("_summary_md", "_md", "summary_md"), "selfcheck_summary.md", "# selfcheck_summary.md\n(not available)\n"),
        ("modules.reports.kg_http", ("_snapshot_json",), "kg_snapshot.json", '{"ok": false}'),
    ]
    manifest = {"ok": True, "ab": AB, "items": [], "ts": ts}
    for mod_name, fns, fname, default in candidates:
        filename, content, ok, note = _try_get(mod_name, fns, default, fname)
        if AB == "B" and not ok:
            manifest["items"].append({"name": fname, "ok": False, "skipped": True, "note": note})
            continue
        items[fname] = {"content": content, "mime": "text/markdown" if fname.endswith(".md") else "application/json" if fname.endswith(".json") else "text/plain"}
        manifest["items"].append({"name": fname, "ok": ok, "skipped": False, "note": note})
    items["manifest.json"] = {"content": json.dumps(manifest, ensure_ascii=False, indent=2), "mime": "application/json"}
    return items

def _make_tgz(items: Dict[str, Dict[str, str]]) -> bytes:
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        for name, spec in items.items():
            data = spec["content"].encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return bio.getvalue()

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/download.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _json_manifest():
        items = _collect()
        return Response(content=items["manifest.json"]["content"], media_type="application/json")
    @app.get(prefix + "/download.tar.gz", response_class=__import__("fastapi").Response)  # type: ignore
    def _tgz():
        items = _collect()
        tgz = _make_tgz(items)
        headers = {"Content-Disposition": "attachment; filename=ester_reports.tgz"}
        return Response(content=tgz, media_type="application/gzip", headers=headers)
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/download.json")
    def _json_manifest():
        items = _collect()
        return Response(items["manifest.json"]["content"], mimetype="application/json")
    @app.get(prefix + "/download.tar.gz")
    def _tgz():
        items = _collect()
        tgz = _make_tgz(items)
        h = [("Content-Disposition","attachment; filename=ester_reports.tgz")]
        return Response(tgz, mimetype="application/gzip", headers=h)
    return True
