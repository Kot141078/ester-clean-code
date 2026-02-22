# -*- coding: utf-8 -*-
from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import http.client as _http_client
import urllib.request as _urllib_request


class NetworkDenyError(RuntimeError):
    def __init__(self, code: str, host: str, port: int, detail: str = "") -> None:
        self.code = str(code or "NET_OUTBOUND_DENIED")
        self.host = str(host or "")
        self.port = int(port or 0)
        self.detail = str(detail or "")
        super().__init__(f"{self.code}:{self.host}:{self.port}:{self.detail}")


_LOCK = threading.RLock()
_INSTALLED = False
_STATE: Dict[str, Any] = {
    "mode": "A",
    "allow_cidrs": ["127.0.0.1/32", "::1/128"],
    "allow_hosts": ["localhost"],
    "deny_count": 0,
    "last_deny": {},
    "internal_errors": 0,
    "rollback_reason": "",
    "log_jsonl": True,
}
_ORIG: Dict[str, Any] = {}


def _truthy(raw: str, default: bool = False) -> bool:
    s = str(raw if raw is not None else ("1" if default else "0")).strip().lower()
    return s in {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _mode_override() -> str:
    raw = str(os.getenv("ESTER_NET_DENY_MODE", "") or "").strip().upper()
    if raw in {"A", "B"}:
        return raw
    return _slot()


def _offline_enabled(policy: Dict[str, Any]) -> bool:
    if "offline" in policy:
        return bool(policy.get("offline"))
    return _truthy(os.getenv("ESTER_OFFLINE", "1"), default=True)


def _split_csv(value: str) -> List[str]:
    return [str(x).strip() for x in str(value or "").split(",") if str(x).strip()]


def _parse_allow_cidrs(policy: Dict[str, Any]) -> List[str]:
    raw = policy.get("allow_cidrs")
    if isinstance(raw, str):
        items = _split_csv(raw)
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        items = _split_csv(os.getenv("ESTER_NET_ALLOW_CIDRS", "127.0.0.1/32,::1/128"))
    out: List[str] = []
    for item in items:
        try:
            ipaddress.ip_network(item, strict=False)
            out.append(item)
        except Exception:
            continue
    if not out:
        out = ["127.0.0.1/32", "::1/128"]
    return out


def _parse_allow_hosts(policy: Dict[str, Any]) -> List[str]:
    raw = policy.get("allow_hosts")
    if isinstance(raw, str):
        items = _split_csv(raw)
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        items = _split_csv(os.getenv("ESTER_NET_ALLOW_HOSTS", "localhost"))
    out = sorted({str(x).strip().lower() for x in items if str(x).strip()})
    if not out:
        out = ["localhost"]
    return out


def _normalize_host(host: Any) -> str:
    s = str(host or "").strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return s.strip().lower()


def _ip_from_host(host: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(host)
    except Exception:
        return None


def _ip_allowed(ip_obj: ipaddress._BaseAddress) -> bool:
    for raw in list(_STATE.get("allow_cidrs") or []):
        try:
            net = ipaddress.ip_network(str(raw), strict=False)
        except Exception:
            continue
        if ip_obj in net:
            return True
    return False


def _resolve_host_ips(host: str, port: int) -> List[str]:
    ips: List[str] = []
    # Resolve before connect; fail-closed if result is not allowed.
    rows = socket.getaddrinfo(host, int(port or 0), type=socket.SOCK_STREAM)
    for row in rows:
        sockaddr = row[4]
        if not isinstance(sockaddr, tuple) or not sockaddr:
            continue
        ip_s = _normalize_host(sockaddr[0])
        if ip_s and ip_s not in ips:
            ips.append(ip_s)
    return ips


def _extract_host_port(address: Any) -> Tuple[str, int]:
    if isinstance(address, tuple) and len(address) >= 2:
        host = _normalize_host(address[0])
        try:
            port = int(address[1] or 0)
        except Exception:
            port = 0
        return host, port
    return "", 0


def _log_path() -> Path:
    raw = str(os.getenv("ESTER_NET_DENY_LOG_PATH", "data/integrity/net_deny.jsonl") or "").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p


def _record_deny(code: str, host: str, port: int, where: str, detail: str = "") -> None:
    row = {
        "ts": int(time.time()),
        "host": str(host or ""),
        "port": int(port or 0),
        "code": str(code or "NET_OUTBOUND_DENIED"),
        "slot": _slot(),
        "where": str(where or ""),
        "chain_id": str(os.getenv("ESTER_CHAIN_ID", "") or ""),
        "detail": str(detail or ""),
    }
    with _LOCK:
        _STATE["deny_count"] = int(_STATE.get("deny_count") or 0) + 1
        _STATE["last_deny"] = dict(row)
        do_log = bool(_STATE.get("log_jsonl"))
    if not do_log:
        return
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _raise_deny(code: str, host: str, port: int, where: str, detail: str = "") -> None:
    _record_deny(code, host, port, where, detail=detail)
    raise NetworkDenyError(code=code, host=host, port=port, detail=detail)


def _rollback_to_a(reason: str) -> None:
    with _LOCK:
        if str(_STATE.get("mode") or "A") != "B":
            return
        _STATE["mode"] = "A"
        _STATE["rollback_reason"] = str(reason or "slot_b_rollback")
    try:
        if "urllib_urlopen" in _ORIG:
            _urllib_request.urlopen = _ORIG["urllib_urlopen"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "http_connect" in _ORIG:
            _http_client.HTTPConnection.connect = _ORIG["http_connect"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "https_connect" in _ORIG:
            _http_client.HTTPSConnection.connect = _ORIG["https_connect"]  # type: ignore[assignment]
    except Exception:
        pass


def _record_internal_error(where: str, exc: BaseException) -> None:
    with _LOCK:
        _STATE["internal_errors"] = int(_STATE.get("internal_errors") or 0) + 1
        errors = int(_STATE.get("internal_errors") or 0)
        mode = str(_STATE.get("mode") or "A")
    limit = max(1, int(os.getenv("ESTER_NET_DENY_FAIL_MAX", "3") or 3))
    if mode == "B" and errors >= limit:
        _rollback_to_a(reason=f"slot_b_internal_error:{where}:{exc.__class__.__name__}")


def _check_allowed(host: str, port: int, where: str) -> None:
    h = _normalize_host(host)
    p = int(port or 0)
    if not h:
        return

    ip_obj = _ip_from_host(h)
    if ip_obj is not None:
        if _ip_allowed(ip_obj):
            return
        _raise_deny("NET_OUTBOUND_DENIED", h, p, where, detail="ip_not_allowed")

    allow_hosts = {str(x).strip().lower() for x in list(_STATE.get("allow_hosts") or [])}
    if h in allow_hosts:
        return

    mode = str(_STATE.get("mode") or "A")
    if mode == "B":
        _raise_deny("DNS_NAME_DENIED", h, p, where, detail="host_not_allowlisted")

    # Slot A: resolve name and deny by resolved address before connect.
    try:
        resolved = _resolve_host_ips(h, p)
    except Exception as exc:
        _record_internal_error(where, exc)
        _raise_deny("DNS_RESOLVE_FAILED", h, p, where, detail=str(exc))

    if not resolved:
        _raise_deny("DNS_RESOLVE_FAILED", h, p, where, detail="empty_result")

    for ip_s in resolved:
        ip_res = _ip_from_host(ip_s)
        if ip_res is not None and _ip_allowed(ip_res):
            return
    _raise_deny("NET_OUTBOUND_DENIED", h, p, where, detail=f"resolved:{','.join(resolved[:8])}")


def _guard_target(host: str, port: int, where: str) -> None:
    try:
        _check_allowed(host, port, where)
    except NetworkDenyError:
        raise
    except Exception as exc:
        _record_internal_error(where, exc)
        _raise_deny("NET_GUARD_INTERNAL", _normalize_host(host), int(port or 0), where, detail=str(exc))


def _patch_socket_layer() -> None:
    if "socket_connect" not in _ORIG:
        _ORIG["socket_connect"] = socket.socket.connect
    if "socket_connect_ex" not in _ORIG:
        _ORIG["socket_connect_ex"] = socket.socket.connect_ex
    if "socket_create_connection" not in _ORIG:
        _ORIG["socket_create_connection"] = socket.create_connection

    _orig_connect = _ORIG["socket_connect"]
    _orig_connect_ex = _ORIG["socket_connect_ex"]
    _orig_create_connection = _ORIG["socket_create_connection"]

    def _patched_connect(sock: socket.socket, address: Any) -> Any:
        host, port = _extract_host_port(address)
        if host:
            _guard_target(host, port, "socket.connect")
        return _orig_connect(sock, address)

    def _patched_connect_ex(sock: socket.socket, address: Any) -> Any:
        host, port = _extract_host_port(address)
        if host:
            _guard_target(host, port, "socket.connect_ex")
        return _orig_connect_ex(sock, address)

    def _patched_create_connection(address: Any, timeout: Any = socket._GLOBAL_DEFAULT_TIMEOUT, source_address: Any = None) -> Any:
        host, port = _extract_host_port(address)
        if host:
            _guard_target(host, port, "socket.create_connection")
        return _orig_create_connection(address, timeout=timeout, source_address=source_address)

    socket.socket.connect = _patched_connect  # type: ignore[assignment]
    socket.socket.connect_ex = _patched_connect_ex  # type: ignore[assignment]
    socket.create_connection = _patched_create_connection  # type: ignore[assignment]


def _url_host_port(raw: Any) -> Tuple[str, int]:
    target = ""
    if hasattr(raw, "full_url"):
        target = str(getattr(raw, "full_url") or "")
    else:
        target = str(raw or "")
    parsed = urlparse(target)
    host = _normalize_host(parsed.hostname or "")
    port = int(parsed.port or (443 if str(parsed.scheme).lower() == "https" else 80 if str(parsed.scheme).lower() == "http" else 0))
    return host, port


def _patch_slot_b_extras() -> None:
    if "urllib_urlopen" not in _ORIG:
        _ORIG["urllib_urlopen"] = _urllib_request.urlopen
    if "http_connect" not in _ORIG:
        _ORIG["http_connect"] = _http_client.HTTPConnection.connect
    if "https_connect" not in _ORIG:
        _ORIG["https_connect"] = _http_client.HTTPSConnection.connect

    _orig_urlopen = _ORIG["urllib_urlopen"]
    _orig_http_connect = _ORIG["http_connect"]
    _orig_https_connect = _ORIG["https_connect"]

    def _patched_urlopen(url: Any, data: Any = None, timeout: Any = socket._GLOBAL_DEFAULT_TIMEOUT, *args: Any, **kwargs: Any) -> Any:
        host, port = _url_host_port(url)
        if host:
            _guard_target(host, port, "urllib.request.urlopen")
        return _orig_urlopen(url, data=data, timeout=timeout, *args, **kwargs)

    def _patched_http_connect(conn: _http_client.HTTPConnection) -> Any:
        host = _normalize_host(getattr(conn, "host", ""))
        port = int(getattr(conn, "port", 0) or 0)
        if host:
            _guard_target(host, port, "http.client.HTTPConnection.connect")
        return _orig_http_connect(conn)

    def _patched_https_connect(conn: _http_client.HTTPSConnection) -> Any:
        host = _normalize_host(getattr(conn, "host", ""))
        port = int(getattr(conn, "port", 0) or 0)
        if host:
            _guard_target(host, port, "http.client.HTTPSConnection.connect")
        return _orig_https_connect(conn)

    _urllib_request.urlopen = _patched_urlopen  # type: ignore[assignment]
    _http_client.HTTPConnection.connect = _patched_http_connect  # type: ignore[assignment]
    _http_client.HTTPSConnection.connect = _patched_https_connect  # type: ignore[assignment]


def is_installed() -> bool:
    with _LOCK:
        return bool(_INSTALLED)


def get_stats() -> Dict[str, Any]:
    with _LOCK:
        mode = str(_STATE.get("mode") or "A")
        allow_cidrs = [str(x) for x in list(_STATE.get("allow_cidrs") or [])]
        allow_hosts = [str(x) for x in list(_STATE.get("allow_hosts") or [])]
        deny_count = int(_STATE.get("deny_count") or 0)
        last_deny = dict(_STATE.get("last_deny") or {})
        rollback_reason = str(_STATE.get("rollback_reason") or "")
        internal_errors = int(_STATE.get("internal_errors") or 0)
        installed = bool(_INSTALLED)
    return {
        "installed": installed,
        "mode": mode,
        "allow": {"cidrs": allow_cidrs, "hosts": allow_hosts},
        "allow_cidrs": allow_cidrs,
        "allow_hosts": allow_hosts,
        "deny_count": deny_count,
        "last_deny": last_deny,
        "rollback_reason": rollback_reason,
        "internal_errors": internal_errors,
    }


def install_network_deny(policy: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = dict(policy or {})
    if not _offline_enabled(cfg):
        return get_stats()

    mode = str(cfg.get("mode") or _mode_override() or "A").strip().upper()
    if mode not in {"A", "B"}:
        mode = "A"
    allow_cidrs = _parse_allow_cidrs(cfg)
    allow_hosts = _parse_allow_hosts(cfg)
    log_jsonl = bool(
        cfg.get("log_jsonl")
        if "log_jsonl" in cfg
        else _truthy(os.getenv("ESTER_NET_DENY_LOG_JSONL", "1"), default=True)
    )

    with _LOCK:
        _STATE["allow_cidrs"] = list(allow_cidrs)
        _STATE["allow_hosts"] = list(allow_hosts)
        _STATE["log_jsonl"] = bool(log_jsonl)
        _STATE["internal_errors"] = 0
        _STATE["rollback_reason"] = ""

    _patch_socket_layer()
    with _LOCK:
        global _INSTALLED
        _INSTALLED = True
        _STATE["mode"] = "A"

    if mode == "B":
        try:
            _patch_slot_b_extras()
            with _LOCK:
                _STATE["mode"] = "B"
        except Exception as exc:
            _record_internal_error("install.slot_b", exc)
            _rollback_to_a(reason=f"slot_b_install_failed:{exc.__class__.__name__}")

    return get_stats()


def uninstall_network_deny() -> None:
    with _LOCK:
        global _INSTALLED
        _INSTALLED = False
        _STATE["mode"] = "A"
        _STATE["rollback_reason"] = ""
        _STATE["internal_errors"] = 0

    try:
        if "socket_connect" in _ORIG:
            socket.socket.connect = _ORIG["socket_connect"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "socket_connect_ex" in _ORIG:
            socket.socket.connect_ex = _ORIG["socket_connect_ex"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "socket_create_connection" in _ORIG:
            socket.create_connection = _ORIG["socket_create_connection"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "urllib_urlopen" in _ORIG:
            _urllib_request.urlopen = _ORIG["urllib_urlopen"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "http_connect" in _ORIG:
            _http_client.HTTPConnection.connect = _ORIG["http_connect"]  # type: ignore[assignment]
    except Exception:
        pass
    try:
        if "https_connect" in _ORIG:
            _http_client.HTTPSConnection.connect = _ORIG["https_connect"]  # type: ignore[assignment]
    except Exception:
        pass


__all__ = [
    "NetworkDenyError",
    "install_network_deny",
    "uninstall_network_deny",
    "is_installed",
    "get_stats",
]

