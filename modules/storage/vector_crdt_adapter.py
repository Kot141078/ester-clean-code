# -*- coding: utf-8 -*-
"""Lightweight CRDT adapter backed by CAS blobs."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from modules.ingest.cas import put_bytes, read_bytes

_INDEX: Dict[str, Dict[str, Any]] = {}


class VectorCRDTAdapter:
    def __init__(self) -> None:
        self._index = _INDEX

    def put(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Compatibility signatures:
          put(item_id: str, payload: dict) -> {id,cid,meta}
          put(meta=..., payload_bytes=..., embedding=[...]) -> CRDT dict
        """
        if args and isinstance(args[0], str):
            item_id = str(args[0])
            payload = dict(args[1] if len(args) > 1 else kwargs.get("payload") or {})
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            cid, _path, _size = put_bytes(raw)
            rec = {
                "id": item_id,
                "cid": cid,
                "meta": {"_cas": cid},
                "data": payload,
                "ts": int(time.time()),
            }
            self._index[item_id] = rec
            return {"id": item_id, "cid": cid, "meta": {"_cas": cid}}

        meta = dict(kwargs.get("meta") or {})
        payload_bytes = kwargs.get("payload_bytes") or b""
        if isinstance(payload_bytes, str):
            payload_bytes = payload_bytes.encode("utf-8")
        if isinstance(payload_bytes, bytearray):
            payload_bytes = bytes(payload_bytes)
        if not isinstance(payload_bytes, bytes):
            payload_bytes = bytes(payload_bytes)
        embedding = kwargs.get("embedding")

        cas_cid, _path, size = put_bytes(payload_bytes)
        emb_ref = None
        if embedding is not None:
            emb_blob = json.dumps(list(embedding), ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            emb_ref, _epath, _esz = put_bytes(emb_blob)

        item_id = str(kwargs.get("id") or meta.get("id") or f"doc:{int(time.time() * 1000)}")
        rec = {
            "id": item_id,
            "meta": meta,
            "cas": cas_cid,
            "size": int(size),
            "embedding_ref": emb_ref,
            "ts": int(time.time()),
        }
        self._index[item_id] = rec
        return rec

    def fetch(self, item_id: str) -> Optional[Dict[str, Any]]:
        rec = self._index.get(str(item_id))
        if not rec:
            return None
        if "cid" in rec:
            cid = rec.get("cid")
            payload: Dict[str, Any] = dict(rec.get("data") or {})
            if not payload and cid:
                try:
                    payload = json.loads(read_bytes(str(cid)).decode("utf-8"))
                except Exception:
                    payload = {}
            return {
                "id": rec.get("id"),
                "cid": cid,
                "meta": dict(rec.get("meta") or {}),
                "data": payload,
            }
        return dict(rec)

    def remove(self, item_id: str) -> None:
        self._index.pop(str(item_id), None)

