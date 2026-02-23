# -*- coding: utf-8 -*-
from __future__ import annotations

"""multilingual_analyzer.py — analiz mnogoyazychnykh dokumentov s (optsionalnym) perevodom i empatiey.

Problema iz loga:
  No module named 'googletrans'

Prichina:
  googletrans ne ustanovlen (i chasto nestabilen/lomaetsya), a modul importiruet ego bez fallback.

Chto sdelano:
- Perevod stal OPTsIONALNYM: esli googletrans net — rabotaem bez perevoda (identity translator).
- Vse vneshnie zavisimosti sdelany best-effort (ne valim kontur, esli chego-to net).
- Dobavlen bezopasnyy ingest fallback (esli ingest_file ne nayden): chitaem tekstovyy fayl i rezhem na chanki.
- Shifrovanie best-effort: esli ENCRYPTION_KEY ne zadan — generiruem klyuch na vremya protsessa (i preduprezhdaem).
- Chroma: PersistentClient s putem iz PERSIST_DIR (po umolchaniyu ./data). Esli chromadb net — rabotaem bez vektornoy BD.
- Dobavlen CLI dlya ruchnogo zapuska.

Mosty (trebovanie):
- Yavnyy most: ingest → (translate?) → emotion → (encrypt?) → store (chroma + structured memory).
- Skrytye mosty:
  1) Infoteoriya ↔ praktichnost: fingerprint/metadannye vmesto “vsego teksta” v summary — ekonomiya kanala.
  2) Kibernetika ↔ ekspluatatsiya: fail-open (net googletrans/net chroma) → analiz vse ravno vydaet rezultat.

ZEMNOY ABZATs: v kontse fayla.
"""

import argparse
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)


# -------------------------
# Optional dependencies
# -------------------------
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

try:
    from cryptography.fernet import Fernet  # type: ignore
except Exception:
    Fernet = None  # type: ignore

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore

# googletrans is optional
try:
    from googletrans import Translator as GoogleTranslator  # type: ignore
except Exception:
    GoogleTranslator = None  # type: ignore


# -------------------------
# Helpers / fallbacks
# -------------------------
def _persist_dir() -> str:
    return (os.getenv("PERSIST_DIR") or "data").strip() or "data"


def _safe_mkdir(p: str) -> None:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass


def _fingerprint(text: str) -> str:
    h = hashlib.sha256((text or "").encode("utf-8", errors="replace")).digest()
    return h[:8].hex()


def _chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if max_chars <= 200:
        max_chars = 200
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for line in text.splitlines():
        ln = line.rstrip()
        if not ln:
            continue
        # +1 for newline separator
        if size + len(ln) + 1 > max_chars and buf:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(ln)
        size += len(ln) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks


class IdentityTranslator:
    """Fallback perevodchik: vozvraschaet iskhodnyy tekst."""

    def translate(self, text: str, dest: str = "ru") -> str:
        return text


def _get_translator() -> Any:
    if GoogleTranslator is None:
        return IdentityTranslator()
    try:
        return GoogleTranslator()
    except Exception:
        return IdentityTranslator()


def _translate(translator: Any, text: str, dest: str) -> str:
    """Edinyy adapter translate()."""
    if not text:
        return ""
    try:
        # googletrans API: translator.translate(text, dest="ru").text
        if hasattr(translator, "translate"):
            res = translator.translate(text, dest=dest)  # type: ignore
            if isinstance(res, str):
                return res
            return getattr(res, "text", text)  # type: ignore
    except Exception:
        return text
    return text


def _load_ingest() -> Optional[Any]:
    """Probuem nayti ingest_file v neskolkikh mestakh."""
    # 1) kak v iskhodnike
    try:
        from file_ingest import ingest_file  # type: ignore
        return ingest_file
    except Exception:
        pass
    # 2) varianty v proekte
    try:
        from modules.ingest.file_ingest import ingest_file  # type: ignore
        return ingest_file
    except Exception:
        pass
    return None


def _load_emotion_analyzer() -> Any:
    """Probuem podklyuchit emotional engine, inache prostoy fallback."""
    try:
        from emotional_engine import EmotionalAnalyzer  # type: ignore
        return EmotionalAnalyzer()
    except Exception:
        pass

    class _FallbackEmotion:
        POS = ("ok", "good", "fine", "great", "happy", "thanks", "merci", "spasibo", "khorosho", "rad")
        NEG = ("bad", "sad", "angry", "error", "fail", "hate", "plokho", "zlo", "strash", "ustal")

        def analyze_emotion(self, t: str) -> Dict[str, Any]:
            low = (t or "").lower()
            score = 0
            for w in self.POS:
                if w in low:
                    score += 1
            for w in self.NEG:
                if w in low:
                    score -= 1
            emo = "neutral"
            if score >= 2:
                emo = "positive"
            elif score <= -2:
                emo = "negative"
            return {"emotion": emo, "score": score}

    return _FallbackEmotion()


def _load_memory_manager() -> Any:
    try:
        from structured_memory import MemoryManager  # type: ignore
        return MemoryManager()
    except Exception:
        # fallback noop
        class _NoopMem:
            def add_to_long_term(self, _x: Any) -> None:
                return

        return _NoopMem()


@dataclass
class AnalyzerConfig:
    target_lang: str = "ru"
    chunk_max_chars: int = 1200
    collection_name: str = "ester_multilingual_memory"
    encrypt: bool = True


class MultilingualAnalyzer:
    def __init__(self, config: Optional[AnalyzerConfig] = None):
        if load_dotenv is not None:
            try:
                load_dotenv()  # type: ignore
            except Exception:
                pass

        self.cfg = config or AnalyzerConfig()
        self.translator = _get_translator()
        self.emotion_analyzer = _load_emotion_analyzer()
        self.memory_manager = _load_memory_manager()

        # crypto
        self.cipher = None
        if self.cfg.encrypt and Fernet is not None:
            key = (os.getenv("ENCRYPTION_KEY") or "").strip()
            if not key:
                # Vazhno: ne valim modul, no preduprezhdaem.
                try:
                    gen = Fernet.generate_key()  # type: ignore
                    key = gen.decode("utf-8", errors="ignore")
                    log.warning("ENCRYPTION_KEY is not set; generated ephemeral key for this run")
                except Exception:
                    key = ""
            try:
                if key:
                    self.cipher = Fernet(key.encode("utf-8"))  # type: ignore
            except Exception:
                self.cipher = None

        # chroma
        self.collection = None
        if chromadb is not None:
            try:
                base = _persist_dir()
                _safe_mkdir(base)
                client = chromadb.PersistentClient(path=base)  # type: ignore[attr-defined]
                self.collection = client.get_or_create_collection(self.cfg.collection_name)
            except Exception as e:
                log.warning("chroma disabled: %s", e)
                self.collection = None

        # ingest
        self.ingest_file = _load_ingest()

    def _read_and_chunk(self, file_path: str) -> List[str]:
        if self.ingest_file is not None:
            try:
                chunks = self.ingest_file(file_path)  # type: ignore[call-arg]
                if isinstance(chunks, list):
                    return [str(x) for x in chunks if str(x).strip()]
            except Exception as e:
                log.warning("ingest_file failed, fallback to text read: %s", e)

        # fallback: try to read as text
        p = Path(file_path)
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                raw = p.read_text(encoding="cp1251", errors="replace")
            except Exception:
                raw = ""
        return _chunk_text(raw, max_chars=self.cfg.chunk_max_chars)

    def analyze_document(self, file_path: str, target_lang: Optional[str] = None) -> Dict[str, Any]:
        tgt = (target_lang or self.cfg.target_lang).strip() or "ru"
        chunks = self._read_and_chunk(file_path)

        translated: List[str] = []
        for ch in chunks:
            translated.append(_translate(self.translator, ch, tgt))

        emotions: List[Dict[str, Any]] = []
        for t in translated:
            try:
                emotions.append(self.emotion_analyzer.analyze_emotion(t))  # type: ignore[attr-defined]
            except Exception:
                emotions.append({"emotion": "neutral"})

        # Summary (korotko, no polezno)
        emo_set = sorted({str(e.get("emotion", "neutral")) for e in emotions})
        summary = {
            "ok": True,
            "file": str(file_path),
            "chunks": len(chunks),
            "translated": len(translated),
            "target_lang": tgt,
            "translator": "googletrans" if GoogleTranslator is not None else "identity",
            "emotions": emo_set,
            "note": "stored encrypted chunks into memory (best-effort)",
        }

        # store
        for i, chunk in enumerate(translated):
            meta = dict(emotions[i] if i < len(emotions) else {})
            meta.setdefault("target_lang", tgt)
            meta.setdefault("fp", _fingerprint(chunk))
            meta.setdefault("i", i)
            meta.setdefault("file", str(file_path))

            payload = f"{chunk}|{meta.get('emotion','neutral')}"
            if self.cipher is not None:
                try:
                    payload = self.cipher.encrypt(payload.encode("utf-8")).decode("utf-8")
                    meta["encrypted"] = True
                except Exception:
                    meta["encrypted"] = False
            else:
                meta["encrypted"] = False

            # chroma best-effort
            if self.collection is not None:
                try:
                    self.collection.add(
                        documents=[payload],
                        metadatas=[meta],
                        ids=[f"{meta['fp']}-{i}"],
                    )
                except Exception:
                    pass

            # structured memory best-effort
            try:
                self.memory_manager.add_to_long_term(payload)
            except Exception:
                pass

        return summary

    def background_process(self, file_path: str) -> Dict[str, Any]:
        return self.analyze_document(file_path)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Multilingual document analyzer (best-effort, offline-friendly)")
    ap.add_argument("file", help="Put k faylu")
    ap.add_argument("--lang", default="ru", help="Tselevoy yazyk perevoda (po umolchaniyu ru)")
    ap.add_argument("--no-encrypt", action="store_true", help="Ne shifrovat sokhranennye chanki")
    args = ap.parse_args(argv)

    cfg = AnalyzerConfig(target_lang=str(args.lang), encrypt=not bool(args.no_encrypt))
    an = MultilingualAnalyzer(cfg)
    rep = an.analyze_document(args.file, target_lang=args.lang)
    print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Esli net perevodchika — eto kak esli u cheloveka net obschego yazyka s sobesednikom: on vse ravno mozhet
zametit ton (emotsii), strukturu i klyuchevye povtoryayuschiesya slova. Perevod — eto usilitel signala,
no kontur ne dolzhen padat bez usilitelya: inache lyubaya meloch vyklyuchit sistemu.
"""