# -*- coding: utf-8 -*-
"""
ITER A2g: normalize .env (paths + dedup), preserve secrets

YaVNYY MOST: c=a+b — poryadok v konfige daet ustoychivuyu pamyat bez samopovrezhdeniy.
SKRYTYE MOSTY:
  - Ashby: regulyator raznoobraziya — odin primary vstore, menshe “dvukh domov”.
  - Cover&Thomas: lechim ukazateli (puti), a ne gonyaem gigabayty.
ZEMNOY ABZATs:
  Eto kak promarkirovat kabeli v servernoy: inache “vse rabotaet”, poka ne dernesh ne tot provod.

Usage (luchshe na ostanovlennom servere):
  cd D:\ester-project
  python tools\\patches\\iter_A2g_env_rewrite_normalize.py
  (perezapusti Ester, chtoby .env perechitalsya)
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = Path(os.getcwd()).resolve()
ENV_PATH = PROJECT_ROOT / ".env"

# Chto schitaem sekretom (znacheniya NE pechataem, no perenosim kak est)
SECRET_PAT = re.compile(r"(API_KEY|TOKEN|SECRET|PASS|JWT)", re.IGNORECASE)

def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        # ubiraem sluchaynye probely vokrug
        if k:
            out[k] = v
    return out

def is_secret_key(k: str) -> bool:
    return bool(SECRET_PAT.search(k or ""))

def backup_file(p: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_A2g_{ts}")
    b.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return b

def main() -> int:
    if not ENV_PATH.exists():
        raise SystemExit(f"Missing .env at: {ENV_PATH}")

    old_text = ENV_PATH.read_text(encoding="utf-8", errors="ignore")
    old = parse_env(old_text)

    root = PROJECT_ROOT
    # fiksirovannye puti (glavnoe)
    fixed = {
        "ESTER_PROJECT_ROOT": str(root),
        "ESTER_HOME": str(root / ".ester"),
        "ESTER_DATA_ROOT": str(root / "data"),
        "ESTER_TMP_DIR": str(root / "data" / "tmp"),
        "ESTER_LOG_DIR": str(root / "data" / "logs"),
        "DATA_DIR": str(root / "data"),
        "PERSIST_DIR": str(root / "data"),
        "CHAT_LOG_DIR": str(root / "data" / "chat"),
        "UPLOAD_DIR": str(root / "data" / "upload"),
        "ESTER_PASSPORT_PATH": str(root / "data" / "passport" / "ester_identity.md"),
        "ESTER_RAG_DOCS_DIR": str(root / "data" / "docs"),
        "ESTER_RAG_DOCS_PATH": str(root / "data" / "docs"),
        "ESTER_RAG_FORCE_PATH": str(root / "data" / "docs"),
        "ESTER_DOCS_DIR": str(root / "data" / "docs"),
        "ESTER_RAG_BASE": str(root / "data" / "docs"),
        "ESTER_VSTORE_ROOT": str(root / "vstore"),
        "CHROMA_PERSIST_DIR": str(root / "vstore" / "chroma"),
        "ESTER_VECTOR_DIR": str(root / "vstore" / "vectors"),
        "LANCEDB_DIR": str(root / "vstore" / "lancedb"),
        "FAISS_INDEX_PATH": str(root / "vstore" / "faiss" / "index.faiss"),
        "ESTER_CHAT_MEM_DIR": str(root / "vstore" / "chat_mem"),
        "ESTER_TG_UPLOAD_DIR": str(root / "tg_uploads"),
        "GOOGLE_APPLICATION_CREDENTIALS": str(root / "config" / "gen-lang-sa.json"),
    }

    # Normalizovannye znacheniya (esli klyucha ne bylo — dobavim defolt)
    defaults = {
        "HOST": "127.0.0.1",
        "PORT": "8080",
        "ESTER_API_BASE": "http://127.0.0.1:8080",
        "ESTER_TZ": "UTC",
        "CHROMA_AUTO_HEAL_ENV": "1",
        "CHROMA_AUTO_HEAL_EAGER": "1",
        "CHROMA_UI_SCAN": "0",
        "CHROMA_COLLECTION_UI": "ester_global",
        "CHROMA_UI_NO_EMBED": old.get("CHROMA_UI_NO_EMBED", "0") or "0",
    }

    # Sobiraem itogovyy nabor klyuchey:
    # 1) berem vse starye (unikalnye),
    # 2) poverkh nakatyvaem fixed i defaults,
    # 3) chistim dubli po opredeleniyu (v dict oni uzhe “poslednie”).
    merged: dict[str, str] = dict(old)
    merged.update(defaults)
    merged.update(fixed)

    # podchistim chastye “bitye” probely (tipa "ACTIONS_AB=A " i t.p.)
    for k, v in list(merged.items()):
        merged[k] = (v or "").strip()

    # Vazhnoe: NE pechataem sekrety, no perenosim kak est.
    # Esli sekretnogo klyucha ne bylo — stavim zaglushku.
    for k in list(merged.keys()):
        if is_secret_key(k) and not merged.get(k):
            merged[k] = "__CHANGE_ME__"

    # Udalyaem yavnye povtoryayuschiesya/musornye klyuchi (ostavlyaem normalnye varianty)
    # (esli tebe vdrug kakoy-to dubl byl nuzhen — skazhesh, vernem)
    drop_keys = {
        # nichego “kritichnogo” ne dropaem, tolko esli vstretyatsya sovsem musornye
    }
    for dk in drop_keys:
        merged.pop(dk, None)

    # Pishem novyy .env uporyadochenno: snachala vazhnoe, potom ostalnoe po alfavitu
    important_order = [
        "HOST","PORT","ESTER_API_BASE","ESTER_TZ","ESTER_PROJECT_ROOT",
        "ESTER_HOME","ESTER_DATA_ROOT","ESTER_TMP_DIR","ESTER_LOG_DIR",
        "ESTER_VSTORE_ROOT","CHROMA_PERSIST_DIR","ESTER_VECTOR_DIR",
        "CHROMA_AUTO_HEAL_ENV","CHROMA_AUTO_HEAL_EAGER","CHROMA_UI_SCAN",
    ]
    important = []
    seen = set()
    for k in important_order:
        if k in merged:
            important.append(k)
            seen.add(k)
    rest = sorted([k for k in merged.keys() if k not in seen])

    header = [
        "# ============================================================",
        "# ITER A2g: .env normalize (paths + dedup), preserve secrets",
        "# ============================================================",
        "",
    ]
    lines = header[:]

    for k in important + rest:
        v = merged.get(k, "")
        # nichego ne ekraniruem: .env u tebya prostoy KEY=VALUE
        lines.append(f"{k}={v}")

    b = backup_file(ENV_PATH)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Otchet (bez sekretov)
    changed = []
    for k in important_order:
        if old.get(k, "") != merged.get(k, ""):
            changed.append(k)

    print("OK: ITER A2g applied")
    print("  backup:", b.name)
    print("  project_root:", str(root))
    if changed:
        print("  key_changes:", ", ".join(changed))
    else:
        print("  key_changes: (none of important keys changed)")
    print("NOTE: restart Ester to reload .env")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())