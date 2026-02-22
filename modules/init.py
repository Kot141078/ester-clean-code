# -*- coding: utf-8 -*-
"""
Kornevoy paket `modules` (obnovlenie): korrektnyy alias dlya scheduler, chtoby
'modules.scheduler' byl PAKETOM, esli na diske est odnoimennaya papka.

MOSTY:
- Yavnyy: (routes.* ↔ modules.*) — ne lomaem poisk podpaketov.
- Skrytyy #1: (Importer ↔ Ustoychivost) alias k scheduler_engine tolko kogda podpaketa net.
- Skrytyy #2: (Diagnostika) bazovye obekty events_bus/telegram_feed_store.

ZEMNOY ABZATs:
«Schitok» ne podmenyaet tseluyu liniyu, esli na ney uzhe ustanovlen modulnyy blok (papka).

# c=a+b
"""
from __future__ import annotations
import sys, time, importlib, importlib.util, types
from typing import Any, Dict

# ====== Bazovye utility ======
class _EventsBus:
    def __init__(self):
        self._log: list[dict] = []
        self._impl = None
        try:
            self._impl = importlib.import_module("modules.events_bus")
        except Exception:
            self._impl = None

    def _append_local(self, kind: str, payload: Any = None, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        rec = {
            "ts": float(time.time()),
            "kind": str(kind or "event"),
            "payload": payload,
        }
        if meta:
            rec["meta"] = dict(meta)
        self._log.append(rec)
        return rec

    def append(self, kind: str, payload: Any = None, **meta: Any) -> Dict[str, Any]:
        if self._impl and hasattr(self._impl, "append"):
            return self._impl.append(kind, payload, **meta)  # type: ignore[operator]
        return self._append_local(kind, payload, dict(meta or {}))

    def publish(
        self,
        kind: str,
        data: Dict[str, Any] | None = None,
        payload: Any = None,
        meta: Dict[str, Any] | None = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        eff_payload = payload if payload is not None else data
        if self._impl and hasattr(self._impl, "publish"):
            try:
                return self._impl.publish(kind, eff_payload, meta=meta, **extra)  # type: ignore[operator]
            except TypeError:
                # sovmestimost s vozmozhnoy staroy signaturoy
                return self._impl.publish(kind, eff_payload)  # type: ignore[operator]
        merged_meta = dict(meta or {})
        if extra:
            merged_meta.update(extra)
        rec = self._append_local(kind, eff_payload, merged_meta)
        return {"ok": True, "event": rec}

    def emit(self, kind: str, payload: Any = None, **meta: Any) -> Dict[str, Any]:
        return self.publish(kind, payload=payload, meta=dict(meta or {}))

    def feed(self, since: float = 0.0, kind: str | None = None, limit: int = 100, kinds: list[str] | None = None):
        if self._impl and hasattr(self._impl, "feed"):
            try:
                return self._impl.feed(since=since, kind=kind, limit=limit, kinds=kinds)  # type: ignore[operator]
            except TypeError:
                out = self._impl.feed(since=since, kind=kind, limit=limit)  # type: ignore[operator]
                if kinds is not None and isinstance(out, list):
                    ks = {str(x) for x in (kinds or []) if str(x)}
                    out = [x for x in out if str((x or {}).get("kind") or "") in ks]
                    return {"ok": True, "items": out, "count": len(out)}
                return out

        try:
            since_f = float(since or 0.0)
        except Exception:
            since_f = 0.0
        lim = max(1, int(limit or 100))
        ks = {str(x) for x in (kinds or []) if str(x)}
        out = []
        for it in self._log:
            try:
                ts = float(it.get("ts", 0.0))
            except Exception:
                ts = 0.0
            if ts <= since_f:
                continue
            k = str(it.get("kind") or "")
            if kind and k != str(kind):
                continue
            if ks and k not in ks:
                continue
            out.append(it)
        out = out[-lim:]
        if kinds is not None:
            return {"ok": True, "items": out, "count": len(out)}
        return out

    def last_ts(self) -> float:
        if self._impl and hasattr(self._impl, "last_ts"):
            return float(self._impl.last_ts())  # type: ignore[operator]
        if not self._log:
            return 0.0
        try:
            return float(self._log[-1].get("ts", 0.0))
        except Exception:
            return 0.0

    def count(self) -> int:
        if self._impl and hasattr(self._impl, "count"):
            return int(self._impl.count())  # type: ignore[operator]
        return len(self._log)

    def clear(self) -> Dict[str, Any]:
        if self._impl and hasattr(self._impl, "clear"):
            return self._impl.clear()  # type: ignore[operator]
        self._log.clear()
        return {"ok": True, "cleared": True}

    def history(self, n: int = 100) -> list[dict]:
        out = self.feed(limit=int(n or 100))
        if isinstance(out, dict):
            return list(out.get("items") or [])
        return list(out or [])

events_bus = _EventsBus()

class _TelegramFeedStore:
    def __init__(self): self._items: list[dict] = []
    def add(self, item: dict) -> dict: self._items.append(dict(item)); return {"ok": True, "count": len(self._items)}
    def list(self, page: int = 1, size: int = 50) -> dict:
        page, size = max(1,int(page)), max(1,int(size)); s, e = (page-1)*size, (page-1)*size+size
        return {"ok": True, "page": page, "size": size, "total": len(self._items), "items": self._items[s:e]}

telegram_feed_store = _TelegramFeedStore()

# ====== Korrektnyy alias dlya modules.scheduler ======
# Esli na diske EST podpaket 'modules.scheduler' — NE podmenyaem ego engine-modulem.
_spec = importlib.util.find_spec("modules.scheduler")
if _spec is None:
    try:
        import modules.scheduler_engine as _sched  # type: ignore
        sys.modules.setdefault("modules.scheduler", _sched)  # alias tolko pri otsutstvii podpaketa
    except Exception:
        pass

# ====== Dinamicheskie zaglushki dlya gluboko vlozhennykh podpaketov (kak ranshe) ======
import importlib.machinery, importlib.abc
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def _make_stub(fullname: str) -> types.ModuleType:
    m = types.ModuleType(fullname); m.__package__ = fullname; m.__path__ = []  # type: ignore[attr-defined]
    def status(): return {"ok": False, "reason": "not_configured", "module": fullname}
    def list_items(): return {"ok": True, "items": []}
    def get(*a, **kw): return None
    def snapshot(*a, **kw): return {"ok": True, "snapshot": {}}
    def exchange(*a, **kw): return {"ok": True}
    m.status, m.list_items, m.get, m.snapshot, m.exchange = status, list_items, get, snapshot, exchange  # type: ignore[attr-defined]
    return m

class _ModulesStubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    prefix = "modules."
    def find_spec(self, fullname, path=None, target=None):  # noqa: D401, ANN001
        if not fullname.startswith(self.prefix): return None
        real = importlib.machinery.PathFinder.find_spec(fullname, path)
        if real is not None or fullname in sys.modules: return None
        return importlib.machinery.ModuleSpec(fullname, self)
    def create_module(self, spec): return _make_stub(spec.name)  # type: ignore[attr-defined]
    def exec_module(self, module): return None

if not any(isinstance(f, _ModulesStubFinder) for f in sys.meta_path):
    sys.meta_path.append(_ModulesStubFinder())

__all__ = ["events_bus", "telegram_feed_store"]
# c=a+b
