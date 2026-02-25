# -*- coding: utf-8 -*-
"""memory_reembed.py - bezopasnyy pere-embedding lokalnoy pamyati Ester.

Features:
- "Zheleznyy" adapter stora: chitaet memory/*.json, *.jsonl/ndjson, memory/daily/*.json,
  prinimaet formaty: spisok dict/str, obekt s klyuchami records/items/data, map key->dict/str.
- Ignoreet sluzhebnye fayly (extra_routes.json, schema.json) po imeni i/ili strukture.
- Obnovlyaet tolko te zapisi, u kotorykh net embeddinga or razmernost otlichaetsya.
- Podderzhivaet A/B-sloty: AB_MODE=B — tolko saydkary (<file>.reembed.json), originaly ne trogaem.
  AB_MODE=A — delaem bekap i pishem in-place (esli ne ukazan --sidecar).
- "Sukhoy" progon (--dry-run), limit (--limit), prinuditelnyy pereschet (--force-all).
- Avto-opredelenie razmernosti embeddinga cherez /v1/embeddings (LM Studio/OpenAI-sovmestimyy API).
- Report v JSON (--report). Minimal details: only standartnaya biblioteka.

Wednesday (env):
- ESTER_DATA_ROOT / ESTER_DATA_DIR - koren dannykh project (by umolchaniyu: ./data).
- OPENAI_API_BASE, OPENAI_API_KEY - HTTP endpoint i klyuch (LM Studio: klyuch mozhet byt lyubym nepustym).
- EMBED_MODEL — identifikator modeli embeddingov (primer: text-embedding-nomic-embed-text-v1.5).

Primery:
    # 0) ping embeddera (sm. tools/embed_ping.ps1)
    #1) scan only (no recording):
    python scripts/memory_reembed.py --scan-only --report .\out_reembed\scan.json

    # 2) "sukhoy" progon pervykh 100 zapisey:
    python scripts/memory_reembed.py --dry-run --limit 100 --report .\out_reembed\report_dry.json

    # 3) realnaya zapis s bekapom (AB_MODE=A):
    set AB_MODE=A
    python scripts/memory_reembed.py --backup-dir "D:\ester-project\_backup_manual" --report .\out_reembed\report_real.json

    # 4) bezopasnyy slot (AB_MODE=B) — just saydkary, originaly ne trogaem:
    set AB_MODE=B
    python scripts/memory_reembed.py --report .\out_reembed\report_sidecar.json

    # 5) Explicit dimension, if auto-detection fails:
    python scripts/memory_reembed.py --embed-dim 768 --dry-run

Sovmestimost: drop-in. Ne trebuet pravki importov v drugikh modulyakh."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import io
import json
import os
import re
import sys
import time
import uuid
import glob
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --------- Utility logirovaniya ---------
def log(msg: str) -> None:
    sys.stdout.write(msg.rstrip() + "\n")
    sys.stdout.flush()

def warn(msg: str) -> None:
    sys.stderr.write("[warn] " + msg.rstrip() + "\n")
    sys.stderr.flush()

def fatal(msg: str, code: int = 2) -> None:
    sys.stderr.write("[fatal] " + msg.rstrip() + "\n")
    sys.stderr.flush()
    sys.exit(code)

# --------- HTTP client for /v1/embeddings ---------
def _http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float = 30.0) -> Dict[str, Any]:
    import urllib.request, urllib.error
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        # useful to see the body of the error LM Studio
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        fatal(f"HTTP {e.code} at {url}: {body}")
    except urllib.error.URLError as e:
        fatal(f"URL error at {url}: {e}")
    except Exception as e:
        fatal(f"Request failed at {url}: {e}")
    return {}

def detect_embed_dim(base: str, api_key: str, model: str) -> int:
    url = base.rstrip("/") + "/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {"model": model, "input": "ping"}
    data = _http_post_json(url, payload, headers)
    try:
        emb = data["data"][0]["embedding"]
        if isinstance(emb, list):
            return len(emb)
    except Exception:
        pass
    fatal("It was not possible to determine the embedding dimension (check EMBED_MODEL / LM Studio).")
    return 0

def do_embed(base: str, api_key: str, model: str, text: str) -> List[float]:
    url = base.rstrip("/") + "/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {"model": model, "input": text}
    data = _http_post_json(url, payload, headers)
    emb = data["data"][0]["embedding"]
    if not isinstance(emb, list):
        raise RuntimeError("Bad embedding payload")
    return emb

# --------- Recognition and normalization of memory records ---------
TEXT_KEYS = ("text", "content", "body", "message", "note", "value", "data", "desc", "description")
EMB_KEYS  = ("embedding", "vector", "e", "embedding_v1")  # read/write in embedding

def is_service_file(path: str) -> bool:
    name = os.path.basename(path).lower()
    if name in {"schema.json"}:
        return True
    # extra_rutes.zhsion is not a memory store, ignore it
    if name.startswith("extra_routes"):
        return True
    return False

def as_record(obj: Any) -> Optional[Dict[str, Any]]:
    """Causes an object to write memory or returns None (not like writing)."""
    if isinstance(obj, dict):
        # tekst
        text = None
        for k in TEXT_KEYS:
            if k in obj and isinstance(obj[k], (str, int, float)):
                text = str(obj[k])
                break
        # allow a map of the form {"id": ЗЗФ0З} - straighten at the top level above
        if text is None and "text" not in obj:
            # if it looks like a container for records, we do not consider it a record
            if any(k in obj for k in ("records", "items", "data")):
                return None
            # if the dictionary is “flat” and there is no explicit text, we’ll try to collect it from known fields
            candidates = [obj.get("title"), obj.get("name"), obj.get("summary")]
            candidates = [str(x) for x in candidates if isinstance(x, (str, int, float))]
            if candidates:
                text = " - ".join(candidates)
        if text is None:
            return None
        rec = dict(obj)
        rec["text"] = text
        return rec
    elif isinstance(obj, (str, int, float)):
        return {"text": str(obj)}
    else:
        return None

def has_embedding(rec: Dict[str, Any], dim: Optional[int] = None) -> bool:
    for k in EMB_KEYS:
        if k in rec and isinstance(rec[k], list):
            if dim is None:
                return True
            return len(rec[k]) == dim
    return False

def get_id(rec: Dict[str, Any]) -> str:
    for k in ("id", "uid", "key", "uuid"):
        if k in rec and rec[k]:
            return str(rec[k])
    # stable ID based on text hash (+ salts of key fields, if any)
    seed = rec.get("text") or ""
    seed += "|" + str(rec.get("created_at") or rec.get("ts") or "")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()

# --------- Adapter stora ---------
@dataclasses.dataclass
class SourceFile:
    path: str
    style: str  # 'jsonl' | 'array' | 'object-map' | 'object-list'
    container_key: Optional[str] = None  # dlya object-list (records/items/data)
    data_cache: Any = None              # downloaded content (for recording)

class JsonStoreAdapter:
    """Universal adapter for memora/*.json, *.jsonl/njson and subdirectories."""
    def __init__(self, memory_dir: str) -> None:
        self.memory_dir = os.path.abspath(memory_dir)
        if not os.path.isdir(self.memory_dir):
            fatal(f"Ne nayden katalog pamyati: {self.memory_dir}")
        self._sources: List[SourceFile] = []

    def discover(self) -> None:
        patterns = [
            os.path.join(self.memory_dir, "*.json"),
            os.path.join(self.memory_dir, "*.jsonl"),
            os.path.join(self.memory_dir, "*.ndjson"),
            os.path.join(self.memory_dir, "daily", "*.json"),
            os.path.join(self.memory_dir, "records.*"),
        ]
        files: List[str] = []
        for p in patterns:
            files.extend(glob.glob(p))
        # filtr sluzhebnykh
        files = [f for f in sorted(set(files)) if not is_service_file(f)]
        for f in files:
            style, container_key = self._probe_style(f)
            if style:
                self._sources.append(SourceFile(path=f, style=style, container_key=container_key))

        if not self._sources:
            fatal(f"The memory store was not found in ZZF0Z. Expected: records.jsonl/njson/jsion or directory records/*.zsionl")

    def _probe_style(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        name = os.path.basename(path).lower()
        # Jsionl/Njson by extension
        if name.endswith(".jsonl") or name.endswith(".ndjson"):
            return "jsonl", None

        # probuem prolistat JSON
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                txt = f.read()
            data = json.loads(txt)
        except Exception:
            # invalid JSION - try as JSIONL (there is an extension .JSION with NJSON)
            try:
                with io.open(path, "r", encoding="utf-8") as f:
                    f.readline()
                return "jsonl", None
            except Exception:
                return None, None

        if isinstance(data, list):
            return "array", None
        if isinstance(data, dict):
            for key in ("records", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return "object-list", key
            # map key -> record
            # if most of the values ​​are dist/str, we consider it a map
            vals = list(data.values())
            if vals and all(isinstance(v, (dict, str, int, float, list)) for v in vals):
                return "object-map", None

        return None, None

    def iter_records(self) -> Iterator[Tuple[SourceFile, int, Dict[str, Any]]]:
        """We iterate over ALL normalized records (as dist).
        Returns (source, index, record)."""
        for src in self._sources:
            if src.style == "jsonl":
                with io.open(src.path, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        obj = None
                        try:
                            obj = json.loads(line)
                        except Exception:
                            # stroka-tekst
                            obj = line
                        rec = as_record(obj)
                        if rec is None:
                            continue
                        yield (src, i - 1, rec)
            else:
                # load once to write at the end
                if src.data_cache is None:
                    with io.open(src.path, "r", encoding="utf-8") as f:
                        src.data_cache = json.load(f)

                if src.style == "array":
                    arr = src.data_cache
                    if isinstance(arr, list):
                        for i, obj in enumerate(arr):
                            rec = as_record(obj)
                            if rec is None:
                                continue
                            yield (src, i, rec)

                elif src.style == "object-list":
                    key = src.container_key or "records"
                    arr = src.data_cache.get(key, [])
                    if isinstance(arr, list):
                        for i, obj in enumerate(arr):
                            rec = as_record(obj)
                            if rec is None:
                                continue
                            yield (src, i, rec)

                elif src.style == "object-map":
                    mp = src.data_cache
                    if isinstance(mp, dict):
                        for i, (k, obj) in enumerate(mp.items()):
                            rec = as_record(obj)
                            if rec is None:
                                continue
                            # let's set the key as default ID
                            if "id" not in rec and k:
                                rec = dict(rec)
                                rec["id"] = k
                            yield (src, i, rec)

    def apply_record(self, src: SourceFile, index: int, updated: Dict[str, Any]) -> None:
        """Applies a record update (embedding and, if necessary, id/text) to the loaded src.data_quality cache."""
        emb = updated.get("embedding")
        if src.style == "jsonl":
            # for zhsionl writes sidecar (rewriting jsyonl “in place” is unsafe)
            return

        if src.style == "array":
            if isinstance(src.data_cache, list) and index < len(src.data_cache):
                obj = src.data_cache[index]
                if isinstance(obj, dict):
                    obj["embedding"] = emb
                    obj.setdefault("id", updated.get("id", get_id(updated)))
                    obj.setdefault("text", updated.get("text", ""))
                else:
                    # byl primitiv — zamenim na dict
                    src.data_cache[index] = {
                        "id": updated.get("id", get_id(updated)),
                        "text": updated.get("text", str(obj)),
                        "embedding": emb,
                    }

        elif src.style == "object-list":
            key = src.container_key or "records"
            arr = src.data_cache.get(key, [])
            if isinstance(arr, list) and index < len(arr):
                obj = arr[index]
                if isinstance(obj, dict):
                    obj["embedding"] = emb
                    obj.setdefault("id", updated.get("id", get_id(updated)))
                    obj.setdefault("text", updated.get("text", ""))
                else:
                    arr[index] = {
                        "id": updated.get("id", get_id(updated)),
                        "text": updated.get("text", str(obj)),
                        "embedding": emb,
                    }

        elif src.style == "object-map":
            # The index is not the key here either, but it is enough to get to the same position; It's better to count by ID
            # We have already added the ID from the map key to the entry - we will find it and update it
            if isinstance(src.data_cache, dict):
                rec_id = updated.get("id", None)
                if rec_id and rec_id in src.data_cache and isinstance(src.data_cache[rec_id], dict):
                    src.data_cache[rec_id]["embedding"] = emb
                    src.data_cache[rec_id].setdefault("text", updated.get("text", ""))

    def save_source(self, src: SourceFile, ab_mode: str, backup_dir: Optional[str], sidecar_only: bool = False) -> Optional[str]:
        """Sokhranyaet odin iskhodnik:
          - AB_MODE=A i ne sidecar_only: delaem bekap i pishem in-place.
          - inache: pishem saidkar <file>.reembed.json
        Vozvraschaet put zapisannogo fayla (ili saydkara)."""
        path = os.path.abspath(src.path)
        if ab_mode.upper() == "A" and not sidecar_only and src.style != "jsonl":
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                bpath = os.path.join(backup_dir, f"{os.path.basename(path)}.{stamp}.bak")
                try:
                    with io.open(bpath, "w", encoding="utf-8") as bf:
                        json.dump(src.data_cache, bf, ensure_ascii=False, indent=2)
                except Exception as e:
                    warn(f"Failed to write backup ZZF0Z: ZZF1ZZ")
            # master record
            try:
                with io.open(path, "w", encoding="utf-8") as f:
                    json.dump(src.data_cache, f, ensure_ascii=False, indent=2)
                return path
            except Exception as e:
                warn(f"Failed to write ZZF0Z: ZZF1ZZ")
                return None
        else:
            # saydkar
            sidecar = path + ".reembed.json"
            try:
                payload = {
                    "source": path,
                    "style": src.style,
                    "container_key": src.container_key,
                    "updated": src.data_cache,
                }
                with io.open(sidecar, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                return sidecar
            except Exception as e:
                warn(f"Failed to record sidecar ZZF0Z: ZZF1ZZ")
                return None

# --------- Osnovnaya logika ---------
def main() -> int:
    parser = argparse.ArgumentParser(description="Re-embed Ester memory with AB-safe flow.")
    parser.add_argument("--data-root", dest="data_root", type=str, default=None, help="Koren dannykh (ESTER_DATA_ROOT/ESTER_DATA_DIR).")
    parser.add_argument("--memory-dir", dest="memory_dir", type=str, default=None, help="Memory directory (default: <date-root>/memory).")
    parser.add_argument("--backup-dir", dest="backup_dir", type=str, default=None, help="Kuda skladyvat bekapy (AB_MODE=A).")
    parser.add_argument("--report", dest="report", type=str, default=None, help="Path for the JSON report.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Do not record anything, just count and log.")
    parser.add_argument("--limit", dest="limit", type=int, default=None, help="Maximum records for processing.")
    parser.add_argument("--force-all", dest="force_all", action="store_true", help="Recalculate all records (even if there is a vector of the required dimension).")
    parser.add_argument("--embed-dim", dest="embed_dim", type=int, default=None, help="Explicit embedding dimension.")
    parser.add_argument("--sidecar", dest="sidecar", action="store_true", help="Vsegda pisat saydkar vmesto in-place.")
    parser.add_argument("--scan-only", dest="scan_only", action="store_true", help="Just identify the store candidates and leave.")
    args = parser.parse_args()

    # --- okruzhenie i korni ---
    data_root = args.data_root or os.environ.get("ESTER_DATA_ROOT") or os.environ.get("ESTER_DATA_DIR") or os.path.join(os.getcwd(), "data")
    data_root = os.path.abspath(data_root)
    memory_dir = args.memory_dir or os.path.join(data_root, "memory")

    ab_mode = os.environ.get("AB_MODE", "B").upper()
    if ab_mode not in ("A", "B"):
        ab_mode = "B"

    openai_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("LMSTUDIO_URL") or ""
    openai_key  = os.environ.get("OPENAI_API_KEY") or "lm-studio"
    embed_model = os.environ.get("EMBED_MODEL") or ""

    if not embed_model:
        fatal("Ne zadan EMBED_MODEL. Podskazka: sm. tools/lm_models.ps1 i vyberi embedding_candidate=True.")

    log(f"[info] data_root={data_root}")
    log(f"[info] memory_dir={memory_dir}")
    log(f"[info] AB_MODE={ab_mode}")
    log(f"[info] EMBED_MODEL={embed_model}")

    # --- adapter ---
    adapter = JsonStoreAdapter(memory_dir)
    adapter.discover()

    if args.scan_only:
        # scan report
        payload = {
            "ok": True,
            "message": f"Naydeno faylov: {len(adapter._sources)}",
            "data_root": data_root,
            "memory_dir": memory_dir,
            "sources": [dataclasses.asdict(s) for s in adapter._sources],
            "embed_model": embed_model,
            "embed_dim": args.embed_dim,
            "updated": 0, "skipped": 0, "total": 0, "dry_run": True, "scan_only": True,
        }
        if args.report:
            os.makedirs(os.path.dirname(os.path.abspath(args.report) or "."), exist_ok=True)
            with io.open(args.report, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        log(f"[scan] faylov: {len(adapter._sources)}")
        return 0

    # --- razmernost ---
    dim = args.embed_dim
    if dim is None:
        if not openai_base:
            fatal("OPENAY_API_BASE/LTSTUDIO_URL is not set for auto-dimension detection (or use --embed-smoke).")
        dim = detect_embed_dim(openai_base, openai_key, embed_model)
    log(f"[info] embed_dim={dim}")

    # --- osnovnoy prokhod ---
    total = 0
    updated = 0
    skipped = 0
    per_source_changed = set()  # source paths where changes were made
    errors: List[str] = []

    try:
        for (src, index, rec) in adapter.iter_records():
            total += 1
            if args.limit and total > args.limit:
                break

            # id / text
            if "id" not in rec or not rec.get("id"):
                rec["id"] = get_id(rec)
            text = rec.get("text") or ""
            if not text or len(text.strip()) == 0:
                skipped += 1
                continue

            need = args.force_all or (not has_embedding(rec, dim))
            if not need:
                skipped += 1
                continue

            # embedd
            try:
                emb = do_embed(openai_base, openai_key, embed_model, text)
            except Exception as e:
                errors.append(f"{src.path}#{index}: {e}")
                continue

            new_rec = dict(rec)
            new_rec["embedding"] = emb
            adapter.apply_record(src, index, new_rec)
            updated += 1
            per_source_changed.add(src.path)

        if args.dry_run:
            log("yudra-runsch Nothing is recorded.")
        else:
            # save changed sources
            for p in sorted(per_source_changed):
                src = next((s for s in adapter._sources if s.path == p), None)
                if not src:
                    continue
                outp = adapter.save_source(src, ab_mode=ab_mode, backup_dir=args.backup_dir, sidecar_only=args.sidecar or src.style == "jsonl")
                if outp:
                    log(f"[ok] wrote: {outp}")

    except KeyboardInterrupt:
        warn("Prervano polzovatelem (Ctrl+C).")

    # --- otchet ---
    summary = {
        "ok": True,
        "data_root": data_root,
        "memory_dir": memory_dir,
        "embed_model": embed_model,
        "embed_dim": dim,
        "updated": updated,
        "skipped": skipped,
        "total": total,
        "dry_run": bool(args.dry_run),
        "ab_mode": ab_mode,
        "sidecar": bool(args.sidecar),
        "sources_changed": sorted(list(per_source_changed)),
        "errors": errors,
    }
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report) or "."), exist_ok=True)
        with io.open(args.report, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"[done] total={total}, updated={updated}, skipped={skipped}, errors={len(errors)}")
    if errors:
        for e in errors[:10]:
            warn(e)
        if len(errors) > 10:
            warn(f"... and more ZZF0Z errors")
    return 0

if __name__ == "__main__":
    sys.exit(main())