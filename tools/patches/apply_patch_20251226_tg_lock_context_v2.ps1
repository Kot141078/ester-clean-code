Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $root

$py = (Get-Command python -ErrorAction Stop).Source
Write-Host ">>> Using python: $py" -ForegroundColor Cyan

$patchDir = Join-Path $root ".patches"
New-Item -ItemType Directory -Force -Path $patchDir | Out-Null

$patchPy = Join-Path $patchDir "patch_20251226_tg_lock_context_v2.py"

$code = @'
# -*- coding: utf-8 -*-
"""
patch_20251226_tg_lock_context_v2.py

YaVNYY MOST: c=a+b — kogda "b" (model/puller) molchit ili konfliktuet, "a" (interfeys) obyazan skazat pravdu.
SKRYTYE MOSTY:
  - Ashby (requisite variety): raznye klassy oshibok -> raznye soobscheniya, a ne odin yarlyk.
  - Cover&Thomas (limit kanala): odin getUpdates-kanal -> odin vladelets (lock), inache 409.
ZEMNOY ABZATs: kak dva nasosa v odnu trubu dayut kavitatsiyu, tak dva getUpdates-pullera dayut 409 Conflict.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read_text_any(path: Path) -> str:
    b = path.read_bytes()
    try:
        return b.decode("utf-8-sig")
    except Exception:
        return b.decode("utf-8", errors="replace")


def _write_text_utf8(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_chat_api(text: str) -> str:
    if "# [CTX_OVERLOAD_PATCH_V2]" in text:
        return text

    lines = text.splitlines()

    insert_at = None
    for i, l in enumerate(lines):
        if l.strip().startswith("TIME_AWARE") and "=" in l:
            insert_at = i + 1
            break
    if insert_at is None:
        last_import = 0
        for i, l in enumerate(lines):
            if l.startswith("import ") or l.startswith("from "):
                last_import = i
        insert_at = last_import + 1

    helper_lines = """
# [CTX_OVERLOAD_PATCH_V2]
# Explicit BRIDGE: c=a+b - when “b” (model) is silent, “a” (interface) is obliged to speak honestly.
# HIDDEN BRIDGES: (Ashby) variety of errors -> classification; (Carpet&Thomas) channel limit -> explicit overflow message.
# EARTHLY Paragraph: just as muscles have a limit of load (and then cramp), so the context has a limit of tokens.

def _fallback_message(err):
    slot = os.getenv("ESTER_CHATAPI_OVERLOAD_SLOT", "B").strip().upper()
    # Slot A: legacy behavior
    if slot == "A":
        return "Izvini, proizoshla peregruzka konteksta. Povtori vopros."

    e = (err or "").strip()
    el = e.lower()

    ctx_keys = [
        "context length", "maximum context", "max context",
        "context window", "too many tokens", "token limit",
        "n_ctx", "context overflow", "prompt is too long",
        "exceeds the context", "exceeded context",
        "increase n_ctx", "kv cache", "eval: failed",
        "output too large", "length of input",
    ]
    if any(k in el for k in ctx_keys):
        return "Izvini, ya uperlas v limit konteksta (slishkom mnogo teksta/pamyati). Sokrati vopros ili skazhi: «otvet kratko»."

    if "timeout" in el or "timed out" in el:
        return "Izvini, taymaut u modeli. Povtori vopros (luchshe koroche)."
    if any(k in el for k in ["connection", "refused", "unreachable", "reset by peer", "502", "503", "504"]):
        return "Izvini, model seychas nedostupna (soedinenie/shlyuz). Povtori vopros cherez minutu."

    return "Izvini, byl sboy pri otvete. Povtori vopros."
""".strip("\n").splitlines()

    new_lines = lines[:insert_at] + [""] + helper_lines + [""] + lines[insert_at:]
    new_text = "\n".join(new_lines) + "\n"

    # spot replacement of old plug
    new_text = new_text.replace(
        '        answer = "Izvini, proizoshla peregruzka konteksta. Povtori vopros."',
        "        answer = _fallback_message(err)",
    )
    return new_text


def _patch_run_ester_fixed(text: str) -> str:
    if "# [TG_LOCK_PATCH_V2]" in text:
        return text

    marker = "def main():"
    idx = text.find(marker)
    if idx == -1:
        return text

    helper = """
# [TG_LOCK_PATCH_V2]
# Explicit BRIDGE: c=a+b - one bot = one getUpdates channel, otherwise “b” argues with itself.
# HIDDEN BRIDGES: (Ashby) stabilization through limitation of competing circuits; (Kover&Thomas) competitive access -> arbitration through Lutsk.
# EARTHLY Paragraph: just as two water pumps in one pipe give cavitation, so two pollerias in one getUpdates give 409 Conflict.

def _tg_lock_path() -> str:
    p = (os.getenv("ESTER_TG_LOCK_PATH") or "").strip()
    if p:
        return p
    return os.path.join(os.path.dirname(__file__), "data", "locks", "telegram_getupdates.lock")

def _tg_try_acquire_lock():
    # Returns a file handle if lock acquired; otherwise None.
    if str(os.getenv("ESTER_TG_LOCK_DISABLE", "0")).strip().lower() in ("1", "true", "yes", "on"):
        return None
    lock_path = _tg_lock_path()
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    f = open(lock_path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                f.close()
                return None
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                f.close()
                return None

        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return f
    except Exception:
        try:
            f.close()
        except Exception:
            pass
        return None

def _tg_release_lock(f):
    if not f:
        return
    try:
        if os.name == "nt":
            import msvcrt
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
    finally:
        try:
            f.close()
        except Exception:
            pass

""".lstrip()

    new_text = text[:idx] + helper + text[idx:]

    # wrap run_polling in gloss (so as not to catch 409 Conflict)
    new_text = new_text.replace(
        "    app.run_polling(drop_pending_updates=True)",
        "    _tg_lock_f = _tg_try_acquire_lock()\n"
        "    if _tg_lock_f is None and str(os.getenv('ESTER_TG_LOCK_DISABLE','0')).strip().lower() not in ('1','true','yes','on'):\n"
        "        logging.error('[TG] getUpdates lock busy: another bot instance is polling. Stop the other instance or set ESTER_TG_LOCK_DISABLE=1 to bypass.')\n"
        "        return\n"
        "    try:\n"
        "        app.run_polling(drop_pending_updates=True)\n"
        "    finally:\n"
        "        _tg_release_lock(_tg_lock_f)\n"
    )

    return new_text


def _patch_messaging_telegram_adapter(text: str) -> str:
    # turn off Telegram autostart by default (so that app/autoload does not raise getUpdates themselves)
    new = text
    new = new.replace('_env_flag("ESTER_TELEGRAM_ENABLED", "1")', '_env_flag("ESTER_TELEGRAM_ENABLED", "0")')
    new = new.replace('_env_flag("ESTER_TELEGRAM_ADAPTER_AUTOSTART", "1")', '_env_flag("ESTER_TELEGRAM_ADAPTER_AUTOSTART", "0")')
    return new


def _apply(root_dir: Path) -> Optional[Path]:
    targets: List[Tuple[str, Callable[[str], str]]] = [
        ("modules/chat_api.py", _patch_chat_api),
        ("run_ester_fixed.py", _patch_run_ester_fixed),
        ("messaging/telegram_adapter.py", _patch_messaging_telegram_adapter),
    ]

    # optional: if there are such files, we’ll also try to fix the defaults
    optional: List[Tuple[str, Callable[[str], str]]] = [
        ("bridges/telegram_adapter.py", _patch_messaging_telegram_adapter),
        ("services/telegram_adapter.py", _patch_messaging_telegram_adapter),
    ]

    all_targets = targets + optional

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root_dir / ".patches" / f"backup_{stamp}_tg_lock_context_v2"
    backup_root.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {"created_at": stamp, "root": str(root_dir), "files": []}
    patched_any = False

    for rel, fn in all_targets:
        p = root_dir / rel
        if not p.exists():
            continue

        orig_bytes = p.read_bytes()
        orig_text = _read_text_any(p)
        new_text = fn(orig_text)

        if new_text != orig_text:
            bpath = backup_root / rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            bpath.write_bytes(orig_bytes)

            _write_text_utf8(p, new_text)

            manifest["files"].append(
                {
                    "rel": rel,
                    "backup": rel,
                    "sha256_before": _sha256_bytes(orig_bytes),
                    "sha256_after": _sha256_bytes(p.read_bytes()),
                }
            )
            patched_any = True

    if not patched_any:
        # nothing changed - clean
        try:
            shutil.rmtree(backup_root)
        except Exception:
            pass
        return None

    (backup_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_root


def _find_latest_backup(root_dir: Path) -> Optional[Path]:
    bp = root_dir / ".patches"
    if not bp.exists():
        return None
    cands = sorted([p for p in bp.glob("backup_*_tg_lock_context_v2") if p.is_dir()])
    return cands[-1] if cands else None


def _rollback(root_dir: Path, backup_dir: Optional[Path] = None) -> Path:
    if backup_dir is None:
        backup_dir = _find_latest_backup(root_dir)
    if backup_dir is None or (not backup_dir.exists()):
        raise FileNotFoundError("No backup folder found.")

    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("manifest.json not found in backup folder.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    restored = []
    for item in manifest.get("files", []):
        rel = item["rel"]
        src = backup_dir / rel
        dst = root_dir / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            restored.append(rel)

    print("Rolled back files:")
    for r in restored:
        print(" -", r)

    return backup_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["apply", "rollback"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--backup", default="")
    args = ap.parse_args()

    root_dir = Path(args.root).resolve()

    if args.cmd == "apply":
        b = _apply(root_dir)
        if b is None:
            print("No changes applied (already patched or targets not found).")
            return 0
        print("Patch applied.")
        print("Backup folder:", str(b))
        return 0

    if args.cmd == "rollback":
        backup_dir = Path(args.backup).resolve() if args.backup.strip() else None
        b = _rollback(root_dir, backup_dir)
        print("Rollback complete. Backup folder used:", str(b))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
'@

Set-Content -Path $patchPy -Value $code -Encoding UTF8
Write-Host ">>> Patch tool written: $patchPy" -ForegroundColor DarkGray

& $py $patchPy apply --root $root
if ($LASTEXITCODE -ne 0) {
    throw "Patch failed with exit code $LASTEXITCODE"
}

Write-Host ">>> Done." -ForegroundColor Green
