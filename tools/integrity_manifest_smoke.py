# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory, agent_runner
from modules.runtime import drift_quarantine, integrity_verifier
from modules.thinking import action_registry
from tools.build_integrity_manifest import DEFAULT_RELPATHS, build_manifest


def _copy_relpaths(src_root: Path, dst_root: Path, relpaths: list[str]) -> None:
    for rel in relpaths:
        src = (src_root / rel).resolve()
        dst = (dst_root / rel).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_integrity_manifest_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    manifest_root = (tmp_root / "manifest_root").resolve()
    manifest_path = (tmp_root / "manifest_root" / "data" / "integrity" / "template_capability_SHA256SUMS.json").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    _copy_relpaths(ROOT, manifest_root, list(DEFAULT_RELPATHS))
    build_rep = build_manifest(root=manifest_root, out_path=manifest_path, relpaths=list(DEFAULT_RELPATHS))

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
        "ESTER_INTEGRITY_MANIFEST_PATH",
        "ESTER_INTEGRITY_TTL_SEC",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_INTEGRITY_MANIFEST_PATH"] = str(manifest_path)
    os.environ["ESTER_INTEGRITY_TTL_SEC"] = "1"

    try:
        verify_ok = integrity_verifier.verify_manifest()
        create = agent_factory.create_agent(
            {
                "name": "agent_integrity_manifest_smoke",
                "goal": "integrity manifest smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.integrity_manifest_smoke",
                "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 200},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(create.get("agent_id") or "")

        enqueue_before = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "manifest_ok",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "integrity_manifest_before",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok.txt", "content": "ok"}}],
                },
            },
        )

        tamper_path = (manifest_root / "modules" / "garage" / "templates" / "pack_v1.py").resolve()
        tamper_path.write_text(tamper_path.read_text(encoding="utf-8") + "\n# integrity smoke tamper\n", encoding="utf-8")
        time.sleep(1.2)
        verify_tampered = integrity_verifier.verify_manifest()

        enqueue_after = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "manifest_tampered",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "integrity_manifest_after",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "x.txt", "content": "x"}}],
                },
            },
        )
        run_after = agent_runner.run_once(
            agent_id,
            {"schema": "ester.plan.v1", "plan_id": "integrity_manifest_run", "steps": []},
            {"chain_id": "chain_integrity_manifest_run"},
        )
        q_after = drift_quarantine.is_quarantined(agent_id)

        ok = (
            bool(build_rep.get("ok"))
            and bool(verify_ok.get("manifest_ok"))
            and bool(create.get("ok"))
            and bool(enqueue_before.get("ok"))
            and (not bool(verify_tampered.get("manifest_ok")))
            and int(verify_tampered.get("mismatch_count") or 0) >= 1
            and (not bool(enqueue_after.get("ok")))
            and str(enqueue_after.get("error_code") or "") == "INTEGRITY_TAMPER"
            and (not bool(run_after.get("ok")))
            and str(run_after.get("error_code") or "") in {"INTEGRITY_TAMPER", "INTEGRITY_UNAVAILABLE"}
            and bool(q_after.get("active"))
        )

        out: Dict[str, Any] = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "manifest_path": str(manifest_path),
            "build_manifest": build_rep,
            "verify_ok": verify_ok,
            "verify_tampered": verify_tampered,
            "agent_id": agent_id,
            "enqueue_before": enqueue_before,
            "enqueue_after": enqueue_after,
            "run_after": run_after,
            "q_after": q_after,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
