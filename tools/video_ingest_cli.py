#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/video_ingest_cli.py - oflayn CLI dlya yadra video-konveyera (URL/fayl → metadannye/subtitry/ASR → konspekt → pamyat).

Optsii:
  --url URL Istochnik-URL (YouTube i dr.)
  --file PATH Local fayl (mp4/mkv/…)
  --probe Tolko metadannye (ffprobe)
  --transcript Izvlech transkript (subtitry/ASR)
  --summary Sformirovat chernovoy konspekt
  --chunk-ms N Razmer chanka audio v millisekundakh (po umolchaniyu 300000)
  --prefer-audio Dlya URL pytatsya skachivat audio-only
  --keep Ne udalyat rabochuyu direktoriyu (dlya otladki)

Mosty:
- Yavnyy: (UX ↔ Inzheneriya) Prozrachnaya CLI dlya tekhpodderzhki i oflayn-proverok.
- Skrytyy #1: (Logika ↔ Nadezhnost) A/B-flag VIDEO_INGEST_AB, avto-otkat — bystryy “strakhovochnyy” stsenariy.
- Skrytyy #2: (Kibernetika ↔ Planirovanie) Chank-parametry — ruchka regulyatora “menshe/bystree” vs “bolshe/kachestvennee”.

Zemnoy abzats:
Eto “ruchnoy pult” linii: mozhno zapuskat uzly konveyera po odnomu (probe) ili skvoznyakom (transcript+summary), proveryaya stabilnost.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Any, Dict

# Yadro
from modules.ingest.video_ingest import ingest_video  # drop-in
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", type=str, help="Istochnik-URL")
    g.add_argument("--file", type=str, help="Lokalnyy fayl")
    ap.add_argument("--probe", action="store_true", help="Only metadannye")
    ap.add_argument("--transcript", action="store_true", help="Izvlech transkript (subtitry/ASR)")
    ap.add_argument("--summary", action="store_true", help="Sformirovat chernovoy konspekt")
    ap.add_argument("--chunk-ms", type=int, default=300000)
    ap.add_argument("--prefer-audio", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    src = args.url or args.file
    want_meta = bool(args.probe or args.transcript or args.summary or True)
    want_transcript = bool(args.transcript or args.summary)
    want_summary = bool(args.summary)

    rep: Dict[str, Any] = ingest_video(
        src=src,
        want_meta=want_meta,
        want_transcript=want_transcript,
        want_summary=want_summary,
        prefer_audio=bool(args.prefer_audio or bool(args.url)),
        want_subs=True,
        chunk_ms=int(args.chunk_ms),
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    # We leave the working directory only using the --keep flag
    if not args.keep:
        try:
            wd = (rep.get("source") or {}).get("workdir")
            if wd and os.path.isdir(wd):
                shutil.rmtree(wd, ignore_errors=True)
        except Exception:
            pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
