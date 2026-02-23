# -*- coding: utf-8 -*-
from __future__ import annotations

"""proactive_doc_analyzer.py — samodostatochnyy analiz dokumentov (proaktivno) + sokhranenie v pamyat.

Problema iz loga:
  No module named 'file_ingest'

Reshenie:
- Dobavlen shim `file_ingest.py` (sm. ryadom) s funktsiey ingest_file().
- Zdes import file_ingest best-effort: esli net — fallback na vnutrenniy ingest_text.

Dizayn:
- Best-effort zavisimosti: chromadb / cryptography / dotenv / EmotionalAnalyzer / MemoryManager.
- AB_MODE:
    A = realno sokhranyaem (v chroma + structured memory)
    B = tolko plan/otchet (bez sokhraneniya)
- Perevod: optsionalno (googletrans esli est, inache identity). Mozhno podklyuchit LLM-perevodchik cherez env.

ENV:
- ESTER_BASE_URL (ne obyazatelen zdes, no polezen esli podklyuchish translate endpoint)
- ESTER_TRANSLATE_ENDPOINT (esli zadan — POST {text, dest} -> {text}
- PERSIST_DIR (dlya chroma persistence)
- ENCRYPTION_KEY (Fernet key, url-safe base64) — esli net, generitsya epemernyy klyuch (warn)
- DOC_ANALYZER_COLLECTION (imya kollektsii chroma)
- AB_MODE=A|B

Mosty:
- Yavnyy most: ingest → (translate) → emotion → anchor → store (chroma + structured memory).
- Skrytye mosty:
  1) Infoteoriya ↔ praktichnost: fingerprint+anchors — eto “szhatie” smysla bez khraneniya lishnego shuma.
  2) Kibernetika ↔ bezopasnost: AB_MODE=B kak circuit-breaker — nablyudaem/planiruem, no ne menyaem pamyat.

ZEMNOY ABZATs: v kontse fayla.
"""

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- ingest (prefer shim) ---
try:
    from file_ingest import ingest_file, ingest_text  # type: ignore
except Exception:
    def ingest_text(text: str, chunk_size: int = 1200, max_chars: int = 200_000) -> List[str]:
        text = (text or "").replace("\ufeff", "")
        if max_chars and len(text) > int(max_chars):
            text = text[: int(max_chars)]
        # naive chunk
        out: List[str] = []
        for i in range(0, len(text), int(chunk_size)):
            part = text[i : i + int(chunk_size)].strip()
            if part:
                out.append(part)
        return out

    def ingest_file(path: str, chunk_size: int = 1200, max_chars: int = 200_000) -> List[str]:
        try:
            raw = open(path, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            raw = ""
        return ingest_text(raw, chunk_size=chunk_size, max_chars=max_chars)

# --- optional deps ---
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore

try:
    from cryptography.fernet import Fernet  # type: ignore
except Exception:
    Fernet = None  # type: ignore

try:
    from googletrans import Translator as GoogleTranslator  # type: ignore
except Exception:
    GoogleTranslator = None  # type: ignore


# --- emotion analyzer (best-effort) ---
def _load_emotion_analyzer() -> Any:
    try:
        from emotional_engine import EmotionalAnalyzer  # type: ignore
        return EmotionalAnalyzer()
    except Exception:
        class _Fallback:
            POS = ("ok", "good", "fine", "great", "happy", "thanks", "merci", "spasibo", "khorosho")
            NEG = ("bad", "sad", "angry", "error", "fail", "hate", "plokho", "ustal", "strash")
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
        return _Fallback()


# --- memory manager (best-effort) ---
def _load_memory_manager() -> Any:
    try:
        from structured_memory import MemoryManager  # type: ignore
        return MemoryManager()
    except Exception:
        class _Noop:
            def add_to_long_term(self, _x: Any) -> None:
                return
        return _Noop()


def _fp(text: str) -> str:
    h = hashlib.sha256((text or "").encode("utf-8", errors="replace")).digest()
    return h[:10].hex()


def _base_url() -> str:
    return (os.getenv("ESTER_BASE_URL") or "http://127.0.0.1:8090").strip().rstrip("/")


def _translate_via_endpoint(text: str, dest: str) -> Optional[str]:
    ep = (os.getenv("ESTER_TRANSLATE_ENDPOINT") or "").strip()
    if not ep:
        return None
    url = ep
    if not (url.startswith("http://") or url.startswith("https://")):
        if not url.startswith("/"):
            url = "/" + url
        url = _base_url() + url
    try:
        import requests  # type: ignore
        r = requests.post(url, json={"text": text, "dest": dest}, timeout=12)
        if r.status_code == 200:
            j = r.json()
            return str(j.get("text") or j.get("translated") or "")
    except Exception:
        return None
    return None


class _IdentityTranslator:
    def translate(self, text: str, dest: str = "ru") -> str:
        return text


def _get_translator() -> Any:
    if GoogleTranslator is None:
        return _IdentityTranslator()
    try:
        return GoogleTranslator()
    except Exception:
        return _IdentityTranslator()


def _translate(translator: Any, text: str, dest: str) -> str:
    if not text:
        return ""
    # 1) project endpoint (esli zadan)
    via = _translate_via_endpoint(text, dest)
    if via:
        return via
    # 2) googletrans (esli est)
    try:
        res = translator.translate(text, dest=dest)  # type: ignore
        if isinstance(res, str):
            return res
        return getattr(res, "text", text)  # type: ignore
    except Exception:
        return text


@dataclass
class AnalyzerConfig:
    target_lang: str = "ru"
    chunk_size: int = 1200
    max_chars: int = 200_000
    collection_name: str = "ester_doc_memory"
    encrypt: bool = True
    store_chroma: bool = True
    store_structured: bool = True


class ProactiveDocAnalyzer:
    def __init__(self, cfg: Optional[AnalyzerConfig] = None):
        if load_dotenv is not None:
            try:
                load_dotenv()  # type: ignore
            except Exception:
                pass

        self.cfg = cfg or AnalyzerConfig()
        self.ab = (os.getenv("AB_MODE") or "A").strip().upper()

        # components
        self.translator = _get_translator()
        self.emotion = _load_emotion_analyzer()
        self.memory = _load_memory_manager()

        # crypto
        self.cipher = None
        if self.cfg.encrypt and Fernet is not None:
            key = (os.getenv("ENCRYPTION_KEY") or "").strip()
            if not key:
                try:
                    key = Fernet.generate_key().decode("utf-8", errors="ignore")  # type: ignore
                except Exception:
                    key = ""
            try:
                if key:
                    self.cipher = Fernet(key.encode("utf-8"))  # type: ignore
            except Exception:
                self.cipher = None

        # chroma
        self.collection = None
        if self.cfg.store_chroma and chromadb is not None:
            try:
                persist = (os.getenv("PERSIST_DIR") or "data").strip() or "data"
                os.makedirs(persist, exist_ok=True)
                client = chromadb.PersistentClient(path=persist)  # type: ignore[attr-defined]
                name = (os.getenv("DOC_ANALYZER_COLLECTION") or self.cfg.collection_name).strip() or self.cfg.collection_name
                self.collection = client.get_or_create_collection(name)
            except Exception:
                self.collection = None

    def analyze_doc(self, doc_path_or_text: str, target_lang: Optional[str] = None, is_text: bool = False) -> Dict[str, Any]:
        tgt = (target_lang or self.cfg.target_lang).strip() or "ru"

        if is_text:
            chunks = ingest_text(doc_path_or_text, chunk_size=self.cfg.chunk_size, max_chars=self.cfg.max_chars)
            src = "text"
        else:
            chunks = ingest_file(doc_path_or_text, chunk_size=self.cfg.chunk_size, max_chars=self.cfg.max_chars)
            src = str(doc_path_or_text)

        analyzed: List[Dict[str, Any]] = []
        emo_hist: Dict[str, int] = {}

        for i, ch in enumerate(chunks):
            translated = _translate(self.translator, ch, tgt)
            emo = {}
            try:
                emo = self.emotion.analyze_emotion(translated)  # type: ignore[attr-defined]
            except Exception:
                emo = {"emotion": "neutral"}

            emo_name = str(emo.get("emotion", "neutral"))
            emo_hist[emo_name] = emo_hist.get(emo_name, 0) + 1

            anchor = f"anchor:{emo_name}|c=a+b|L4|fp={_fp(translated)}"

            analyzed.append(
                {
                    "i": i,
                    "text": translated,
                    "emotion": emo,
                    "anchor": anchor,
                }
            )

        # summary (szhatyy)
        themes = sorted(emo_hist.keys())
        summary_text = (
            f"Proactive analiz: tem(y)={', '.join(themes) if themes else 'none'}. "
            f"chunks={len(chunks)}, lang={tgt}, src={src}."
        )

        rep: Dict[str, Any] = {
            "ok": True,
            "ab": self.ab,
            "source": src,
            "target_lang": tgt,
            "chunks": len(chunks),
            "themes": themes,
            "hist": emo_hist,
            "summary": summary_text,
        }

        # store (A only)
        do_store = (self.ab != "B")
        rep["stored"] = bool(do_store)

        if do_store:
            for item in analyzed:
                text = str(item.get("text") or "")
                meta = dict(item.get("emotion") or {})
                meta["anchor"] = item.get("anchor")
                meta["src"] = src
                meta["i"] = int(item.get("i") or 0)
                meta["fp"] = _fp(text)
                payload = f"{text}|{meta['anchor']}"

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
                            ids=[f"{meta['fp']}-{meta['i']}"],
                        )
                    except Exception:
                        pass

                # structured memory best-effort
                if self.cfg.store_structured:
                    try:
                        self.memory.add_to_long_term(payload)
                    except Exception:
                        pass

        # return brief + first anchors for UX
        rep["anchors"] = [a.get("anchor") for a in analyzed[:3]]
        return rep

    def background_process(self, input_data: str, is_text: bool = False) -> Dict[str, Any]:
        return self.analyze_doc(input_data, is_text=is_text)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Proactive document analyzer (self-contained)")
    ap.add_argument("input", help="Put k faylu ili tekst (esli --text)")
    ap.add_argument("--text", action="store_true", help="Vkhod — eto tekst, a ne put")
    ap.add_argument("--lang", default="ru", help="Tselevoy yazyk")
    ap.add_argument("--chunk", type=int, default=1200, help="Razmer chanka (simvoly)")
    ap.add_argument("--max", type=int, default=200_000, help="Limit simvolov na vkhod")
    ap.add_argument("--no-encrypt", action="store_true", help="Ne shifrovat")

    args = ap.parse_args(argv)

    cfg = AnalyzerConfig(
        target_lang=str(args.lang),
        chunk_size=int(args.chunk),
        max_chars=int(args.max),
        encrypt=not bool(args.no_encrypt),
    )
    an = ProactiveDocAnalyzer(cfg)
    rep = an.analyze_doc(args.input, target_lang=args.lang, is_text=bool(args.text))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Esli net “file_ingest”, eto kak esli net medsestry na prieme: vrach vse ravno mozhet osmotret patsienta —
prosto medlennee i grubee (chitaem fayl sami i rezhem na kuski). Glavnyy printsip: kontur ne dolzhen padat
iz‑za otsutstviya odnogo assistenta; on dolzhen degradirovat i prodolzhat rabotu.
"""