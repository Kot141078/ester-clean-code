# -*- coding: utf-8 -*-
"""ester_runner.py - edinyy zapuskator (supervisor) dlya dvukh entrypoint'ov:
- app.py (Web Hub)
- run_ester_fixed.py (Telegram/Hive + optional mini-flask)

Oba fayla ostayutsya polnostyu rabotosposobnymi po otdelnosti.
This runner prosto zapuskaet ikh vmeste i akkuratno vedet logi.

Primery:
  python ester_runner.py --both
  python ester_runner.py --web
  python ester_runner.py --telegram
  python ester_runner.py --both --restart"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _print_prefixed(prefix: str, line: str) -> None:
    # Without unnecessary decorations, but it is convenient to distinguish between flows.
    try:
        sys.stdout.write(f"[{prefix}] {line}")
        if not line.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    except Exception:
        # As a last resort - silently.
        pass


def _reader_thread(prefix: str, stream) -> None:
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            _print_prefixed(prefix, line.rstrip("\n"))
    except Exception as e:
        _print_prefixed(prefix, f"(log reader error: {e})")
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _spawn_process(
    name: str,
    script: Path,
    env_overrides: Dict[str, str],
    cwd: Path,
) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(env_overrides)
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [PY, str(script)]
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    if p.stdout:
        threading.Thread(target=_reader_thread, args=(name, p.stdout), daemon=True).start()
    if p.stderr:
        threading.Thread(target=_reader_thread, args=(name + ":ERR", p.stderr), daemon=True).start()

    _print_prefixed("runner", f"started {name}: pid={p.pid} cmd={' '.join(cmd)}")
    return p


def _terminate_process(p: subprocess.Popen, name: str, timeout_sec: float = 8.0) -> None:
    if p.poll() is not None:
        return

    _print_prefixed("runner", f"stopping {name}: pid={p.pid}")

    try:
        # Na Windows terminate() = TerminateProcess, na *nix SIGTERM.
        p.terminate()
    except Exception:
        pass

    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if p.poll() is not None:
            _print_prefixed("runner", f"{name} stopped with code={p.returncode}")
            return
        time.sleep(0.1)

    _print_prefixed("runner", f"{name} did not stop in time — killing")
    try:
        p.kill()
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true", help="start app.py (web)")
    ap.add_argument("--telegram", action="store_true", help="start run_ester_fixed.py (telegram)")
    ap.add_argument("--both", action="store_true", help="start both")
    ap.add_argument("--restart", action="store_true", help="auto-restart crashed process")
    ap.add_argument("--restart-delay", type=float, default=2.0, help="seconds before restart")

    # Web options
    ap.add_argument("--web-host", default=os.getenv("FLASK_HOST", os.getenv("HOST", "127.0.0.1")))
    ap.add_argument("--web-port", default=os.getenv("FLASK_PORT", os.getenv("PORT", "8080")))
    ap.add_argument("--web-debug", default=os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "0")))
    ap.add_argument("--web-no-bg", action="store_true", help="set ESTER_BG_DISABLE=1 for web")

    # Telegram runner options
    ap.add_argument("--tg-closed-box", action="store_true", help="set CLOSED_BOX=1 for telegram runner")
    ap.add_argument("--tg-flask-enable", action="store_true", help="set ESTER_FLASK_ENABLE=1 for telegram runner")
    ap.add_argument("--tg-port", default="8081", help="PORT for telegram runner mini-flask (if enabled)")
    ap.add_argument("--tg-host", default="127.0.0.1", help="HOST for telegram runner mini-flask (if enabled)")

    args = ap.parse_args()

    mode_web = args.web or args.both
    mode_tg = args.telegram or args.both
    if not mode_web and not mode_tg:
        ap.print_help()
        return 2

    app_py = ROOT / "app.py"
    tg_py = ROOT / "run_ester_fixed.py"

    if mode_web and not app_py.exists():
        _print_prefixed("runner", f"ERROR: not found: {app_py}")
        return 1
    if mode_tg and not tg_py.exists():
        _print_prefixed("runner", f"ERROR: not found: {tg_py}")
        return 1

    procs: Dict[str, subprocess.Popen] = {}

    def stop_all():
        # We install in the reverse order so that the “outside” (web) goes last.
        for name in list(procs.keys())[::-1]:
            _terminate_process(procs[name], name)
        procs.clear()

    # Korrektnoe zavershenie po Ctrl+C
    stop_flag = {"stop": False}

    def _sig_handler(_sig, _frame):
        stop_flag["stop"] = True

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    # Startuem
    if mode_web:
        env_web = {
            "FLASK_HOST": str(args.web_host),
            "HOST": str(args.web_host),
            "FLASK_PORT": str(args.web_port),
            "PORT": str(args.web_port),
            "FLASK_DEBUG": str(args.web_debug),
            "DEBUG": str(args.web_debug),
        }
        if args.web_no_bg:
            env_web["ESTER_BG_DISABLE"] = "1"
        procs["web"] = _spawn_process("web", app_py, env_web, ROOT)

    if mode_tg:
        env_tg = {}
        if args.tg_closed_box:
            env_tg["CLOSED_BOX"] = "1"

        # It is better NOT to enable Mini-Flask inside rune_ester_fixed by default,
        # so as not to conflict on the port with the app.
        if args.tg_flask_enable:
            env_tg["ESTER_FLASK_ENABLE"] = "1"
            env_tg["HOST"] = str(args.tg_host)
            env_tg["PORT"] = str(args.tg_port)
        else:
            env_tg["ESTER_FLASK_ENABLE"] = "0"

        procs["telegram"] = _spawn_process("telegram", tg_py, env_tg, ROOT)

    # Petlya supervizora
    try:
        while not stop_flag["stop"]:
            time.sleep(0.3)
            for name, p in list(procs.items()):
                rc = p.poll()
                if rc is None:
                    continue
                _print_prefixed("runner", f"{name} exited with code={rc}")
                if args.restart and not stop_flag["stop"]:
                    _print_prefixed("runner", f"restarting {name} in {args.restart_delay}s")
                    time.sleep(args.restart_delay)
                    if name == "web":
                        env_web = {
                            "FLASK_HOST": str(args.web_host),
                            "HOST": str(args.web_host),
                            "FLASK_PORT": str(args.web_port),
                            "PORT": str(args.web_port),
                            "FLASK_DEBUG": str(args.web_debug),
                            "DEBUG": str(args.web_debug),
                        }
                        if args.web_no_bg:
                            env_web["ESTER_BG_DISABLE"] = "1"
                        procs[name] = _spawn_process("web", app_py, env_web, ROOT)
                    elif name == "telegram":
                        env_tg = {}
                        if args.tg_closed_box:
                            env_tg["CLOSED_BOX"] = "1"
                        if args.tg_flask_enable:
                            env_tg["ESTER_FLASK_ENABLE"] = "1"
                            env_tg["HOST"] = str(args.tg_host)
                            env_tg["PORT"] = str(args.tg_port)
                        else:
                            env_tg["ESTER_FLASK_ENABLE"] = "0"
                        procs[name] = _spawn_process("telegram", tg_py, env_tg, ROOT)
                else:
                    # If the restart is not turned on, one crashes and extinguishes everything.
                    stop_flag["stop"] = True
                    break
    finally:
        stop_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())