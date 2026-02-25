# -*- coding: utf-8 -*-
from __future__ import annotations

"""modules/listeners/lan_jobs_runner.py - fonovyy runner lokalnoy ocheredi LAN‑zadach (pull/offer).

Problemy iskhodnika:
- sloman blok `if __name__ == "__main__":` → SyntaxError: expected an indented block. fileciteturn13file0
- AB_MODE byl globalnyy i konfliktuet s drugimi “B” v sisteme.
- obrabotka ocheredi: tolko odna zadacha za tik, bez batch/drain; mark_done mog upast, esli net job["id"].
- tselevaya papka pull byla obschey (peretirat dannye raznykh peer).
- slabaya nablyudaemost: net took_ms, net akkuratnogo otcheta, net jitter dlya intervala.

What was done:
- restore otstupy i __main__.
- AB dlya rannera neymspeysnyy:
    ESTER_LAN_JOBS_AB_MODE → LAN_JOBS_AB_MODE → AB_MODE (fallback).
- batch/drain: za tik mozhno vypolnit N zadach (po umolchaniyu 1), chtoby ochered ne “zalipala”.
- pull kladet v otdelnuyu papku na peer: base_dir/replica/from_peer/<peer_safe>/
- report out expandedn: took_ms, bytes_in/bytes_out, mode, action.
- jitter k sleep, chtoby neskolko rannerov ne “schelkali” sinkhronno.
- vsya markirovka zaversheniya best‑effort: dazhe esli mark_done slomalsya, ranner zhivet dalshe.

ENV (optional):
- LAN_JOBS_INTERVAL=15
- LAN_JOBS_MAX_PER_TICK=1
- LAN_JOBS_JITTER=0.10 (dolya, 0..0.5)
- ESTER_LAN_JOBS_AB_MODE=A|B (or LAN_JOBS_AB_MODE; fallback AB_MODE)
- LAN_JOBS_PULL_TARGET_SUBDIR=replica/from_peer

MOSTY:
- Yavnyy: kibernetika ↔ ekspluatatsiya: ochered → deystvie → otchet → mark_done.
- Skrytyy #1: infoteoriya ↔ ustoychivost: batch+backoff/jitter snizhayut “pulsatsii” i uvelichivayut propusknuyu sposobnost.
- Skrytyy #2: inzheneriya ↔ suverennost: neymspeysnyy AB = lokalnaya privilegiya na setevye deystviya.

ZEMNOY ABZATs:
Eto “motorchik konveyera”: vazhno, chtoby on ne ostanavlivalsya iz‑za odnoy krivoy zadachi i ne putal yaschiki raznykh postavschikov
(poetomu otdelnye papki po peer i best‑effort zavershenie)."""

import argparse
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# upravlenie ocheredyu
from modules.lan.job_queue import pop_for_run, mark_done  # type: ignore
# replika
from modules.replica.portable_sync_settings import load_sync_settings  # type: ignore
from modules.replica.portable_sync import index_current, set_offer, pull_from_peer  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)


def _ab_mode() -> str:
    for key in ("ESTER_LAN_JOBS_AB_MODE", "LAN_JOBS_AB_MODE", "AB_MODE"):
        v = os.getenv(key)
        if v is None:
            continue
        v = str(v).strip().upper()
        if v in ("A", "B"):
            return v
    return "A"


def _env_int(key: str, default: int, min_v: Optional[int] = None, max_v: Optional[int] = None) -> int:
    raw = os.getenv(key)
    try:
        v = int(str(raw).strip()) if raw is not None and str(raw).strip() else int(default)
    except Exception:
        v = int(default)
    if min_v is not None:
        v = max(min_v, v)
    if max_v is not None:
        v = min(max_v, v)
    return v


def _env_float(key: str, default: float, min_v: Optional[float] = None, max_v: Optional[float] = None) -> float:
    raw = os.getenv(key)
    try:
        v = float(str(raw).strip()) if raw is not None and str(raw).strip() else float(default)
    except Exception:
        v = float(default)
    if min_v is not None:
        v = max(min_v, v)
    if max_v is not None:
        v = min(max_v, v)
    return v


def _safe_peer(peer: str) -> str:
    peer = (peer or "").strip()
    if not peer:
        return "peer"
    peer = re.sub(r"[^a-zA-Z0-9._-]+", "_", peer)[:64].strip("_")
    return peer or "peer"


@dataclass(frozen=True)
class RunnerConfig:
    interval_sec: int = 15
    max_per_tick: int = 1
    jitter_frac: float = 0.10
    pull_target_subdir: str = "replica/from_peer"

    @staticmethod
    def from_env() -> "RunnerConfig":
        interval = _env_int("LAN_JOBS_INTERVAL", 15, min_v=1, max_v=3600)
        max_per = _env_int("LAN_JOBS_MAX_PER_TICK", 1, min_v=1, max_v=100)
        jitter = _env_float("LAN_JOBS_JITTER", 0.10, min_v=0.0, max_v=0.5)
        subdir = str(os.getenv("LAN_JOBS_PULL_TARGET_SUBDIR", "replica/from_peer")).strip() or "replica/from_peer"
        return RunnerConfig(interval_sec=interval, max_per_tick=max_per, jitter_frac=jitter, pull_target_subdir=subdir)


class LanJobsRunner:
    def __init__(self, cfg: Optional[RunnerConfig] = None):
        self.cfg = cfg or RunnerConfig.from_env()

    def run_batch(self, ab_override: Optional[str] = None) -> int:
        """Executes up to sfg.max_per_tisk tasks (if any).
        Returns the number of completed (including dry runes)."""
        ab = (ab_override or _ab_mode()).strip().upper()
        done = 0
        for _ in range(self.cfg.max_per_tick):
            job = None
            try:
                job = pop_for_run()
            except Exception as e:
                log.exception("pop_for_run failed: %s", e)
                break

            if not job:
                break

            self._handle_job(job, ab=ab)
            done += 1

        return done

    def _handle_job(self, job: Dict[str, Any], ab: str) -> None:
        job_id = job.get("id") or job.get("_id") or job.get("job_id")
        job_type = str(job.get("type") or "").strip()

        t0 = time.time()
        ok = False
        out: Dict[str, Any] = {
            "mode": "dry" if ab != "B" else "real",
            "job_type": job_type or None,
        }

        try:
            if job_type == "offer":
                ok, rep = self._do_offer(ab=ab)
                out.update(rep)

            elif job_type == "pull":
                peer = str((job.get("args") or {}).get("peer") or "").strip()
                ok, rep = self._do_pull(peer=peer, ab=ab)
                out.update(rep)

            else:
                ok = False
                out.update({"error": "bad-type", "bytes_in": 0, "bytes_out": 0})

        except Exception as e:
            ok = False
            out.update({"error": str(e), "bytes_in": 0, "bytes_out": 0})

        out["took_ms"] = int((time.time() - t0) * 1000)

        # mark_done best-effort
        try:
            if job_id is not None:
                mark_done(job_id, ok, out)
            else:
                log.warning("Job without id; cannot mark_done. job=%r out=%r", job, out)
        except Exception as e:
            log.exception("mark_done failed: %s (job_id=%r)", e, job_id)

    def _do_offer(self, ab: str) -> Tuple[bool, Dict[str, Any]]:
        s = load_sync_settings() or {}
        base_dir = str(s.get("base_dir") or ".")
        cas_dir = str(s.get("cas_dir") or "")
        block_mb = int(s.get("block_mb") or 4)

        if ab != "B":
            return True, {"action": "offer", "dry": True, "bytes_in": 0, "bytes_out": 0}

        man = index_current(base_dir, cas_dir, block_mb)
        rep = set_offer(man) or {}
        ok = bool(rep.get("ok", True))

        return ok, {
            "action": "offer",
            "version": rep.get("version"),
            "blocks": int(rep.get("blocks", 0) or 0),
            "bytes_in": 0,
            "bytes_out": int(rep.get("bytes_out", 0) or 0),
        }

    def _do_pull(self, peer: str, ab: str) -> Tuple[bool, Dict[str, Any]]:
        s = load_sync_settings() or {}
        cas_dir = str(s.get("cas_dir") or "")
        base_dir = Path(str(s.get("base_dir") or ".")).expanduser()

        if not peer:
            return False, {"action": "pull", "error": "no-peer", "bytes_in": 0, "bytes_out": 0}

        target = base_dir / self.cfg.pull_target_subdir / _safe_peer(peer)
        target_str = str(target)

        if ab != "B":
            return True, {"action": "pull", "peer": peer, "dry": True, "target": target_str, "bytes_in": 0, "bytes_out": 0}

        rep = pull_from_peer(peer, cas_dir, target_str, token=str(s.get("token", "")))
        ok = bool(rep.get("ok"))
        fetched = int(rep.get("fetched", 0) or 0)
        block_sz = max(1, int(s.get("block_mb", 4))) * 1024 * 1024

        # if portable_sync is returned, beat it - we use it, otherwise it evaluates
        bytes_in = int(rep.get("bytes_in", 0) or rep.get("bytes", 0) or (fetched * block_sz))

        return ok, {
            "action": "pull",
            "peer": peer,
            "target": target_str,
            "version": rep.get("version"),
            "fetched": fetched,
            "bytes_in": bytes_in,
            "bytes_out": 0,
        }

    def sleep_interval(self) -> None:
        base = float(self.cfg.interval_sec)
        j = base * float(self.cfg.jitter_frac)
        sleep_s = base if j <= 0 else max(0.2, base + (2 * (os.urandom(1)[0] / 255.0) - 1) * j)
        time.sleep(sleep_s)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN jobs runner")
    ap.add_argument("--loop", action="store_true", help="Run in an endless loop.")
    ap.add_argument("--interval", type=int, default=0, help="Interval mezhdu tikami, sek (overrides ENV).")
    ap.add_argument("--max-per-tick", type=int, default=0, help="How many tasks maximum per tick (overrides ENV).")
    ap.add_argument("--drain", action="store_true", help="Drain the queue until empty and exit (ignores --interval).")
    ap.add_argument("--ab", type=str, default="", help="Override AB mode for this process: A|B.")
    ap.add_argument("--log-level", type=str, default="", help="DEBUG|INFO|WARNING|ERROR (if run as a script).")
    args = ap.parse_args(argv)

    # local base logger (only if launched directly)
    lvl = (args.log_level or os.getenv("LAN_JOBS_LOG_LEVEL") or "").strip().upper()
    if lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        logging.basicConfig(level=getattr(logging, lvl))

    cfg = RunnerConfig.from_env()
    if args.interval and args.interval > 0:
        cfg = RunnerConfig(interval_sec=max(1, int(args.interval)), max_per_tick=cfg.max_per_tick, jitter_frac=cfg.jitter_frac, pull_target_subdir=cfg.pull_target_subdir)
    if args.max_per_tick and args.max_per_tick > 0:
        cfg = RunnerConfig(interval_sec=cfg.interval_sec, max_per_tick=max(1, int(args.max_per_tick)), jitter_frac=cfg.jitter_frac, pull_target_subdir=cfg.pull_target_subdir)

    ab_override = (args.ab or "").strip().upper()
    if ab_override not in ("A", "B"):
        ab_override = ""

    runner = LanJobsRunner(cfg)

    try:
        if args.drain:
            total = 0
            while True:
                n = runner.run_batch(ab_override=ab_override or None)
                total += n
                if n == 0:
                    break
            log.info("Drain done. total_jobs=%s", total)
            return 0

        while True:
            runner.run_batch(ab_override=ab_override or None)
            if not args.loop:
                break
            runner.sleep_interval()

    except KeyboardInterrupt:
        log.info("LAN jobs runner interrupted by user")
        return 0
    except Exception as e:
        log.exception("LAN jobs runner crashed: %s", e)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())