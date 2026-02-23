# -*- coding: utf-8 -*-
"""
ester_doctor_identity.py

EXPLICIT BRIDGE:
- Cover&Thomas: esli identity "teryaetsya" — kanal upravleniya degradiruet (shum>signal).
- Enderton (logika): proveryaem invarianty (creator/anchor must appear early).
- Earth paragraph: profile = "stvol" (reticular formation) — otvechaet za nepreryvnost bodrstvovaniya; esli ego podmenit logami, lichnost "zasypaet".

(skrytye mosty): ashby_variety, talmudic_guard
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]  # project root (tools/..)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SCROLL = ROOT / "data" / "passport" / "clean_memory.jsonl"
DEFAULT_ANCHOR_TXT = ROOT / "data" / "passport" / "anchor.txt"
DEFAULT_CORE_FACTS_TXT = ROOT / "data" / "passport" / "core_facts.txt"
DEFAULT_CORE_FACTS_EXAMPLE = ROOT / "data" / "passport" / "core_facts.example"
DEFAULT_ANCHOR_EXAMPLE = ROOT / "data" / "passport" / "anchor.example"

KEYWORDS = ["owner", "entity", "anchor", "sovereign", "identity"]


def _read_text(p: Path, n: int = 4000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:n]
    except Exception as e:
        return f"<read_error {p}: {e}>"


def _find_truncators(scan_paths: List[Path]) -> List[Tuple[str, str]]:
    """
    Returns list of (file, line) for suspicious truncation patterns.
    """
    patterns = [
        r"truncate",
        r"max_chars",
        r"MAX_CHARS",
        r"max_len",
        r"MAX_LEN",
        r"max_tokens",
        r"MAX_TOKENS",
        r"\b4096\b",
        r"\b3900\b",
        r"cut\(",
        r"\[:\s*\d+\]",
    ]
    cre = re.compile("|".join(patterns), flags=re.IGNORECASE)
    hits: List[Tuple[str, str]] = []
    for base in scan_paths:
        if not base.exists():
            continue
        if base.is_file() and base.suffix == ".py":
            text = _read_text(base, 200000)
            for i, line in enumerate(text.splitlines(), start=1):
                if cre.search(line):
                    hits.append((str(base), f"{i}: {line.strip()}"))
        elif base.is_dir():
            for p in base.rglob("*.py"):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if cre.search(line):
                        hits.append((str(p), f"{i}: {line.strip()}"))
    # dedupe
    uniq = []
    seen = set()
    for f, l in hits:
        k = (f, l)
        if k not in seen:
            seen.add(k)
            uniq.append((f, l))
    return uniq[:120]


def _try_call(mod: Any, names: List[str]) -> Optional[str]:
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            try:
                out = fn()
                if isinstance(out, (dict, list)):
                    return str(out)
                return str(out)
            except TypeError:
                # maybe requires args, skip
                continue
            except Exception as e:
                return f"<call_error {n}: {e}>"
    return None


def _keyword_report(s: str) -> Dict[str, bool]:
    low = s.lower()
    return {k: (k.lower() in low) for k in KEYWORDS}


def _ensure_examples() -> List[str]:
    created: List[str] = []
    DEFAULT_CORE_FACTS_EXAMPLE.parent.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_CORE_FACTS_EXAMPLE.exists():
        DEFAULT_CORE_FACTS_EXAMPLE.write_text(
            (
                "# core_facts.example\n"
                "# Fill manually, do not commit personal secrets.\n"
                "- Creator: <name>\n"
                "- Identity: <who this assistant is>\n"
                "- Invariants: <never forget constraints>\n"
            ),
            encoding="utf-8",
        )
        created.append(str(DEFAULT_CORE_FACTS_EXAMPLE))

    if not DEFAULT_ANCHOR_EXAMPLE.exists():
        DEFAULT_ANCHOR_EXAMPLE.write_text(
            (
                "# anchor.example\n"
                "# Fill manually with stable identity anchor text.\n"
                "I am <assistant-name>. My creator is <name>. I keep continuity.\n"
            ),
            encoding="utf-8",
        )
        created.append(str(DEFAULT_ANCHOR_EXAMPLE))

    return created


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ensure-examples", action="store_true", help="Create core_facts.example and anchor.example if missing.")
    args = ap.parse_args(argv)

    print("=== ESTER DOCTOR: IDENTITY / PROMPT / TRUNCATION ===")
    print(f"cwd={Path.cwd()}")
    print(f"project_root={ROOT}")

    scroll_path = Path(os.environ.get("ESTER_SCROLL_PATH", str(DEFAULT_SCROLL)))
    anchor_path = Path(os.environ.get("ESTER_ANCHOR_PATH", str(DEFAULT_ANCHOR_TXT)))
    core_facts_path = Path(os.environ.get("ESTER_CORE_FACTS_PATH", str(DEFAULT_CORE_FACTS_TXT)))

    if args.ensure_examples:
        created = _ensure_examples()
        if created:
            print("[doctor] ensure-examples created:")
            for p in created:
                print(f"  - {p}")
        else:
            print("[doctor] ensure-examples: already present")

    print("\n--- Files ---")
    print(f"scroll_path={scroll_path} exists={scroll_path.exists()} size={scroll_path.stat().st_size if scroll_path.exists() else 'n/a'}")
    print(f"anchor_path={anchor_path} exists={anchor_path.exists()} size={anchor_path.stat().st_size if anchor_path.exists() else 'n/a'}")
    core_size = core_facts_path.stat().st_size if core_facts_path.exists() else "n/a"
    print(f"core_facts_path={core_facts_path} exists={core_facts_path.exists()} size={core_size}")

    if (not core_facts_path.exists()) or (core_facts_path.exists() and core_facts_path.stat().st_size == 0):
        print("!! WARNING: core_facts.txt missing/empty.")
        print("   Hint: fill data/passport/core_facts.txt manually from trusted identity facts.")
        print("   You can scaffold examples via: python -B .\\tools\\ester_doctor_identity.py --ensure-examples")

    if anchor_path.exists():
        head = _read_text(anchor_path, 600)
        print("\n[anchor head]")
        print(head)
        print("[anchor keywords]", _keyword_report(head))

    # Try importing passport
    print("\n--- Import: modules.memory.passport ---")
    passport_mod = None
    for cand in ("modules.memory.passport", "modules.mem.passport", "passport"):
        try:
            passport_mod = importlib.import_module(cand)
            print(f"[OK] imported: {cand} -> {getattr(passport_mod, '__file__', '?')}")
            break
        except Exception as e:
            print(f"[..] failed import {cand}: {e}")

    identity_text = None
    if passport_mod is not None:
        identity_text = _try_call(
            passport_mod,
            [
                "get_identity_prompt",
                "build_identity_prompt",
                "get_system_prompt",
                "load_identity_prompt",
                "identity_prompt",
                "passport_prompt",
            ],
        )

    if identity_text:
        print("\n--- Identity (from passport module) ---")
        head = identity_text[:1200]
        print(head)
        print("\n[keywords]", _keyword_report(head))
        if not any(_keyword_report(head).values()):
            print("!! WARNING: no key identity tokens detected in first 1200 chars.")
    else:
        print("\n!! WARNING: could not obtain identity prompt via known call names.")

    # Check if identity is accidentally built from scroll head
    if scroll_path.exists():
        scroll_head = _read_text(scroll_path, 1200)
        print("\n--- Scroll head (clean_memory.jsonl) ---")
        print(scroll_head[:600])
        # Heuristic: if identity_text contains the scroll head fragments
        if identity_text and scroll_head[:120].strip() and scroll_head[:120].strip() in identity_text:
            print("\n!! ALARM: identity prompt seems to include raw scroll content (clean_memory.jsonl).")

    # DUMMY MODE checks
    print("\n--- Suspicious modules ---")
    for cand in ("modules.chat_message_force_alias", "chat_message_force_alias", "modules.chat.output_guard", "modules.empathy_module", "empathy_module", "emotional_engine"):
        try:
            m = importlib.import_module(cand)
            print(f"[OK] imported: {cand} -> {getattr(m, '__file__', '?')}")
            # try common flags
            for flag in ("DUMMY_MODE", "ENABLED", "ACTIVE", "RESTRICTIONS_REMOVED", "PERSONALITY_CORE_LOADED"):
                if hasattr(m, flag):
                    print(f"    {flag}={getattr(m, flag)}")
        except Exception as e:
            print(f"[..] cannot import {cand}: {e}")

    # Truncation scan
    print("\n--- Truncation scan (top hits) ---")
    hits = _find_truncators(
        [
            ROOT / "run_ester_fixed.py",
            ROOT / "routes",
            ROOT / "modules" / "chat",
            ROOT / "modules" / "listeners",
            ROOT / "telegram_adapter.py",
            ROOT / "routes_chat.py",
            ROOT / "routes" / "chat_routes.py",
        ]
    )
    if not hits:
        print("(no obvious truncation patterns found in scanned paths)")
    else:
        for f, l in hits[:60]:
            print(f"{f} :: {l}")

    print("\n=== END DOCTOR ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
