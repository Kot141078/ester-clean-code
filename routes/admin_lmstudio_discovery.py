# -*- coding: utf-8 -*-
"""
Admin LM Studio Discovery - offlayn avtopoisk lokalnykh LM Studio i generatsiya alias.

Most (yavnyy):
- (Kibernetika ↔ Arkhitektura) Pereklyuchatel A/B: A = nablyudaem, B = deystvuem. Upravlyaemost sostoyaniya snizhaet entropiyu izmeneniy.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Dopisyvaem tolko nedostayuschie klyuchi → minimalnaya divergentsiya konfigov → nizhe stoimost soprovozhdeniya.
- (Logika ↔ UX) Razdelenie scan/apply i dry-run po umolchaniyu (A) uproschaet proveryaemost gipotez bez pobochnykh effektov.

Zemnoy abzats:
Marshruty pozvolyayut bez interneta proskanirovat disk/porty, pokazat naydennye modeli/servery LM Studio i
v rezhime B bezopasno dopisat predlozhennye LLM-aliasy v ESTER/portable/recommend.env. Eto oblegchaet podklyuchenie lokalnykh LLM.
"""
from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Dict, List, Tuple

from flask import Blueprint, jsonify, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint(
    "admin_lmstudio_discovery",
    __name__,
    url_prefix="/admin/lmstudio_discovery",
)

# ---------- A/B pereklyuchatel ----------
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()
IS_DRY = AB_MODE != "B"

# ---------- Konstanty ----------
DEFAULT_PORTS = [1234]
EXTRA_PORTS = [
    int(p.strip())
    for p in (os.getenv("LMSTUDIO_EXTRA_PORTS") or "").split(",")
    if p.strip().isdigit()
]
SCAN_PORTS = sorted(set(DEFAULT_PORTS + EXTRA_PORTS))
RECOMMEND_ENV = Path("ESTER/portable/recommend.env")
RECOMMEND_ENV.parent.mkdir(parents=True, exist_ok=True)

# ---------- Utility ----------
def _read_recommend_env(env_path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _append_new_pairs(env_path: Path, new_pairs: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """
    Vozvraschaet (added_keys, skipped_keys). V A-rezhime (dry-run) nichego ne pishet.
    """
    existing = _read_recommend_env(env_path)
    to_add = {k: v for k, v in new_pairs.items() if k not in existing}
    skipped = sorted(set(new_pairs) - set(to_add))

    if IS_DRY:
        return sorted(to_add), skipped

    # Zapis (append) tolko nedostayuschikh klyuchey
    needs_newline = False
    if env_path.exists():
        try:
            txt = env_path.read_text(encoding="utf-8", errors="ignore")
            needs_newline = len(txt) > 0 and not txt.endswith("\n")
        except OSError:
            needs_newline = False

    with env_path.open("a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        for k in sorted(to_add):
            f.write(f"{k}={new_pairs[k]}\n")

    return sorted(to_add), skipped


def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _candidate_dirs() -> List[Path]:
    home = Path.home()
    env_dirs = [
        Path(p.strip())
        for p in (os.getenv("LMSTUDIO_SCAN_DIRS") or "").split(";")
        if p.strip()
    ]
    candidates = [
        # Linux/macOS
        home / ".cache" / "lm-studio" / "models",
        home / ".config" / "LM Studio" / "models",
        # Windows
        home / "AppData" / "Roaming" / "LM Studio" / "models",
        # Inogda kladut ryadom s proektom
        Path.cwd() / "models",
    ]
    return [p for p in env_dirs + candidates if p.exists()]


def _scan_models() -> List[Dict[str, str]]:
    res: List[Dict[str, str]] = []
    for root in _candidate_dirs():
        for p in root.rglob("*.gguf"):
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            res.append({"path": str(p), "size": size})
    # Dedup po puti
    unique: Dict[str, Dict[str, str]] = {}
    for m in res:
        unique[m["path"]] = m
    return list(unique.values())


def _scan_servers() -> List[Dict[str, object]]:
    servers: List[Dict[str, object]] = []
    for port in SCAN_PORTS:
        base = f"http://127.0.0.1:{port}"
        alive = _port_open("127.0.0.1", port)
        # V A-rezhime API ne trogaem (dry). V B mozhno poprobovat sprosit spisok modeley pozzhe.
        servers.append({"base": base, "alive": alive, "models": []})
    return servers


def _propose_aliases(servers: List[Dict[str, object]]) -> Dict[str, str]:
    """
    Generiruem LLM_LOCAL_* → http://127.0.0.1:<port>
    Pervyy «zhivoy» port poluchaet druzhelyubnyy psevdonim, ostalnye - po nomeru.
    """
    aliases: Dict[str, str] = {}
    friendly_given = False
    for srv in servers:
        base = str(srv["base"])
        port = base.rsplit(":", 1)[-1]
        if srv.get("alive") and not friendly_given:
            aliases["LLM_LOCAL_JARVIS"] = base
            friendly_given = True
        key = f"LLM_LOCAL_{port}"
        aliases.setdefault(key, base)
    return aliases


def _discover() -> Dict[str, object]:
    """
    Pytaemsya vospolzovatsya imeyuschimsya modules.lmstudio.discovery (esli est),
    inache ispolzuem lokalnyy skaner vyshe.
    Ozhidaem kontrakt discover(): {"ok": True, "models": [...], "servers": [...]}
    """
    try:
        from modules.lmstudio import discovery as core  # type: ignore
        if hasattr(core, "discover") and callable(core.discover):
            return core.discover()  # type: ignore[no-any-return]
    except Exception:
        pass

    models = _scan_models()
    servers = _scan_servers()
    return {"ok": True, "models": models, "servers": servers}


# ---------- Marshruty ----------
@bp.get("/")
def page_index():
    current_env = _read_recommend_env(RECOMMEND_ENV)
    return render_template(
        "admin_lmstudio_discovery.html",
        ab_mode=AB_MODE,
        recommend_env=current_env,
        scan_result=None,
    )


@bp.post("/scan")
def api_scan():
    result = _discover()
    servers = result.get("servers", [])
    aliases = _propose_aliases(servers)
    return jsonify(
        {
            "ok": True,
            "ab": AB_MODE,
            "servers": servers,
            "models": result.get("models", []),
            "suggested_aliases": aliases,
        }
    )


@bp.post("/apply")
def api_apply():
    result = _discover()
    servers = result.get("servers", [])
    aliases = _propose_aliases(servers)
    added, skipped = _append_new_pairs(RECOMMEND_ENV, aliases)
    return jsonify(
        {
            "ok": True,
            "ab": AB_MODE,
            "applied": not IS_DRY,
            "added": added,
            "skipped_existing": skipped,
            "env_path": str(RECOMMEND_ENV),
        }
    )


# Khuki registratsii dlya raznykh stiley init
def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)


__all__ = ["bp", "register", "init_app"]