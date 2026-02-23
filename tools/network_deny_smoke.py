# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(dict(obj))
    return rows


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_network_deny_smoke_")).resolve()
    log_path = (tmp_root / "data" / "integrity" / "net_deny.jsonl").resolve()

    env_keys = [
        "CLOSED_BOX",
        "WEB_FACTCHECK",
        "ESTER_OFFLINE",
        "ESTER_VOLITION_SLOT",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_NET_DENY_MODE",
        "ESTER_NET_ALLOW_CIDRS",
        "ESTER_NET_ALLOW_HOSTS",
        "ESTER_NET_DENY_LOG_JSONL",
        "ESTER_NET_DENY_LOG_PATH",
        "ESTER_NET_DENY_FAIL_MAX",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["CLOSED_BOX"] = "1"
    os.environ["WEB_FACTCHECK"] = "auto"
    os.environ["ESTER_OFFLINE"] = "1"
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_NET_DENY_MODE"] = "B"
    os.environ["ESTER_NET_ALLOW_CIDRS"] = "127.0.0.1/32,::1/128"
    os.environ["ESTER_NET_ALLOW_HOSTS"] = "localhost"
    os.environ["ESTER_NET_DENY_LOG_JSONL"] = "1"
    os.environ["ESTER_NET_DENY_LOG_PATH"] = str(log_path)
    os.environ["ESTER_NET_DENY_FAIL_MAX"] = "3"

    net_mod = None
    try:
        net_mod = importlib.import_module("modules.runtime.network_deny")
        net_mod.uninstall_network_deny()
        install_rep = net_mod.install_network_deny({"mode": "B"})
        installed = bool(net_mod.is_installed())

        policy_check: Dict[str, Any] = {
            "ok": False,
            "allowed": None,
            "reason": "",
            "code": "",
            "error": "",
        }
        try:
            policy_mod = importlib.import_module("modules.policy.network_policy")
            allowed, reason, code = policy_mod.is_outbound_allowed()
            policy_check = {
                "ok": True,
                "allowed": bool(allowed),
                "reason": str(reason),
                "code": str(code),
                "error": "",
            }
        except Exception as exc:
            policy_check["error"] = str(exc)

        # Allowed loopback connection.
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = int(srv.getsockname()[1])
        accepted = {"ok": False}

        def _server_once() -> None:
            try:
                conn, _addr = srv.accept()
                accepted["ok"] = True
                conn.sendall(b"ok")
                conn.close()
            except Exception:
                pass
            finally:
                try:
                    srv.close()
                except Exception:
                    pass

        th = threading.Thread(target=_server_once, daemon=True)
        th.start()

        local_ok = False
        local_error = ""
        local_payload = ""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5) as c:
                local_payload = str(c.recv(2).decode("utf-8", errors="replace"))
            local_ok = True
        except Exception as exc:
            local_error = str(exc)

        denied = {"caught": False, "type": "", "code": "", "host": "", "port": 0, "detail": ""}
        try:
            socket.create_connection(("1.1.1.1", 80), timeout=1.0)
        except Exception as exc:
            denied["caught"] = True
            denied["type"] = exc.__class__.__name__
            denied["code"] = str(getattr(exc, "code", ""))
            denied["host"] = str(getattr(exc, "host", ""))
            denied["port"] = int(getattr(exc, "port", 0) or 0)
            denied["detail"] = str(getattr(exc, "detail", "") or str(exc))

        stats = dict(net_mod.get_stats() or {})
        rows = _read_jsonl(log_path)

        status_network: Dict[str, Any] = {}
        status_error = ""
        try:
            status_mod = importlib.import_module("modules.runtime.status_iter18")
            status_rep = dict(status_mod.runtime_status() or {})
            status_network = dict(status_rep.get("network") or {})
        except Exception as exc:
            status_error = str(exc)

        ok = (
            bool(install_rep.get("installed"))
            and installed
            and local_ok
            and (local_payload == "ok")
            and bool(accepted.get("ok"))
            and bool(denied.get("caught"))
            and str(denied.get("code") or "") == "NET_OUTBOUND_DENIED"
            and int(stats.get("deny_count") or 0) >= 1
            and bool(rows)
            and bool(policy_check.get("ok"))
            and (policy_check.get("allowed") is False)
            and str(policy_check.get("code") or "") == "NET_OUTBOUND_DENIED"
            and bool(status_network)
            and bool(status_network.get("deny_installed"))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "install": install_rep,
            "local_connect": {
                "ok": local_ok,
                "payload": local_payload,
                "error": local_error,
                "port": port,
                "accepted": bool(accepted.get("ok")),
            },
            "outbound_deny": denied,
            "stats": stats,
            "policy_check": policy_check,
            "log_path": str(log_path),
            "log_rows": len(rows),
            "last_log": rows[-1] if rows else {},
            "runtime_status_network": status_network,
            "runtime_status_error": status_error,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        if net_mod is not None:
            try:
                net_mod.uninstall_network_deny()
            except Exception:
                pass
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
