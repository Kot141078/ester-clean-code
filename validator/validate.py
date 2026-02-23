# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import platform
import sys
import time
import typing as t
from dataclasses import asdict, dataclass

# VAZhNO: headless-bekend, chtoby ne trebovalsya displey
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class CheckResult:
    name: str
    ok: bool
    info: t.Dict[str, t.Any] | None = None
    error: str | None = None


def _persist_dir(payload: dict) -> str:
    # 1) iz payload.persist_dir, 2) iz ENV PERSIST_DIR, 3) ./vstore
    pd = str(payload.get("persist_dir") or os.getenv("PERSIST_DIR") or "vstore")
    os.makedirs(pd, exist_ok=True)
    os.makedirs(os.path.join(pd, "logs"), exist_ok=True)
    return pd


def _try_import(mod: str) -> CheckResult:
    try:
        __import__(mod)
        return CheckResult(name=f"import:{mod}", ok=True)
    except Exception as e:
        return CheckResult(name=f"import:{mod}", ok=False, error=str(e))


def _torch_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        import torch  # type: ignore

        results.append(CheckResult("torch:installed", True, {"version": torch.__version__}))
        try:
            cuda_ok = torch.cuda.is_available()
            dev_count = torch.cuda.device_count() if cuda_ok else 0
            dev_name = torch.cuda.get_device_name(0) if cuda_ok and dev_count > 0 else None
            results.append(
                CheckResult(
                    "torch:cuda",
                    cuda_ok,
                    {"device_count": dev_count, "device_name": dev_name},
                )
            )
        except Exception as e:
            results.append(CheckResult("torch:cuda", False, error=str(e)))
    except Exception as e:
        results.append(CheckResult("torch:installed", False, error=str(e)))
    return results


def _faiss_check() -> CheckResult:
    try:
        import faiss  # type: ignore

        _ = faiss.IndexFlatL2(4)
        return CheckResult("faiss", True, {"ok": True})
    except Exception as e:
        return CheckResult("faiss", False, error=str(e))


def _sentence_transformers_check() -> CheckResult:
    try:
        import sentence_transformers  # type: ignore

        return CheckResult(
            "sentence-transformers",
            True,
            {"version": sentence_transformers.__version__},
        )
    except Exception as e:
        return CheckResult("sentence-transformers", False, error=str(e))


def _providers_check() -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        from providers.registry import list_providers, ping_provider  # type: ignore

        provs = list_providers()
        results.append(CheckResult("providers:list", True, {"providers": provs}))
        pings = []
        for p in provs:
            try:
                info = ping_provider(p)
                pings.append({p: info})
            except Exception as e:
                pings.append({p: {"ok": False, "error": str(e)}})
        results.append(CheckResult("providers:ping", True, {"results": pings}))
    except Exception as e:
        results.append(CheckResult("providers", False, error=str(e)))
    return results


def _draw_plot(save_path: str, checks: list[CheckResult]) -> None:
    labels = [c.name for c in checks]
    values = [1 if c.ok else 0 for c in checks]

    plt.figure(figsize=(max(6, len(labels) * 0.6), 4))
    plt.bar(labels, values)
    plt.ylim(0, 1.2)
    plt.yticks([0, 1], ["FAIL", "OK"])
    plt.xticks(rotation=30, ha="right")
    plt.title("Ester — Validate Checks")
    plt.tight_layout()
    plt.savefig(save_path, dpi=120)
    plt.close()


def main(payload: dict | None = None) -> dict:
    """
    Osnovnaya funktsiya validatora.
    Vkhod: payload (optsionalno) — mozhno peredat persist_dir, flagi i t.p.
    Vykhod: podrobnyy otchet + put k sgenerirovannomu PNG-grafiku.
    """
    payload = payload or {}
    pd = _persist_dir(payload)
    logs_dir = os.path.join(pd, "logs")
    ts = int(time.time())
    plot_path = os.path.join(logs_dir, f"validate_{ts}.png")

    sys_info = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": os.getcwd(),
        "persist_dir": pd,
    }

    checks: list[CheckResult] = []
    for mod in ["matplotlib", "flask", "requests"]:
        checks.append(_try_import(mod))

    checks.extend(_torch_checks())
    checks.append(_faiss_check())
    checks.append(_sentence_transformers_check())
    checks.extend(_providers_check())

    ok = all(c.ok for c in checks)

    try:
        _draw_plot(plot_path, checks)
        plot_ok = True
    except Exception as e:
        plot_ok = False
        plot_path = ""
        checks.append(CheckResult("plot", False, error=str(e)))

    report = {
        "ok": ok,
        "ts": ts,
        "system": sys_info,
        "checks": [asdict(c) for c in checks],
        "artifacts": {"plot_png": plot_path if plot_ok else None},
    }
    return report


if __name__ == "__main__":
    out = main({})
# print(json.dumps(out, ensure_ascii=False, indent=2))