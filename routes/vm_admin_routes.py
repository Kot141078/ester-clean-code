# -*- coding: utf-8 -*-
"""
routes/vm_admin_routes.py - edinye pulty upravleniya VM (Hyper-V/KVM) cherez REST.

Ruchki:
  GET  /vm/list
  POST /vm/start    {"name": "..."}
  POST /vm/stop     {"name": "...", "force": false}
  POST /vm/status   {"name": "..."}
  POST /vm/checkpoint {"name":"...","cp":"label"}     # sozdat snapshot
  POST /vm/restore    {"name":"...","cp":"label"}     # otkat k snapshotu

Avto-detekt platformy:
  - Windows: PowerShell + Hyper-V
  - Linux:   virsh (libvirt)

RBAC: rol 'operator' obyazatelna (sm. security.rbac_utils.require_role).

MOSTY:
- Yavnyy: (Arkhitektura ↔ Ekspluatatsiya) pult VM s edinym REST poverkh Hyper-V/KVM.
- Skrytyy #1: (Nadezhnost ↔ Infoteoriya) snapshoty - deshevaya «tochka vozvrata», snizhayut stoimost oshibok.
- Skrytyy #2: (Kibernetika ↔ Volya) bystroknopochnye «start/otkat» dayut ustoychivuyu obratnuyu svyaz pri eksperimente.

ZEMNOY ABZATs:
Start/stop/snapshoty dostupny lokalno i oflayn; vse prozrachno (nikakikh skrytykh demonov).
VM - otdelnaya «korobka» dlya Ester: silnaya izolyatsiya + bystryy otkat.

# c=a+b
"""
from __future__ import annotations
import os, subprocess, json, platform, shlex
from typing import Dict, Any
from flask import Blueprint, jsonify, request
from security.rbac_utils import require_role
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("vm_admin", __name__, url_prefix="/vm")

def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

def _run(cmd: str) -> Dict[str, Any]:
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"code": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}
    except Exception as e:
        return {"code": 999, "out": "", "err": str(e)}

@bp.route("/list", methods=["GET"])
@require_role("operator")
def vm_list():
    if _is_windows():
        res = _run('powershell -NoProfile -Command "Get-VM | Select-Object Name, State | ConvertTo-Json"')
    else:
        res = _run('bash -lc "virsh list --all | tail -n +3 | awk \'{print $2\"|\"$3}\'"')
        if res["code"] == 0:
            items = []
            for line in res["out"].splitlines():
                if not line.strip():
                    continue
                name, state = line.split("|", 1)
                items.append({"Name": name.strip(), "State": state.strip()})
            res["out"] = json.dumps(items)
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 500
    try:
        return jsonify({"ok": True, "items": json.loads(res["out"] or "[]")})
    except Exception:
        return jsonify({"ok": True, "items": []})

@bp.route("/start", methods=["POST"])
@require_role("operator")
def vm_start():
    name = (request.json or {}).get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    res = _run(f'powershell -NoProfile -Command "Start-VM -Name {shlex.quote(name)}"') if _is_windows() \
        else _run(f'bash -lc "virsh start {shlex.quote(name)}"')
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 400
    return jsonify({"ok": True})

@bp.route("/stop", methods=["POST"])
@require_role("operator")
def vm_stop():
    data = request.json or {}
    name = data.get("name", "")
    force = bool(data.get("force", False))
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    if _is_windows():
        cmd = f'Stop-VM -Name {shlex.quote(name)} ' + ('-TurnOff' if force else '')
        res = _run(f'powershell -NoProfile -Command "{cmd}"')
    else:
        cmd = f'virsh {"destroy" if force else "shutdown"} {shlex.quote(name)}'
        res = _run(f'bash -lc "{cmd}"')
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 400
    return jsonify({"ok": True})

@bp.route("/status", methods=["POST"])
@require_role("operator")
def vm_status():
    name = (request.json or {}).get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    if _is_windows():
        res = _run(f'powershell -NoProfile -Command "Get-VM -Name {shlex.quote(name)} | Select-Object Name,State | ConvertTo-Json"')
    else:
        res = _run(f'bash -lc "virsh dominfo {shlex.quote(name)} | sed -n \\"s/^State: \\(.*\\)$/\\1/p\\""')
        if res["code"] == 0:
            res["out"] = json.dumps({"Name": name, "State": (res["out"].strip() or "unknown")})
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 400
    try:
        return jsonify({"ok": True, "info": json.loads(res["out"] or "{}")})
    except Exception:
        return jsonify({"ok": True, "info": {"Name": name}})

@bp.route("/checkpoint", methods=["POST"])
@require_role("operator")
def vm_checkpoint():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    cp = (data.get("cp") or "").strip()
    if not name or not cp:
        return jsonify({"ok": False, "error": "name_cp_required"}), 400
    if _is_windows():
        cmd = f'Checkpoint-VM -Name {shlex.quote(name)} -SnapshotName {shlex.quote(cp)}'
        res = _run(f'powershell -NoProfile -Command "{cmd}"')
    else:
        # libvirt snapshots need XML or simplified call via virsh snapshot-create-as
        cmd = f'virsh snapshot-create-as {shlex.quote(name)} {shlex.quote(cp)}'
        res = _run(f'bash -lc "{cmd}"')
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 400
    return jsonify({"ok": True})

@bp.route("/restore", methods=["POST"])
@require_role("operator")
def vm_restore():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    cp = (data.get("cp") or "").strip()
    if not name or not cp:
        return jsonify({"ok": False, "error": "name_cp_required"}), 400
    if _is_windows():
        cmd = f'Stop-VM -Name {shlex.quote(name)} -TurnOff; Restore-VMSnapshot -VMName {shlex.quote(name)} -Name {shlex.quote(cp)} -Confirm:$false'
        res = _run(f'powershell -NoProfile -Command "{cmd}"')
    else:
        cmd = f'virsh snapshot-revert {shlex.quote(name)} {shlex.quote(cp)}'
        res = _run(f'bash -lc "{cmd}"')
    if res["code"] != 0:
        return jsonify({"ok": False, "error": res["err"]}), 400
    return jsonify({"ok": True})

def register(app):
    app.register_blueprint(bp)