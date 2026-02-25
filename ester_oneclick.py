#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ester_oneclick.py — single-file safe "one icon" launcher i .env-organayzer dlya Ester.
Author: adaptatsiya pod request Owner.

Zapusk:
  python3 ester_oneclick.py

Tseli:
  - Sdelat odnu ikonku/yarlyk na rabochem stole, zapuskayuschuyu "Ester" lokalno (esli zadan ESTER_START_CMD).
  - Privesti bolshoy .env v udobnyy vid: sektsiya sekretov v beginning, further ostalnoe.
  - Sozdat rezervnye kopii i kartu peremennykh.
  - Prepare instrumenty dlya ruchnogo rasprostraneniya na vashi mashiny (SSH klyuchi, upakovka).

Limitations of safety:
  - NIKAKIKh avtomaticheskikh setevykh skanirovaniy/rasprostraneniy. SCP/SSH - tolko po yavnomu podtverzhdeniyu.
  - NIKAKIKh avtorizatsiy v oblaka bez vashego uchastiya.

Mosty (demand):
  - Yavnyy most: UI (menyu/yarlyk) ↔ Replikatsiya (ruchnye SCP/SSH punkty menyu).
  - Skrytye mosty:
      (1) Anatomiya ↔ PO - struktura ~/.ester modeliruet telo/organy (sm. ZEMNOY).
      (2) Kibernetika ↔ Arkhitektura - kontrolnye tochki/sloty A/B (checkpointing v backup + atomarnye zapisi).

ZEMNOY ABZATs: vnizu fayla (ZEMNOY).

# c=a+b"""
from __future__ import annotations

import getpass
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------- Nastroyki i puti --------------------
USER = os.getenv("USER") or os.getenv("USERNAME") or "user"
HOME = Path.home()

ESTER_HOME = HOME / ".ester"
APP_DIR = ESTER_HOME / "app"
VENV_DIR = ESTER_HOME / "venv"
LOG_DIR = ESTER_HOME / "logs"
BACKUP_DIR = ESTER_HOME / "backups"
SSH_DIR = ESTER_HOME / "ssh"

ENV_PATH_CANDIDATES = [
    Path.cwd() / ".env",
    HOME / ".env",
    Path.cwd() / "env/.env",
    Path.cwd() / "config/.env",
]

# Desktop dir
def _desktop_dir() -> Path:
    sysname = platform.system()
    if sysname == "Windows":
        base = os.environ.get("USERPROFILE") or str(HOME)
        return Path(base) / "Desktop"
    if sysname == "Darwin":
        return HOME / "Desktop"
    return HOME / "Desktop"

DESKTOP_DIR = _desktop_dir()

ICON_NAME = "Esther - Launch"
SCRIPT_PATH = Path(__file__).resolve()


# -------------------- Utility --------------------
def info(msg: str) -> None:
    print(f"[ester] {msg}")


def warn(msg: str) -> None:
    print(f"[ester][warn] {msg}")


def ensure_dirs() -> None:
    for d in (ESTER_HOME, APP_DIR, VENV_DIR, LOG_DIR, BACKUP_DIR, SSH_DIR):
        d.mkdir(parents=True, exist_ok=True)
    info(f"Katalogi gotovy: {ESTER_HOME}")


def _read_text_fallback(path: Path, encodings: Iterable[str] = ("utf-8", "utf-8-sig", "cp1251", "latin-1")) -> str:
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("read_text_fallback failed")


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(content, encoding=encoding)
        tmp_path.replace(path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def find_env() -> Optional[Path]:
    """We are looking for .env from the list of candidates; returns path or None."""
    for p in ENV_PATH_CANDIDATES:
        if p.exists():
            return p
    return None


# -------------------- .env obrabotka --------------------
# Podderzhivaem stroki vida:
#   KEY=value
#   export KEY=value
# Others (comments/empty) are saved as equal.
ENV_KEY_RE = re.compile(r'^\s*(?:export\s+)?([A-Za-z0-9_]+)\s*=')


def parse_env_lines(lines: List[str]) -> List[Tuple[str, Optional[str], str]]:
    """Razbivaet na (kind, key, line). kind: 'kv' ili 'raw'."""
    out: List[Tuple[str, Optional[str], str]] = []
    for ln in lines:
        m = ENV_KEY_RE.match(ln)
        if m:
            out.append(("kv", m.group(1), ln))
        else:
            out.append(("raw", None, ln))
    return out


def is_secret_key(key: str) -> bool:
    """Secrets heuristic - extensible."""
    k = key.upper()
    secret_markers = ("KEY", "SECRET", "TOKEN", "PASS", "PRIVATE", "AWS", "GCP", "DB_", "JWT", "SSH", "API_")
    return any(m in k for m in secret_markers)


def _dedupe_keep_last(items: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
    """items: [(key, line), ...] v poryadke poyavleniya.
    Vozvraschaet:
      - unique_items: tolko poslednee vkhozhdenie kazhdogo klyucha (poryadok - po poslednemu vkhozhdeniyu),
      - dups: key -> [stroki-rannie-vkhozhdeniya] (dlya otcheta)"""
    dups: Dict[str, List[str]] = {}
    seen: Dict[str, int] = {}
    for idx, (k, ln) in enumerate(items):
        if k in seen:
            dups.setdefault(k, []).append(items[seen[k]][1])
        seen[k] = idx
    # collected in order of last appearance
    last_indices = sorted(seen.values())
    unique = [items[i] for i in last_indices]
    return unique, dups


def reorganize_env(src_path: Path, dest_path: Path, backup_dir: Path) -> None:
    """Make a backup, then create a new .env with the secrets section at the beginning.
    We write atomically and save a map of keys/duplicates."""
    if not src_path.exists():
        raise FileNotFoundError(f".env ne nayden po {src_path}")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f".env.backup.{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, backup)
    info(f"Rezerv .env -> {backup}")

    raw_text = _read_text_fallback(src_path)
    raw_lines = raw_text.splitlines()

    parsed = parse_env_lines(raw_lines)

    secrets_kv: List[Tuple[str, str]] = []
    others_kv: List[Tuple[str, str]] = []
    raw_other: List[str] = []

    for kind, key, ln in parsed:
        if kind == "kv" and key:
            if is_secret_key(key):
                secrets_kv.append((key, ln))
            else:
                others_kv.append((key, ln))
        else:
            raw_other.append(ln)

    secrets_unique, secrets_dups = _dedupe_keep_last(secrets_kv)
    others_unique, others_dups = _dedupe_keep_last(others_kv)

    out_lines: List[str] = []
    out_lines.append("# === SECRETS (moved to the beginning; last value wins) ===")
    for _, ln in secrets_unique:
        out_lines.append(ln)
    out_lines.append("# === END SECRETS ===")
    out_lines.append("")
    out_lines.append("# === OTHER CONFIG (last value wins) ===")
    # Important: put equal lines before the config so that comments/empty lines are saved “as background”
    if raw_other:
        out_lines.extend(raw_other)
        if raw_other and raw_other[-1].strip() != "":
            out_lines.append("")
    for _, ln in others_unique:
        out_lines.append(ln)

    content = "\n".join(out_lines).rstrip("\n") + "\n"
    _atomic_write_text(dest_path, content, encoding="utf-8")
    info(f"Novyy .env zapisan v {dest_path}")

    # map variables
    map_path = dest_path.with_suffix(".map.json")
    var_map = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "src": str(src_path),
        "backup": str(backup),
        "secrets": [k for k, _ in secrets_unique],
        "others": [k for k, _ in others_unique],
        "duplicates": {
            "secrets": {k: len(v) + 1 for k, v in secrets_dups.items()},
            "others": {k: len(v) + 1 for k, v in others_dups.items()},
        },
        "notes": "Duplicate keys are collapsed: the last value is retained.",
    }
    _atomic_write_text(map_path, json.dumps(var_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    info(f"Karta peremennykh -> {map_path}")


def _dotenv_to_env_dict(dotenv_text: str) -> Dict[str, str]:
    """Mini-parser .env: we take only simple KEY=VALUE.
    - we do not perform substitutions
    - we do not execute the shell"""
    env: Dict[str, str] = {}
    for ln in dotenv_text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = ENV_KEY_RE.match(ln)
        if not m:
            continue
        key = m.group(1)
        # we separate everything after ъ=ь as value
        _, _, v = ln.partition("=")
        v = v.strip()
        # snimaem prostye kavychki
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        env[key] = v
    return env


def _write_env_example(src_env_path: Path, out_path: Path) -> None:
    txt = _read_text_fallback(src_env_path)
    lines = txt.splitlines()
    out: List[str] = []
    for ln in lines:
        m = ENV_KEY_RE.match(ln)
        if m:
            out.append(f"{m.group(1)}=")
        else:
            out.append(ln)
    _atomic_write_text(out_path, "\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    info(f".env.example zapisan v {out_path}")


# -------------------- Yarlyk / ikonka --------------------
def make_desktop_shortcut(python_path: Optional[str] = None) -> Optional[Path]:
    """Sozdaet yarlyk na rabochem stole, kotoryy zapuskaet etot skript v terminale.

    Linux: .desktop (Terminal=true) — work on bolshinstve DE bez privyazki k gnome-terminal.
    macOS: .command (ispolnyaemyy)
    Windows: .cmd + .vbs (vbs zapuskaet cmd v otdelnom okne)"""
    ensure_dirs()
    exe = python_path or sys.executable
    script_full = SCRIPT_PATH
    desktop = DESKTOP_DIR
    desktop.mkdir(parents=True, exist_ok=True)

    sysname = platform.system()
    if sysname == "Linux":
        desktop_file = desktop / "ester-start.desktop"
        content = textwrap.dedent(f"""\
            [Desktop Entry]
            Type=Application
            Name={ICON_NAME}
            Exec={exe} "{script_full}"
            Icon=utilities-terminal
            Terminal=true
            Categories=Utility;
        """)
        desktop_file.write_text(content, encoding="utf-8")
        desktop_file.chmod(0o755)
        info(f".desktop sozdan: {desktop_file}")
        return desktop_file

    if sysname == "Darwin":
        cmd_file = desktop / "ester-start.command"
        content = textwrap.dedent(f"""\
            #!/bin/bash
            cd "{script_full.parent}"
            "{exe}" "{script_full}"
            read -n 1 -s -r -p "Nazhmite lyubuyu klavishu..."
        """)
        cmd_file.write_text(content, encoding="utf-8")
        cmd_file.chmod(0o755)
        info(f".command sozdan: {cmd_file}")
        return cmd_file

    if sysname == "Windows":
        # Important: cmd loves BOT for UTF-8, otherwise it may cut quotes/paths.
        cmd = desktop / "ester-start.cmd"
        vbs = desktop / "ester-start.vbs"
        cmd_content = "\r\n".join([
            "@echo off",
            "chcp 65001>nul",
            f'cd /d "{script_full.parent}"',
            f'"{exe}" "{script_full}"',
            "pause",
            ""
        ])
        cmd.write_text(cmd_content, encoding="utf-8-sig")
        vbs_content = f'CreateObject("Wscript.Shell").Run Chr(34) & "{cmd}" & Chr(34), 1, false'
        vbs.write_text(vbs_content, encoding="ascii")
        info(f"Windows shortcut created (smd + vvs) on the desktop: ZZF0Z, ZZF1ZZ")
        return cmd

    warn("Platforma ne raspoznana: yarlyk ne sozdan.")
    return None


# -------------------- Upakovka / SCP (ruchnaya) --------------------
def package_ester(output_format: str = "tar") -> Path:
    """Upakovat ~/.ester v arkhiv, vernut put."""
    ensure_dirs()
    ts = time.strftime("%Y%m%d-%H%M%S")
    if output_format == "zip":
        out = BACKUP_DIR / f"ester-{ts}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(ESTER_HOME):
                for f in files:
                    full = Path(root) / f
                    arc = str(full.relative_to(ESTER_HOME))
                    z.write(full, arc)
        info(f"Sozdan arkhiv: {out}")
        return out

    out = BACKUP_DIR / f"ester-{ts}.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.add(str(ESTER_HOME), arcname="ester")
    info(f"Sozdan arkhiv: {out}")
    return out


def scp_send(archive_path: Path) -> bool:
    """Execute special command on the target host only after confirmation."""
    if not archive_path.exists():
        warn("Arkhiv ne nayden.")
        return False

    info("SSP requires that CCX keys be configured between machines.")
    host = input("Target host (IP or DNS) or empty to cancel:").strip()
    if not host:
        info("Otmena.")
        return False

    user = input("User on target machine (Enter=current):").strip() or getpass.getuser()
    path = input("Tselevoy put (naprimer ~/): ").strip() or "~/"
    port = input("Port SSH (Enter=22): ").strip() or "22"

    confirm = input(f"Podtverdite: scp {archive_path} -> {user}@{host}:{path} (yes/NO): ").strip().lower()
    if confirm != "yes":
        info("Otmena SCP.")
        return False

    cmd = ["scp", "-P", port, str(archive_path), f"{user}@{host}:{path}"]
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        warn(f"SSP failed: ZZF0Z")
        return False

    info("SCP uspeshen.")
    return True


# -------------------- SSH keys --------------------
def gen_ssh_keypair(keyname: str = "id_ester") -> Tuple[Path, Path]:
    priv = SSH_DIR / keyname
    pub = SSH_DIR / f"{keyname}.pub"
    if priv.exists() and pub.exists():
        info(f"The keys are already there: ZZF0Z and ZZF1ZZ")
        return priv, pub

    SSH_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["ssh-keygen", "-t", "ed25519", "-f", str(priv), "-N", "", "-C", "ester-oneclick"]
    subprocess.check_call(cmd)
    info(f"SS keys generated: ZZF0Z, ZZF1ZZ")
    return priv, pub


# -------------------- Launching Esther (locally) --------------------
def start_ester() -> None:
    """Runs the command from ESTER_START_CMD.
    No "magic" auto-discovery: only an explicit command.
    Example:
      set ESTER_START_CMD=python run_ester_fixed.py
    or:
      export ESTER_START_CMD="bash tools/run_ester_utf8.sh"
    """
    cmd = os.getenv("ESTER_START_CMD", "").strip()
    if not cmd:
        warn("ESTER_START_CMD ne zadan. Zadayte ego i povtorite (punkt 10).")
        warn('Primer: ESTER_START_CMD="python run_ester_fixed.py"')
        return

    # Let's mix ~/.ester/.env (if any) without breaking the already defined variables.
    child_env = os.environ.copy()
    envf = ESTER_HOME / ".env"
    if envf.exists():
        try:
            d = _dotenv_to_env_dict(_read_text_fallback(envf))
            for k, v in d.items():
                child_env.setdefault(k, v)
        except Exception as e:
            warn(f"Couldn't read ~/.ester/.env (skipping): ZZF0Z")

    info(f"I run (locally): ZZF0Z")
    try:
        # shell=Three - because cmd can be a string with arguments
        subprocess.Popen(cmd, shell=True, cwd=str(SCRIPT_PATH.parent), env=child_env)
        info("The command has been sent to launch (Popen).")
    except Exception as e:
        warn(f"Failed to start: ZZF0Z")


# -------------------- CLI / Menyu --------------------
def print_menu() -> None:
    print("\n=== Ester One-Click — menyu ===")
    print("1) Initialization of directories ~/.ester (create app/ venv/ logs/ backkups/ ssh/)")
    print("2) Process .env (backup + move secrets to the beginning in ~/.ester/.env)")
    print("3) Create a shortcut/icon on the desktop (one-click)")
    print("4) Generate SS keys (d25519) in ~/.ester/ssh/")
    print("5) Upakovat ~/.ester v arkhiv (tar.gz)")
    print("6) Send the archive to your machine via SCP (requires keys; EU confirmation)")
    print("7) Show map .env (~/.ester/.env.map.zsion)")
    print("8) Sozdat env_meta.json i/ili .env.example iz ~/.ester/.env")
    print("i) Manual backup: create an archive and show the path")
    print("10) Launch Esther now (only if ESTER_START_SMD is specified)")
    print("0) Vykhod\n")


def init_deploy() -> None:
    ensure_dirs()
    # Here we deliberately “don’t download” or “install” anything:
    # the maximum is to put a local dump (if you put it nearby yourself).
    local_dump: Optional[Path] = None
    for candidate in ("dump", "ester-dump.zip", "ester-dump.tar.gz"):
        p = Path(candidate)
        if p.exists():
            local_dump = p
            break

    def _is_safe_member(base: Path, member_path: Path) -> bool:
        try:
            base_res = base.resolve()
            m_res = (base / member_path).resolve()
            return str(m_res).startswith(str(base_res))
        except Exception:
            return False

    if local_dump:
        info(f"Nayden lokalnyy damp {local_dump}. Raspakovat v {APP_DIR}? (yes/NO)")
        if input().strip().lower() == "yes":
            try:
                if local_dump.suffix.lower() == ".zip":
                    with zipfile.ZipFile(local_dump, "r") as z:
                        for name in z.namelist():
                            if not _is_safe_member(APP_DIR, Path(name)):
                                raise RuntimeError(f"Unsafe path in zip: {name}")
                        z.extractall(APP_DIR)
                else:
                    with tarfile.open(local_dump, "r:*") as tf:
                        for m in tf.getmembers():
                            if not _is_safe_member(APP_DIR, Path(m.name)):
                                raise RuntimeError(f"Unsafe path in tar: {m.name}")
                        tf.extractall(APP_DIR)
                info("Damp raspakovan.")
            except Exception as e:
                warn(f"Unpacking error: ЗЗФ0З")

    # README
    readme = ESTER_HOME / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Ester One-Click\n"
            "- ~/.ester/.env soderzhit konfig\n"
            "- ESTER_START_CMD specifies the start command for Esther"
            "  primer: ESTER_START_CMD=\"python run_ester_fixed.py\"\n",
            encoding="utf-8",
        )

    info("Initialization complete.")


def handle_env_flow() -> None:
    ensure_dirs()
    env_path = find_env()
    if not env_path:
        warn(".env not found in standard places. Place .env next to the script or in ~/.env")
        if input("Sozdat pustoy ~/.ester/.env.example? (yes/NO): ").strip().lower() == "yes":
            example = ESTER_HOME / ".env.example"
            _atomic_write_text(example, "# EXAMPLE .env\nDEBUG=\n", encoding="utf-8")
            info(f"Primer sozdan: {example}")
        return

    info(f"Nayden .env: {env_path}")
    dest = ESTER_HOME / ".env"

    try:
        reorganize_env(env_path, dest, BACKUP_DIR)
    except Exception as e:
        warn(f"Error processing .env: ЗЗФ0З")
        return

    # .env.example
    try:
        _write_env_example(dest, ESTER_HOME / ".env.example")
    except Exception as e:
        warn(f"Failed to create .env.example: ZZF0Z")


def show_env_map() -> None:
    mapf = ESTER_HOME / ".env.map.json"
    if not mapf.exists():
        warn(".env card not found. First perform .env processing (step 2).")
        return
    print(_read_text_fallback(mapf))


def create_env_meta() -> None:
    envf = ESTER_HOME / ".env"
    if not envf.exists():
        warn("No ~/.ester/.env. First process .env (step 2).")
        return

    txt = _read_text_fallback(envf)
    raw = txt.splitlines()
    keys: List[str] = []
    for ln in raw:
        m = ENV_KEY_RE.match(ln)
        if m:
            keys.append(m.group(1))

    meta = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "keys": keys,
        "count": len(keys),
        "notes": "Keys are listed without values.",
    }
    metaf = ESTER_HOME / "env_meta.json"
    _atomic_write_text(metaf, json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    info(f"env_meta.json -> {metaf}")

    # .env.example (if not present)
    ex = ESTER_HOME / ".env.example"
    if not ex.exists():
        try:
            _write_env_example(envf, ex)
        except Exception as e:
            warn(f"Failed to create .env.example: ZZF0Z")


def main() -> None:
    info("Ester One-Click start.")
    while True:
        print_menu()
        choice = input("Vyberite punkt: ").strip()
        if choice == "1":
            init_deploy()
        elif choice == "2":
            handle_env_flow()
        elif choice == "3":
            make_desktop_shortcut()
        elif choice == "4":
            try:
                gen_ssh_keypair()
            except Exception as e:
                warn(f"Oshibka: {e}")
        elif choice == "5":
            pkg = package_ester()
            info(f"Paket sozdan: {pkg}")
        elif choice == "6":
            pkg = package_ester()
            scp_send(pkg)
        elif choice == "7":
            show_env_map()
        elif choice == "8":
            create_env_meta()
        elif choice == "9":
            info("Manual backup: I create an archive and show the path.")
            p = package_ester()
            info(f"The ZZF0Z archive is ready. Copy it manually where you need it.")
        elif choice == "10":
            start_ester()
        elif choice == "0":
            info("Vykhod.")
            break
        else:
            warn("Nevernyy vybor. Vvedite nomer punkta menyu.")


# -------------------- Zemnoy abzats --------------------
ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Ester - organizm inzhenerno: ~/.ester - ee “telo”, app/ - “organy”, venv/ - “myshtsy”, logs/ - “pamyat”.
Sekrety (klyuchi, tokeny) - kak krov: derzhite ikh otdelno, v legko otkatyvaemom rezerve i pod kontrolem.
Inzhenernaya rekomendatsiya:
  1) Razdelyayte sektsii: secrets + config + runtime. Sekrety - v initial .env i v secure storage (esli est).
  2) Ispolzuyte SSH-klyuchi (ed25519) i dobavlyayte publichnyy klyuch vruchnuyu na kazhduyu svoyu mashinu.
  3) Delayte bekapy atomarno i s “poslednee znachenie pobezhdaet” - eto snimaet polovinu zagadochnykh bagov."""

# -------------------- Launch --------------------
if __name__ == "__main__":
    try:
        ensure_dirs()
        main()
    except KeyboardInterrupt:
        info("Aborted by user - exit.")
    except Exception as e:
        warn(f"Error in the script: ZZF0Z")
        raise
    finally:
        # You can enable printing of the “earthly paragraph” when exiting:
        if os.getenv("ESTER_SHOW_ZEMNOY", "0").strip() == "1":
            print("\n" + ZEMNOY)
