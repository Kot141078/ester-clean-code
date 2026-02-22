# -*- coding: utf-8 -*-
"""
IdleEngine — avtonomnyy myslitelnyy tsikl Ester.

Chto delaet odin «tik»:
  1) Smotrit poslednie zapisi pamyati.
  2) Formiruet «chto novogo/chto vazhno» (prostaya evristika).
  3) Delaet lokalnyy QA po klyuchevomu voprosu (bez oblachnykh LLM).
  4) Zapisyvaet mysl/nablyudenie obratno v pamyat (role="system", tag="idle").

Profili nagruzki (ENV/konfiguratsiya i /idle/config):
  mode: off | silent | balanced | max
    off      — potok ostanovlen
    silent   — redkie tiki (raz v 60–120s), minimalnaya vychislitelnaya aktivnost
    balanced — kazhdye 15–30s, srednyaya aktivnost CPU
    max      — kazhdye 3–7s, aktivnaya CPU-nagruzka; pri nalichii GPU — pytaetsya zadeystvovat

  gpu_mode: off | on  (po umolchaniyu off)
    on — probuet cupy/torch dlya matrichnykh umnozheniy; esli ikh net — tikho padaet na CPU

MOSTY:
- Yavnyy: Memory ↔ Mysl — kazhdyy tik chitaet pamyat i pishet «repliku soznaniya».
- Skrytyy 1: Kibernetika (Eshbi) ↔ Regulyatsiya — profili nagruzki ogranichivayut «raznoobrazie» aktivnosti.
- Skrytyy 2: Infoteoriya (Kover–Tomas) ↔ Szhatie — dnevnye mysli svodyatsya v korotkie «smyslovye kody».

ZEMNOY ABZATs:
Eto kak regulyator kholostogo khoda u dvigatelya: poka ty zanyat, Ester «rovno murchit», no po komande mozhet
dat polnyy gaz (i dazhe progret GPU), libo «prisest v ugol» i zhdat.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    # lokalnaya pamyat (nash paket MemoryBoot)
    from modules.memory import get_store
except Exception:  # krayniy sluchay
    from modules.memory.api import get_store  # type: ignore

DATA_DIR = Path(os.getcwd()) / "data"
(ID_DATA := DATA_DIR / "idle").mkdir(parents=True, exist_ok=True)
LOG_PATH = ID_DATA / "idle.log"

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

def _log(msg: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass

@dataclass
class IdleConfig:
    mode: str = "silent"   # off|silent|balanced|max
    gpu_mode: str = "off"  # off|on
    interval_lo: float = 15.0
    interval_hi: float = 30.0

    @staticmethod
    def from_env() -> "IdleConfig":
        m = os.getenv("ESTER_IDLE_MODE", "silent").lower()
        g = os.getenv("ESTER_GPU_MODE", "off").lower()
        if m == "off":
            lo, hi = 60.0, 120.0
        elif m == "silent":
            lo, hi = 60.0, 120.0
        elif m == "balanced":
            lo, hi = 15.0, 30.0
        elif m == "max":
            lo, hi = 3.0, 7.0
        else:
            m, lo, hi = "silent", 60.0, 120.0
        return IdleConfig(mode=m, gpu_mode=g, interval_lo=lo, interval_hi=hi)

# A/B-slot: poka realizatsii odinakovye; kryuchok dlya buduschey podmeny
IDLE_AB = os.getenv("ESTER_IDLE_AB", "A").upper()

class IdleEngine:
    _instance: Optional["IdleEngine"] = None
    _lock = threading.Lock()

    def __init__(self, cfg: IdleConfig):
        self.cfg = cfg
        self._stop = threading.Event()
        self._thr: Optional[threading.Thread] = None
        self._last_tick_ts: float = 0.0
        self._tick_count: int = 0

    # ------------ upravlenie ------------
    @classmethod
    def get(cls) -> "IdleEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = IdleEngine(IdleConfig.from_env())
            return cls._instance

    def configure(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(cfg.get("mode", self.cfg.mode)).lower()
        gpu = str(cfg.get("gpu_mode", self.cfg.gpu_mode)).lower()
        if mode not in ("off", "silent", "balanced", "max"):
            mode = self.cfg.mode
        if gpu not in ("off", "on"):
            gpu = self.cfg.gpu_mode
        self.cfg.mode = mode
        self.cfg.gpu_mode = gpu
        if mode == "off":
            self.cfg.interval_lo, self.cfg.interval_hi = 60.0, 120.0
        elif mode == "silent":
            self.cfg.interval_lo, self.cfg.interval_hi = 60.0, 120.0
        elif mode == "balanced":
            self.cfg.interval_lo, self.cfg.interval_hi = 15.0, 30.0
        else:  # max
            self.cfg.interval_lo, self.cfg.interval_hi = 3.0, 7.0
        return asdict(self.cfg)

    def start(self) -> Dict[str, Any]:
        if self._thr and self._thr.is_alive():
            return self.status()
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, name="EsterIdle", daemon=True)
        self._thr.start()
        _log("IdleEngine started: " + json.dumps(asdict(self.cfg), ensure_ascii=False))
        try:
            _mirror_background_event(
                f"[IDLE_START] mode={self.cfg.mode} gpu={self.cfg.gpu_mode}",
                "idle_engine",
                "start",
            )
        except Exception:
            pass
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self._stop.set()
        if self._thr and self._thr.is_alive():
            self._thr.join(timeout=2.0)
        _log("IdleEngine stopped")
        try:
            _mirror_background_event(
                "[IDLE_STOP]",
                "idle_engine",
                "stop",
            )
        except Exception:
            pass
        return self.status()

    def status(self) -> Dict[str, Any]:
        running = bool(self._thr and self._thr.is_alive())
        return {
            "running": running,
            "mode": self.cfg.mode,
            "gpu_mode": self.cfg.gpu_mode,
            "tick_count": self._tick_count,
            "last_tick_ts": self._last_tick_ts,
            "log_path": str(LOG_PATH),
        }

    # ------------ rabochaya chast ------------
    def _sleep_interval(self) -> float:
        lo, hi = self.cfg.interval_lo, self.cfg.interval_hi
        return random.uniform(lo, hi)

    def _cpu_work(self, scale: int) -> None:
        # legkaya CPU-nagruzka: neskolko matrichnykh peremnozheniy na pure-Python spiskakh
        # (bez numpy, chtoby ne trebovat zavisimostey)
        n = min(100 + 50 * scale, 800)  # upravlyaem razmer
        # sozdaem dve matritsy n x n so znacheniyami 0..1 (redko — 1), peremnozhaem n raz
        a = [[(i * j) % 7 for j in range(n)] for i in range(n)]
        b = [[(i + j) % 5 for j in range(n)] for i in range(n)]
        for _ in range(2):  # nebolshoe chislo iteratsiy, chtoby ne zavisnut
            # klassicheskoe troynoe umnozhenie (O(n^3)) — nagruzka zametnaya
            c = [[0] * n for _ in range(n)]
            for i in range(n):
                ai = a[i]
                ci = c[i]
                for k in range(n):
                    aik = ai[k]
                    bk = b[k]
                    for j in range(n):
                        ci[j] += aik * bk[j]
            # chut izmenim matritsy, chtoby kompilyator ne vybrosil «mertvyy» kod
            a, b = b, c

    def _gpu_try(self, scale: int) -> None:
        if self.cfg.gpu_mode != "on":
            return
        # probuem cupy -> torch; esli net — tikho vykhodim
        try:
            import cupy as cp  # type: ignore
            n = 2048 if scale >= 2 else 1024
            x = cp.random.rand(n, n, dtype=cp.float32)
            y = cp.random.rand(n, n, dtype=cp.float32)
            z = x @ y
            cp.cuda.Stream.null.synchronize()
            _ = float(z[0, 0].item())  # chtenie na khost
            return
        except Exception:
            pass
        try:
            import torch  # type: ignore
            if not torch.cuda.is_available():
                return
            device = torch.device("cuda:0")
            n = 4096 if scale >= 2 else 2048
            x = torch.rand((n, n), device=device)
            y = torch.rand((n, n), device=device)
            z = torch.matmul(x, y)
            torch.cuda.synchronize()
            _ = z[0, 0].item()
        except Exception:
            return

    def _think_one(self) -> None:
        store = get_store()
        recent = store.recent(limit=50)
        if recent:
            last = recent[-1]
            topic = last.get("text", "")[:140]
        else:
            topic = "initsializatsiya sistemy"
        # prostoy «vopros dnya»
        question = f"Chto dalshe delat s: {topic}?"
        qa_res = store.qa(question)
        summary = qa_res.get("answer") or "Mysl sformulirovat ne udalos."
        store.remember({
            "role": "system",
            "text": f"[idle] Vopros: {question} | Nablyudenie: {summary}",
            "tags": ["idle", "thought"],
            "meta": {"mode": self.cfg.mode, "gpu": self.cfg.gpu_mode}
        })
        self._tick_count += 1
        self._last_tick_ts = time.time()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.cfg.mode == "off":
                    time.sleep(1.0)
                    continue
                # mysl
                self._think_one()
                # nagruzka
                scale = {"silent": 0, "balanced": 1, "max": 2}.get(self.cfg.mode, 0)
                if scale > 0:
                    self._cpu_work(scale)
                    self._gpu_try(scale)
            except Exception as e:
                _log("tick error: " + repr(e))
                try:
                    _mirror_background_event(
                        f"[IDLE_TICK_ERROR] {e}",
                        "idle_engine",
                        "tick_error",
                    )
                except Exception:
                    pass
            time.sleep(self._sleep_interval())

# Fasad dlya vneshnego koda/routov
def idle_get() -> IdleEngine:
    return IdleEngine.get()

def idle_start() -> Dict[str, Any]:
    return idle_get().start()

def idle_stop() -> Dict[str, Any]:
    return idle_get().stop()

def idle_status() -> Dict[str, Any]:
    return idle_get().status()

def idle_configure(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return idle_get().configure(cfg)

# c=a+b