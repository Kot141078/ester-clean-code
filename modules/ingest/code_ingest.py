# -*- coding: utf-8 -*-
"""modules.ingest.code_ingest - analiz iskhodnikov i strukturirovannaya zagruzka v pamyat/KG.

MOSTY:
- (Yavnyy) routes.ingest_* ↔ analyze_code/ingest_code.
- (Skrytyy #1) KG ↔ tekst: sozdaem zapisi i rebra, esli KGStore dostupen.
- (Skrytyy #2) Dedup ↔ indexes: podderzhka should_ingest/record_ingest, esli est.

ZEMNOY ABZATs:
Bystryy parser po direktorii: vytaskivaet docstring/shapku/imena funktsiy — dostatochno dlya “zhivoy” priemki v Ester.
# c=a+b"""
from __future__ import annotations

import os, re, json, hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from modules.ingest.dedup_index import record_ingest, should_ingest  # type: ignore
except Exception:  # pragma: no cover
    def record_ingest(sha, path, size=0, meta=None): return {"sha": sha, "path": path, "size": size, "meta": meta or {}}
    def should_ingest(sha, size=0): return True

from .common import persist_dir, add_structured_record, kg_attach_artifact
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Reliable patterns (equal strings, explicit spaces):
RE_DEF   = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
RE_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
RE_PY_IMPORT = re.compile(r"^\s*import\s+(.+)$", re.MULTILINE)
RE_PY_FROM = re.compile(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+", re.MULTILINE)
RE_JS_IMPORT_FROM = re.compile(r"""^\s*import\s+[^'"]*?\sfrom\s+['"]([^'"]+)['"]""", re.MULTILINE)
RE_JS_IMPORT_SIDE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.MULTILINE)
RE_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE)

CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def _peek_py(path: str) -> Dict[str, Any]:
    text = open(path, "r", encoding="utf-8", errors="ignore").read()
    header = ""
    if '"""' in text:
        try:
            header = text.split('"""', 2)[1].strip()[:400]
        except Exception:
            header = ""
    functions = RE_DEF.findall(text)
    classes   = RE_CLASS.findall(text)
    return {"header": header, "functions": functions, "classes": classes, "size": len(text)}


def _iter_code_files(root: str, glob: str) -> List[Path]:
    patterns = [glob]
    # Backward compatible default: include JS/TS imports graph as well.
    if str(glob or "").strip() in {"**/*.py", "*.py"}:
        patterns = ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.mjs", "**/*.cjs"]
    out: List[Path] = []
    seen = set()
    for pat in patterns:
        for p in Path(root).glob(pat):
            if not p.is_file():
                continue
            if p.suffix.lower() not in CODE_EXTS:
                continue
            sp = str(p)
            if sp in seen:
                continue
            seen.add(sp)
            out.append(p)
    return out


def _normalize_package(spec: str, lang: str) -> str:
    s = str(spec or "").strip().strip("\"'`")
    if not s:
        return ""
    if s.startswith(".") or s.startswith("/"):
        return ""
    if lang == "python":
        return s.split(".", 1)[0].strip()
    # npm scoped package support: @scope/pkg/inner -> @scope/pkg
    if s.startswith("@"):
        parts = s.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return s
    return s.split("/", 1)[0].strip()


def _extract_imports(path: Path, text: str) -> List[str]:
    ext = path.suffix.lower()
    lang = "python" if ext == ".py" else "js"
    out: List[str] = []
    if lang == "python":
        for line in RE_PY_IMPORT.findall(text):
            for part in str(line or "").split(","):
                mod = part.strip().split(" as ", 1)[0].strip()
                pkg = _normalize_package(mod, "python")
                if pkg:
                    out.append(pkg)
        for mod in RE_PY_FROM.findall(text):
            pkg = _normalize_package(mod, "python")
            if pkg:
                out.append(pkg)
    else:
        for mod in RE_JS_IMPORT_FROM.findall(text):
            pkg = _normalize_package(mod, "js")
            if pkg:
                out.append(pkg)
        for mod in RE_JS_IMPORT_SIDE.findall(text):
            pkg = _normalize_package(mod, "js")
            if pkg:
                out.append(pkg)
        for mod in RE_JS_REQUIRE.findall(text):
            pkg = _normalize_package(mod, "js")
            if pkg:
                out.append(pkg)
    # Unique preserving order
    uniq: List[str] = []
    seen = set()
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq


def _peek_code(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lower()
    meta: Dict[str, Any] = {
        "size": len(text),
        "language": "python" if ext == ".py" else "javascript",
        "imports": _extract_imports(path, text),
    }
    if ext == ".py":
        meta.update(_peek_py(str(path)))
    else:
        head = ""
        for line in text.splitlines():
            s = line.strip()
            if s:
                head = s[:400]
                break
        meta.update({"header": head, "functions": [], "classes": []})
    return meta

def analyze_code(root: str, glob: str = "**/*.py") -> Dict[str, Any]:
    if not os.path.isabs(root):
        root = os.path.join(persist_dir(), root)
    items: List[Dict[str, Any]] = []
    for p in _iter_code_files(root, glob):
        meta = _peek_code(p)
        items.append({"path": str(p), **meta})
    return {"ok": True, "count": len(items), "items": items}

def ingest_code(root: str, glob: str = "**/*.py", tags: Iterable[str] = ()) -> Dict[str, Any]:
    """High-level ingest of sources into memory/KG."""
    if not os.path.isabs(root):
        root = os.path.join(persist_dir(), root)
    if not os.path.isdir(root):
        return {"ok": False, "error": "dir_not_found", "dir": root}
    processed, skipped = 0, 0
    for p in _iter_code_files(root, glob):
        sha = _sha(str(p))
        if not should_ingest(sha, size=os.path.getsize(p)):
            skipped += 1
            continue
        meta = _peek_code(p)
        relpath = os.path.relpath(p, root).replace("\\", "/")
        rid = add_structured_record(text=meta.get("header","") or Path(p).name, tags=list(tags)+["code"])
        kg_attach_artifact(label=os.path.relpath(p, root), text=json.dumps(meta, ensure_ascii=False), tags=list(tags)+["code-meta"])
        # Build explicit import graph edges for code intelligence.
        try:
            from memory.kg_store import KGStore  # type: ignore
            kg = KGStore()
            src_id = f"codefile::{relpath}"
            nodes = [
                {
                    "id": src_id,
                    "type": "code.file",
                    "label": relpath,
                    "props": {"path": str(p), "lang": meta.get("language", "unknown")},
                }
            ]
            edges = []
            for pkg in meta.get("imports") or []:
                pkg_name = str(pkg or "").strip()
                if not pkg_name:
                    continue
                dst_id = f"package::{pkg_name}"
                nodes.append({"id": dst_id, "type": "package", "label": pkg_name, "props": {"name": pkg_name}})
                edges.append(
                    {
                        "src": src_id,
                        "rel": "imports",
                        "dst": dst_id,
                        "weight": 1.0,
                        "props": {"file": relpath},
                    }
                )
            kg.upsert_nodes(nodes)
            if edges:
                kg.upsert_edges(edges)
        except Exception:
            pass
        record_ingest(sha, str(p), size=os.path.getsize(p), meta={"rid": rid, **meta})
        processed += 1
    return {"ok": True, "processed": processed, "skipped": skipped, "root": root}
