# -*- coding: utf-8 -*-
from __future__ import annotations

"""config_backup.py - bekap konfiguratsii/pamyati (zip) + podpis tselostnosti (HMAC-SHA256).

Error from loga:
  expected an indented block after 'except' statement
V iskhodnike v kontse byl `except Exception:` bez tela - modul dazhe ne importirovalsya.

What improved:
- Ispravlena sintaksicheskaya oshibka.
- Normalnaya russkaya dokumentatsiya (bez krakozyabr).
- Zip teper stroitsya s ponyatnymi otnositelnymi putyami (rel otnositelno PERSIST_DIR).
- Isklyuchaem papku BACKUP_DIR (chtoby bekap ne bekapil bekapy i ne razrastalsya).
- Add manifest.json vnutr arkhiva (spisok faylov, razmery, vremya).
- Atomarnaya zapis: snachala *.tmp, zatem rename; pri sboe otkat (A/B-slot po faktu).
- verify_backup teper vsegda vozvraschaet bool (False pri lyuboy oshibke).

Mosty (demand):
- Yavnyy most: etot zip+sig — gotovaya “fizicheskaya” zagotovka dlya L4 Witness zapisi
  (hash/podpis → tamper-evident audit trail).
- Skrytye mosty:
  (1) Infoteoriya ↔ praktika: HMAC na baytakh arkhiva - kompaktnyy “kanal proverki” tselostnosti.
  (2) Inzheneriya ↔ gigiena: isklyuchenie BACKUP_DIR iz nabora - kak ne khranit musor v otseke s instrumentsami.

ZEMNOY ABZATs: v kontse fayla."""


import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Iterable, List, Tuple, Optional, Sequence

# Important: we keep the import from security.signing, but make an adapter:
# - the security.signing module can exist, but have different function names
# - therefore, we are looking for suitable callables and, if not available, use the HMAS stdlib
import base64
import hmac
import hashlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env_hmac_key() -> bytes:
    """Klyuch dlya HMAC (dolzhen byt stable mezhdu zapuskom create/verify).

    Predpochtitelnye peremennye:
      - ESTER_HMAC_KEY
      - HMAC_KEY
      - BACKUP_HMAC_KEY

    Format: stroka UTF-8 (lyuboy), libo base64url/base64 (optional)."""
    for k in ("ESTER_HMAC_KEY", "HMAC_KEY", "BACKUP_HMAC_KEY"):
        v = (os.getenv(k) or "").strip()
        if not v:
            continue
        # poprobuem base64/url-safe
        try:
            pad = "=" * (-len(v) % 4)
            raw = base64.urlsafe_b64decode((v + pad).encode("ascii"))
            if raw:
                return raw
        except Exception:
            pass
        return v.encode("utf-8", errors="replace")
    # the key is not specified - it’s better to honestly fail than to make unsigned “one-time” backups
    raise RuntimeError("HMAC key not set. Set ESTER_HMAC_KEY (or HMAC_KEY/BACKUP_HMAC_KEY).")

def _stdlib_hmac_sign(blob: bytes) -> str:
    key = _env_hmac_key()
    mac = hmac.new(key, blob, hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")
    return sig

def _stdlib_hmac_verify(blob: bytes, sig: str) -> bool:
    try:
        exp = _stdlib_hmac_sign(blob)
        return hmac.compare_digest(str(exp), str(sig or "").strip())
    except Exception:
        return False

def _pick_signing_functions():
    """Pytaemsya nayti sovmestimye funktsii v security.signing.

    Ozhidaemye signatury:
      - sign(blob: bytes) -> str
      - hmac_sign(blob: bytes) -> str
      - verify(blob: bytes, sig: str) -> bool
      - hmac_verify(blob: bytes, sig: str) -> bool
    Esli signatury otlichayutsya (for example, trebuyut key), ispolzuem stdlib."""
    try:
        import security.signing as signing  # type: ignore
    except Exception:
        return None, None, "security.signing missing"

    sign_candidates = ("hmac_sign", "sign_hmac", "sign", "sign_bytes", "hmac_sha256_sign")
    ver_candidates = ("hmac_verify", "verify_hmac", "verify", "verify_bytes", "hmac_sha256_verify")

    sign_fn = None
    ver_fn = None
    for name in sign_candidates:
        fn = getattr(signing, name, None)
        if callable(fn):
            sign_fn = fn
            break
    for name in ver_candidates:
        fn = getattr(signing, name, None)
        if callable(fn):
            ver_fn = fn
            break

    note = f"security.signing: sign={getattr(sign_fn, '__name__', None)} verify={getattr(ver_fn, '__name__', None)}"
    return sign_fn, ver_fn, note

_SIGN_FN, _VER_FN, _SIGN_NOTE = _pick_signing_functions()

def hmac_sign(blob: bytes) -> str:
    """Single signal() for backups. Returns basier64irl(sig) without b=b."""
    if callable(_SIGN_FN):
        try:
            return str(_SIGN_FN(blob))  # type: ignore[misc]
        except TypeError:
            # signatura trebuet key — ispolzuem stdlib
            return _stdlib_hmac_sign(blob)
        except Exception:
            return _stdlib_hmac_sign(blob)
    return _stdlib_hmac_sign(blob)

def hmac_verify(blob: bytes, sig: str) -> bool:
    """Single verifi() for backups."""
    if callable(_VER_FN):
        try:
            return bool(_VER_FN(blob, sig))  # type: ignore[misc]
        except TypeError:
            return _stdlib_hmac_verify(blob, sig)
        except Exception:
            return _stdlib_hmac_verify(blob, sig)
    return _stdlib_hmac_verify(blob, sig)
# -------------------- Parametry/defolty --------------------
def _persist_dir() -> str:
    return os.getenv("PERSIST_DIR", os.path.join(os.getcwd(), "data"))


def _backup_dir(persist_dir: str) -> str:
    return os.getenv("BACKUP_DIR", os.path.join(persist_dir, "backups"))


def _ensure_dir(p: str) -> None:
    if p:
        os.makedirs(p, exist_ok=True)


# -------------------- Sbor faylov --------------------
def _walk_include(base_dir: str, *, exclude_dirs: Iterable[str]) -> List[str]:
    files: List[str] = []
    base_dir = os.path.abspath(base_dir)
    exclude_abs = {os.path.abspath(d) for d in exclude_dirs if d}

    if not os.path.isdir(base_dir):
        return files

    for root, dirnames, fnames in os.walk(base_dir):
        root_abs = os.path.abspath(root)

        # prune: does not enter excluded directories
        pruned: List[str] = []
        for d in list(dirnames):
            cand = os.path.abspath(os.path.join(root_abs, d))
            if any(cand == ex or cand.startswith(ex + os.sep) for ex in exclude_abs):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        # dopolnitelno: standartnyy musor
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]

        for name in fnames:
            if name.endswith((".pyc", ".tmp")):
                continue
            files.append(os.path.join(root_abs, name))
    return files


def _relpath(abs_path: str, base_dir: str) -> str:
    # otnositelnyy put vnutri payload (ot persist_dir)
    rp = os.path.relpath(abs_path, start=base_dir)
    rp = rp.replace("\\", "/")  # normalizes for zip
    return rp


def _build_manifest(paths: List[str], *, base_dir: str) -> dict:
    items = []
    for p in paths:
        try:
            st = os.stat(p)
            items.append(
                {
                    "path": _relpath(p, base_dir),
                    "size": int(st.st_size),
                    "mtime": int(st.st_mtime),
                }
            )
        except Exception:
            items.append({"path": _relpath(p, base_dir), "size": None, "mtime": None})
    return {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_dir": os.path.abspath(base_dir),
        "files": items,
        "count": len(items),
    }


def _build_manifest_multi(sources: Sequence[Tuple[str, str, List[str]]]) -> dict:
    """Manifest for archives that include several independent source roots."""
    items = []
    roots = []
    for label, base_dir, paths in sources:
        roots.append(
            {
                "label": label,
                "base_dir": os.path.abspath(base_dir),
                "count": len(paths),
            }
        )
        for p in paths:
            rel = _relpath(p, base_dir)
            try:
                st = os.stat(p)
                items.append(
                    {
                        "source": label,
                        "path": rel,
                        "size": int(st.st_size),
                        "mtime": int(st.st_mtime),
                    }
                )
            except Exception:
                items.append({"source": label, "path": rel, "size": None, "mtime": None})

    return {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": roots,
        "files": items,
        "count": len(items),
    }


def _zip_to_file(zip_path_tmp: str, include_dir: str, *, exclude_dirs: Iterable[str]) -> None:
    include_dir_abs = os.path.abspath(include_dir)
    files = _walk_include(include_dir_abs, exclude_dirs=exclude_dirs)

    manifest = _build_manifest(files, base_dir=include_dir_abs)
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    with zipfile.ZipFile(zip_path_tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # payload/*
        for abs_path in files:
            arc = "payload/" + _relpath(abs_path, include_dir_abs)
            zf.write(abs_path, arcname=arc)
        # meta/manifest.json
        zf.writestr("meta/manifest.json", manifest_json)


def _zip_to_file_multi(zip_path_tmp: str, include_dirs: Sequence[str], *, exclude_dirs: Iterable[str]) -> None:
    include_abs = [os.path.abspath(p) for p in include_dirs if str(p or "").strip()]
    if not include_abs:
        raise ValueError("include_dirs must not be empty")
    if len(include_abs) == 1:
        _zip_to_file(zip_path_tmp, include_abs[0], exclude_dirs=exclude_dirs)
        return

    used_labels = set()
    sources: List[Tuple[str, str, List[str]]] = []
    for idx, base_dir in enumerate(include_abs):
        base_name = Path(base_dir).name or f"src_{idx+1}"
        label = base_name
        suffix = 2
        while label in used_labels:
            label = f"{base_name}_{suffix}"
            suffix += 1
        used_labels.add(label)
        files = _walk_include(base_dir, exclude_dirs=exclude_dirs)
        sources.append((label, base_dir, files))

    manifest = _build_manifest_multi(sources)
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    with zipfile.ZipFile(zip_path_tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for label, base_dir, files in sources:
            for abs_path in files:
                arc = "payload/" + label + "/" + _relpath(abs_path, base_dir)
                zf.write(abs_path, arcname=arc)
        zf.writestr("meta/manifest.json", manifest_json)


def _atomic_rename(tmp_path: str, final_path: str) -> None:
    # Windows-friendly: replace()
    Path(tmp_path).replace(final_path)


# -------------------- API --------------------
def create_backup(
    output_dir: Optional[str] = None,
    include_dirs: Optional[Iterable[str]] = None,
) -> Tuple[str, str]:
    """Sozdaet zip-bekap i vozvraschaet (zip_path, sig_path).

    Subscription:
      HMAC-SHA256 po baytam arkhiva, encoded base64url (bez '='),
      sokhranyaetsya ryadom v fayle .sig.

    Sovmestimost:
      - create_backup() — staroe behavior (PERSIST_DIR -> BACKUP_DIR)
      - create_backup(output_dir=..., include_dirs=[...]) - legacy API dlya testov/CLI"""
    persist_dir = _persist_dir()
    roots: List[str] = []
    if include_dirs is not None:
        for p in include_dirs:
            cand = str(p or "").strip()
            if not cand:
                continue
            abs_p = os.path.abspath(cand)
            if abs_p not in roots:
                roots.append(abs_p)
    if not roots:
        roots = [os.path.abspath(persist_dir)]

    backup_dir = os.path.abspath(str(output_dir or "").strip()) if str(output_dir or "").strip() else _backup_dir(persist_dir)
    _ensure_dir(backup_dir)

    # We exclude the backlog_dir itself so that the backup does not grow endlessly
    exclude = [backup_dir]

    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    zip_path = os.path.join(backup_dir, f"backup_{ts}.zip")
    zip_tmp = zip_path + ".tmp"
    sig_path = zip_path + ".sig"
    sig_tmp = sig_path + ".tmp"

    # A/B slot: atomic recording with rollback on exceptions
    try:
        if os.path.exists(zip_tmp):
            os.remove(zip_tmp)
        if os.path.exists(sig_tmp):
            os.remove(sig_tmp)

        _zip_to_file_multi(zip_tmp, roots, exclude_dirs=exclude)
        _atomic_rename(zip_tmp, zip_path)

        # podpis
        with open(zip_path, "rb") as f:
            blob = f.read()
        sig = hmac_sign(blob)

        with open(sig_tmp, "w", encoding="ascii") as f:
            f.write(sig)
        _atomic_rename(sig_tmp, sig_path)

        return zip_path, sig_path
    except Exception:
        # rollback temporary files
        for p in (zip_tmp, sig_tmp):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        raise


def verify_backup(path: str) -> bool:
    """Checks the integrity of the archive and, if there is a .sig, the correctness of the signature."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            blob = f.read()

        # zip-validnost
        with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
            _ = zf.infolist()

        # signature (if any)
        sig_path = path + ".sig"
        if os.path.isfile(sig_path):
            with open(sig_path, "r", encoding="ascii") as f:
                sig = f.read().strip()
            return bool(hmac_verify(blob, sig))

        return True
    except Exception:
        return False


def latest_backup_path() -> Optional[str]:
    """Returns the path to the last Backup_*.zip or None."""
    persist_dir = _persist_dir()
    backup_dir = _backup_dir(persist_dir)
    if not os.path.isdir(backup_dir):
        return None
    zips = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".zip")]
    if not zips:
        return None
    zips.sort()
    return zips[-1]


# -------------------- CLI (optsionalno) --------------------
def _main(argv: List[str]) -> int:
    cmd = (argv[1] if len(argv) > 1 else "").strip().lower()
    if cmd in ("create", "backup", "b"):
        zp, sp = create_backup()
        print(zp)
        print(sp)
        return 0
    if cmd in ("verify", "v"):
        target = argv[2] if len(argv) > 2 else (latest_backup_path() or "")
        ok = verify_backup(target) if target else False
        print("OK" if ok else "FAIL")
        return 0 if ok else 2
    print("Usage: python -m config_backup create|verify [path]")
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys
    raise SystemExit(_main(sys.argv))


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Bekap - eto kak aptechka v mashine: ona ne nuzhna rovno do momenta, kogda nuzhna srochno.
Inzhenernyy smysl podpisi (HMAC) - plomba na konteynere: vy ne “verite”, vy proveryaete.
I esche: ne skladyvayte bekapy vnutr togo, chto bekapite - eto kak khranit musor v motornom otseke:
snachala “nichego”, potom peregrev i pozhar."""
