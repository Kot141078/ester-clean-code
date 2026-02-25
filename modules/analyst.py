# -*- coding: utf-8 -*-
"""modules/analyst.py - Deep Processing Unit (GPU/CPU safe).

EXPLICIT BRIDGE (c=a+b):
  a) vkhodyaschiy kontent (soobscheniya/veb/fayly) +
  b) protsedurnaya ochered obrabotki/sokhraneniya =>
  c) vosproizvodimyy analiticheskiy sled (JSONL).

HIDDEN BRIDGES:
  - Ashby: raznye vkhody privodim k edinomu payload.
  - Cover & Thomas: ogranichivaem “shirinu kanala” (snippet/metadannye).

EARTH:
  kak zheludochek serdtsa - prinimaet portsiyu i vytalkivaet dalshe; ne blokiruet osnovnoy potok."""

from __future__ import annotations

import os
import json
import logging
import threading
import time
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger("ester.analyst")

# torch - strictly optional
try:
    import torch  # type: ignore
except Exception:
    torch = None  # type: ignore


def _has_cuda() -> bool:
    try:
        return (torch is not None) and hasattr(torch, "cuda") and torch.cuda.is_available()  # type: ignore
    except Exception:
        return False


HAS_TORCH = torch is not None
HAS_CUDA = _has_cuda()


def cuda_device_count() -> int:
    if not HAS_CUDA:
        return 0
    try:
        return int(torch.cuda.device_count())  # type: ignore
    except Exception:
        return 0


HAS_DUAL_GPU = cuda_device_count() > 1
DEVICE = "cuda:1" if HAS_DUAL_GPU else ("cuda:0" if HAS_CUDA else "cpu")


def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass


class EsterAnalyst:
    def __init__(self) -> None:
        self.queue: "Queue[Dict[str, Any]]" = Queue()
        self.active: bool = True
        self.device: str = DEVICE
        logger.info(f"[ANALYST] Initialized on {self.device}. Dual GPU: {HAS_DUAL_GPU}")
        try:
            _mirror_background_event(
                f"[ANALYST_INIT] device={self.device} dual_gpu={int(HAS_DUAL_GPU)}",
                "analyst",
                "init",
            )
        except Exception:
            pass

        self.worker = threading.Thread(
            target=self._worker_loop, daemon=True, name="Analyst-Worker"
        )
        self.worker.start()

    def submit_event(self, content: str, source: str, meta: Optional[dict] = None) -> None:
        if not content or len(content) < 5:
            return
        payload = {
            "content": content,
            "source": source,
            "meta": meta or {},
            "ts": datetime.now().isoformat(),
        }
        self.queue.put(payload)

    def process_incoming_data(self, *args, **kwargs) -> None:
        """
        Compatibility shim:
          - process_incoming_data(content, source)
          - process_incoming_data(payload_dict)
        """
        try:
            if len(args) == 1 and isinstance(args[0], dict):
                p = args[0]
                self.submit_event(str(p.get("content", "")), str(p.get("source", "unknown")), p.get("meta") or {})
                return
            if len(args) >= 2:
                self.submit_event(str(args[0]), str(args[1]), kwargs.get("meta"))
                return
        except Exception as e:
            logger.error(f"[ANALYST] process_incoming_data failed: {e}")

    def _worker_loop(self) -> None:
        logger.info("[ANALYST] Worker started. Waiting for data...")
        try:
            _mirror_background_event(
                "[ANALYST_WORKER_START]",
                "analyst",
                "worker_start",
            )
        except Exception:
            pass
        while self.active:
            try:
                task = self.queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._process_task(task)
            except Exception as e:
                logger.error(f"[ANALYST] Error in worker: {e}")
                try:
                    _mirror_background_event(
                        f"[ANALYST_WORKER_ERROR] {e}",
                        "analyst",
                        "worker_error",
                    )
                except Exception:
                    pass
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass

    def _process_task(self, task: Dict[str, Any]) -> None:
        content = str(task.get("content", ""))
        source = str(task.get("source", ""))

        sentiment = "neutral"
        keywords = [w for w in content.split() if len(w) > 6 and w.istitle()]

        insight = {
            "timestamp": task.get("ts"),
            "source_type": source,
            "sentiment": sentiment,
            "extracted_keys": list(set(keywords))[:10],
            "snippet": content[:200].replace("\n", " "),
            "full_content_hash": hash(content),
        }

        self._save_insight(insight)
        try:
            _mirror_background_event(
                f"[ANALYST_INSIGHT] source={source} snippet={insight.get('snippet','')}",
                "analyst",
                "insight",
            )
        except Exception:
            pass

    def _save_insight(self, insight: Dict[str, Any]) -> None:
        path = "data/memory/deep_insights.jsonl"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(insight, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[ANALYST] Save failed: {e}")
            try:
                _mirror_background_event(
                    f"[ANALYST_SAVE_ERROR] {e}",
                    "analyst",
                    "save_error",
                )
            except Exception:
                pass


analyst = EsterAnalyst()
analyst_unit = analyst