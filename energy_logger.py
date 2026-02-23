#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
energy_logger.py
Cross-platform energy logger for GPU (nvidia-smi) + optional CPU (Intel RAPL on Linux).

Modes:
  1) sample   : periodically sample watts, write CSV, compute kWh on exit
  2) from-csv : integrate existing CSV (timestamp + watts)
  3) estimate : compute kWh from avg watts * hours * days

Works on:
  - Windows PowerShell 5 (needs Python 3.x, NVIDIA drivers for GPU power)
  - Linux (same; CPU power via RAPL if available)
No third-party dependencies (stdlib only).

Examples:
  # Sample every 2 seconds, until Ctrl+C, save CSV, tariff 0.30 €/kWh
  python energy_logger.py sample --interval 2 --tariff 0.30

  # Sample for 6 hours, output file specified
  python energy_logger.py sample --interval 5 --duration 21600 --out logs/my_run.csv

  # Manual watts (if no nvidia-smi / want wall-meter value)
  python energy_logger.py sample --interval 10 --manual-watts 650 --tariff 0.30

  # Integrate an existing CSV file
  python energy_logger.py from-csv --in logs/my_run.csv --tariff 0.30

  # Quick estimate: 650W 24h/day 30 days
  python energy_logger.py estimate --watts 650 --hours 24 --days 30 --tariff 0.30
"""

import argparse
import csv
import datetime as dt
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from typing import Optional, Tuple, List, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def default_out_path() -> str:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join("logs", f"energy_log_{ts}.csv")


def which_nvidia_smi() -> Optional[str]:
    return shutil.which("nvidia-smi")


def run_nvidia_smi_power(smi_path: str) -> Tuple[Optional[float], str]:
    """
    Returns (gpu_watts_total, note). If error -> (None, note).
    """
    try:
        # Query GPU power draw in W, no units.
        cmd = [smi_path, "--query-gpu=power.draw", "--format=csv,noheader,nounits"]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if p.returncode != 0:
            note = f"nvidia-smi failed: rc={p.returncode}; stderr={p.stderr.strip()[:200]}"
            return None, note

        lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
        if not lines:
            return None, "nvidia-smi returned empty output"
        watts = 0.0
        for ln in lines:
            # Some drivers return "N/A"
            if ln.upper() == "N/A":
                continue
            try:
                watts += float(ln.replace(",", "."))
            except ValueError:
                # ignore bad lines, but note
                continue
        if watts <= 0.0:
            return None, f"nvidia-smi output parsed but watts<=0; raw={lines[:3]}"
        return watts, "gpu_ok"
    except FileNotFoundError:
        return None, "nvidia-smi not found"
    except Exception as e:
        return None, f"nvidia-smi exception: {e!r}"


def list_rapl_energy_files() -> List[str]:
    """
    Linux Intel RAPL energy files (microjoules). Returns list of paths.
    """
    base = "/sys/class/powercap"
    if not os.path.isdir(base):
        return []
    paths = []
    try:
        for entry in os.listdir(base):
            if not entry.startswith("intel-rapl"):
                continue
            d = os.path.join(base, entry)
            efile = os.path.join(d, "energy_uj")
            if os.path.isfile(efile):
                paths.append(efile)
            # also look into subdomains
            try:
                for sub in os.listdir(d):
                    subd = os.path.join(d, sub)
                    efile2 = os.path.join(subd, "energy_uj")
                    if os.path.isfile(efile2):
                        paths.append(efile2)
            except Exception:
                pass
    except Exception:
        return []
    # unique
    return sorted(list(dict.fromkeys(paths)))


def read_energy_uj_sum(rapl_files: List[str]) -> Optional[int]:
    """
    Sum of energy_uj across detected files. Returns int microjoules or None.
    """
    if not rapl_files:
        return None
    total = 0
    try:
        for fp in rapl_files:
            with open(fp, "r", encoding="utf-8") as f:
                s = f.read().strip()
            if not s:
                continue
            total += int(s)
        return total
    except Exception:
        return None


def integrate_trapezoid(samples: List[Dict[str, float]]) -> Tuple[float, float, float]:
    """
    samples: list of {t, watts} where t is epoch seconds (float)
    returns (duration_s, avg_watts, kwh)
    """
    if len(samples) < 2:
        return 0.0, 0.0, 0.0
    energy_wh = 0.0
    w_sum = 0.0
    w_n = 0

    for i in range(1, len(samples)):
        t0 = samples[i-1]["t"]
        t1 = samples[i]["t"]
        w0 = samples[i-1]["watts"]
        w1 = samples[i]["watts"]
        dt_s = max(0.0, t1 - t0)
        if dt_s <= 0:
            continue
        # Trapezoid
        energy_wh += (w0 + w1) / 2.0 * (dt_s / 3600.0)
        w_sum += w1
        w_n += 1

    duration_s = max(0.0, samples[-1]["t"] - samples[0]["t"])
    avg_watts = (w_sum / w_n) if w_n else 0.0
    kwh = energy_wh / 1000.0
    return duration_s, avg_watts, kwh


def money(cost_per_kwh: Optional[float], kwh: float) -> Optional[float]:
    if cost_per_kwh is None:
        return None
    return kwh * cost_per_kwh


def fmt_seconds(sec: float) -> str:
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def cmd_sample(args: argparse.Namespace) -> int:
    out_path = args.out or default_out_path()
    ensure_parent_dir(out_path)

    smi = which_nvidia_smi()
    rapl_files = []
    is_linux = platform.system().lower() == "linux"
    if is_linux and (not args.no_cpu):
        rapl_files = list_rapl_energy_files()

    # Ctrl+C handling
    stop = {"flag": False}

    def _sigint(_signum, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _sigint)

    print(f"[INFO] Mode=sample | interval={args.interval}s | duration={args.duration or 'until Ctrl+C'}")
    print(f"[INFO] Output CSV: {out_path}")
    if args.manual_watts is not None:
        print(f"[INFO] Manual watts override: {args.manual_watts} W (wall-meter mode)")
    else:
        print(f"[INFO] nvidia-smi: {smi or 'NOT FOUND'}")
    if is_linux and (not args.no_cpu):
        print(f"[INFO] RAPL CPU files: {len(rapl_files)} detected")
    else:
        if args.no_cpu:
            print("[INFO] CPU power: disabled")
        elif not is_linux:
            print("[INFO] CPU power: not available on this OS (Windows/macOS) via stdlib")
        else:
            print("[INFO] CPU power: no RAPL found")

    header = [
        "timestamp_iso",
        "t_epoch",
        "gpu_watts_total",
        "cpu_watts_est",
        "total_watts",
        "note",
    ]

    samples = []
    last_rapl_uj = read_energy_uj_sum(rapl_files) if rapl_files else None
    last_t = time.time()
    last_total_w = None

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)

        start_t = time.time()
        while True:
            now_t = time.time()
            if args.duration is not None and (now_t - start_t) >= args.duration:
                break
            if stop["flag"]:
                break

            dt_s = max(1e-6, now_t - last_t)

            note_parts = []

            # GPU
            if args.manual_watts is not None:
                gpu_watts = float(args.manual_watts)
                note_parts.append("manual_watts")
            else:
                if smi:
                    gw, gn = run_nvidia_smi_power(smi)
                    if gw is None:
                        gpu_watts = 0.0
                        note_parts.append(gn)
                    else:
                        gpu_watts = float(gw)
                else:
                    gpu_watts = 0.0
                    note_parts.append("nvidia-smi not found")

            # CPU (Linux RAPL)
            cpu_watts = None
            if rapl_files:
                cur_rapl_uj = read_energy_uj_sum(rapl_files)
                if cur_rapl_uj is not None and last_rapl_uj is not None and cur_rapl_uj >= last_rapl_uj:
                    delta_uj = cur_rapl_uj - last_rapl_uj
                    delta_j = delta_uj / 1e6
                    cpu_watts = delta_j / dt_s
                    last_rapl_uj = cur_rapl_uj
                    note_parts.append("cpu_rapl_ok")
                else:
                    note_parts.append("cpu_rapl_na")

            total_watts = gpu_watts + (cpu_watts if cpu_watts is not None else 0.0)

            row = [
                iso_now(),
                f"{now_t:.3f}",
                f"{gpu_watts:.2f}",
                "" if cpu_watts is None else f"{cpu_watts:.2f}",
                f"{total_watts:.2f}",
                ";".join(note_parts)[:200],
            ]
            w.writerow(row)
            f.flush()

            # Keep for integration
            samples.append({"t": now_t, "watts": total_watts})

            # Print status
            if last_total_w is None:
                delta = 0.0
            else:
                delta = total_watts - last_total_w
            last_total_w = total_watts

            msg = f"[{row[0]}] total={total_watts:8.2f} W (gpu={gpu_watts:7.2f} W"
            if cpu_watts is not None:
                msg += f", cpu~{cpu_watts:7.2f} W"
            msg += f")  Δ{delta:+.1f}W"
            if args.tariff is not None:
                # naive live cost rate (€/h) = kW * €/kWh
                eur_per_h = (total_watts / 1000.0) * args.tariff
                msg += f"  ~{eur_per_h:.3f} €/h"
            print(msg)

            time.sleep(max(0.0, args.interval))

    # Summary
    duration_s, avg_w, kwh = integrate_trapezoid(samples)
    print("\n=== SUMMARY ===")
    print(f"Samples: {len(samples)}")
    print(f"Duration: {fmt_seconds(duration_s)}")
    print(f"Average power: {avg_w:.2f} W")
    print(f"Energy: {kwh:.4f} kWh")
    if args.tariff is not None:
        eur = money(args.tariff, kwh)
        print(f"Cost @ {args.tariff:.4f} €/kWh: {eur:.2f} €")
    print(f"CSV saved: {out_path}")
    return 0


def cmd_from_csv(args: argparse.Namespace) -> int:
    in_path = args.in_path
    if not os.path.isfile(in_path):
        print(f"[ERROR] Input CSV not found: {in_path}", file=sys.stderr)
        return 2

    rows = []
    with open(in_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if len(rows) < 2:
        print("[ERROR] Not enough rows to integrate.", file=sys.stderr)
        return 2

    # Detect timestamp and watts columns
    # Supported:
    #   - t_epoch + total_watts (our own format)
    #   - timestamp + watts
    #   - time + watts
    def pick(d: dict, keys: List[str]) -> Optional[str]:
        for k in keys:
            if k in d and d[k] not in (None, ""):
                return d[k]
        return None

    samples = []
    for r in rows:
        t_s = pick(r, ["t_epoch", "t", "time", "timestamp"])
        w_s = pick(r, ["total_watts", "watts", "power_w", "power"])
        if t_s is None or w_s is None:
            continue
        try:
            t = float(str(t_s).replace(",", "."))
            wv = float(str(w_s).replace(",", "."))
        except ValueError:
            continue
        samples.append({"t": t, "watts": wv})

    if len(samples) < 2:
        print("[ERROR] Could not parse timestamp/watts columns.", file=sys.stderr)
        return 2

    duration_s, avg_w, kwh = integrate_trapezoid(samples)
    print("=== CSV INTEGRATION ===")
    print(f"File: {in_path}")
    print(f"Samples parsed: {len(samples)}")
    print(f"Duration: {fmt_seconds(duration_s)}")
    print(f"Average power: {avg_w:.2f} W")
    print(f"Energy: {kwh:.4f} kWh")
    if args.tariff is not None:
        eur = money(args.tariff, kwh)
        print(f"Cost @ {args.tariff:.4f} €/kWh: {eur:.2f} €")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    watts = float(args.watts)
    hours = float(args.hours)
    days = float(args.days)
    kwh = (watts / 1000.0) * hours * days
    print("=== ESTIMATE ===")
    print(f"Avg power: {watts:.2f} W")
    print(f"Hours/day: {hours:.2f}")
    print(f"Days: {days:.2f}")
    print(f"Energy: {kwh:.4f} kWh")
    if args.tariff is not None:
        eur = money(args.tariff, kwh)
        print(f"Cost @ {args.tariff:.4f} €/kWh: {eur:.2f} €")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Energy logger (GPU via nvidia-smi + optional CPU via RAPL on Linux).")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("sample", help="Sample watts periodically, write CSV, integrate on exit.")
    ps.add_argument("--interval", type=float, default=2.0, help="Sampling interval in seconds.")
    ps.add_argument("--duration", type=float, default=None, help="Stop after N seconds (default: run until Ctrl+C).")
    ps.add_argument("--out", dest="out", default=None, help="Output CSV path (default: logs/energy_log_*.csv).")
    ps.add_argument("--tariff", type=float, default=None, help="Optional cost in EUR per kWh.")
    ps.add_argument("--manual-watts", type=float, default=None, help="Override measured watts with a constant value.")
    ps.add_argument("--no-cpu", action="store_true", help="Disable CPU power (Linux RAPL).")

    pc = sub.add_parser("from-csv", help="Integrate an existing CSV with timestamp+watts columns.")
    pc.add_argument("--in", dest="in_path", required=True, help="Input CSV path.")
    pc.add_argument("--tariff", type=float, default=None, help="Optional cost in EUR per kWh.")

    pe = sub.add_parser("estimate", help="Quick estimate from avg watts * hours/day * days.")
    pe.add_argument("--watts", type=float, required=True, help="Average watts.")
    pe.add_argument("--hours", type=float, required=True, help="Hours per day.")
    pe.add_argument("--days", type=float, required=True, help="Number of days.")
    pe.add_argument("--tariff", type=float, default=None, help="Optional cost in EUR per kWh.")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "sample":
        return cmd_sample(args)
    if args.cmd == "from-csv":
        return cmd_from_csv(args)
    if args.cmd == "estimate":
        return cmd_estimate(args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())