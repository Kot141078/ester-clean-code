# -*- coding: utf-8 -*-
"""
empathy_module.py — modul empatii i myagkogo “sotsialnogo upravleniya tonom” dlya Ester.

Prichina oshibki iz loga:
  name 'Any' is not defined
V originale ispolzovalsya tip Any, no on ne byl importirovan iz typing.

Chto sdelano:
  - Pochinka importa Any i bolshoy refaktoring: modul teper samodostatochnyy i NE padaet,
    dazhe esli otsutstvuyut vneshnie zavisimosti (Chroma/vektornyy stor/LLM-analizator).
  - Ubrany dubliruyuschiesya funktsii (dvoynoy _is_whois_query, dvoynoy load_from_db vne klassa).
  - Dobavlen prostoy lokalnyy analiz tona (bez numpy), s vozmozhnostyu podklyuchit “umnyy” analizator.
  - Memory empatii: best-effort, libo RAM-slovar, libo vneshniy collection (esli proekt ego daet).
  - Dobavleny udobnye khuki: observe(), get_user_state(), should_be_gentle().

Mosty (trebovanie):
  - Yavnyy most: ton/emotsii → zhurnal sobytiy (journal.record_event) kak L4‑sled (audit trail).
  - Skrytye mosty:
      (1) Infoteoriya ↔ privatnost: sokhranyaem fingerprint teksta (korotkiy hash), a ne syroy tekst (esli redact vklyuchen).
      (2) Kibernetika ↔ kod: A/B‑sloty otveta (FACT vs HUMAN) fiksiruyutsya v meta i mogut byt prinuditelno “A”.

ZEMNOY ABZATs: v kontse fayla.

# c=a+b
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# Optional: richer emotion scores if emotional_engine is available.
try:
    from emotional_engine import analyze_emotions as _ee_analyze_emotions  # type: ignore
except Exception:
    _ee_analyze_emotions = None

# -------------------- Konfiguratsiya cherez env --------------------
NODE_IDENTITY = os.getenv("NODE_IDENTITY", "node-unknown").strip() or "node-unknown"

# Vklyuchit “obogaschennuyu” pamyat (obrezka istorii, dopolnitelnye polya)
EMPATHY_V2_ENABLED = os.getenv("EMPATHY_V2_ENABLED", "1").strip() != "0"

# Maksimalnaya dlina istorii na polzovatelya (0 = ne khranit, no analizirovat mozhno)
try:
    EMPATHY_HISTORY_MAX = int(os.getenv("EMPATHY_HISTORY_MAX", "80").strip())
except Exception:
    EMPATHY_HISTORY_MAX = 80

# Kak silno “smyagchat” otvety po umolchaniyu (1..10)
try:
    EMPATHY_DEFAULT_LEVEL = int(os.getenv("EMPATHY_DEFAULT_LEVEL", "5").strip())
except Exception:
    EMPATHY_DEFAULT_LEVEL = 5

# Redaktirovanie: ne khranit syroy tekst v pamyati empatii (privacy-by-default)
EMPATHY_REDACT = os.getenv("EMPATHY_REDACT", "1").strip() != "0"

# Ne predlagat podpiski/plany po umolchaniyu (v originale byla vstavka pro podpisku)
EMPATHY_ALLOW_UPSELL = os.getenv("EMPATHY_ALLOW_UPSELL", "0").strip() == "1"

# Prinuditelnyy “slot” otveta: A=tolko fakty, B=chelovecheskoe obyasnenie
EMPATHY_FORCE_SLOT = os.getenv("EMPATHY_FORCE_SLOT", "").strip().upper()  # "A"/"B"/""


# -------------------- Vnutrenniy RAM-store (fallback) --------------------
# Format: user_id -> json string (istoriya)
_EMPATHY_RAM_DB: Dict[str, str] = {}


def _writer_enabled() -> bool:
    """Esli proekt zapreschaet zapis (naprimer, read-only rezhim), mozhno otklyuchit."""
    return os.getenv("ESTER_WRITER_ENABLED", "1").strip() != "0"


def get_empathy_collection() -> Any:
    """Best-effort: vernut backend dlya khraneniya.

    Podderzhka:
      - dict (RAM-rezhim)
      - obekt s .get/.upsert/.add/.delete (Chroma-like)

    Nikogda ne brosaet isklyuchenie.
    """
    for mod_name, attr in [
        ("modules.memory.empathy_store", "get_empathy_collection"),
        ("modules.memory.store", "get_empathy_collection"),
        ("modules.memory.memory_hub", "get_empathy_collection"),
    ]:
        try:
            mod = __import__(mod_name, fromlist=[attr])
            fn = getattr(mod, attr, None)
            if callable(fn):
                coll = fn()
                if coll is not None:
                    return coll
        except Exception:
            pass
    return _EMPATHY_RAM_DB


# -------------------- Utility --------------------
@dataclass
class ToneAnalysis:
    tone: str
    polarity: float  # [-1..+1]
    anxiety: float   # [0..1]
    interest: float  # [0..1]
    warmth: float    # [0..1]
    flags: Dict[str, bool]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone": self.tone,
            "polarity": self.polarity,
            "anxiety": self.anxiety,
            "interest": self.interest,
            "warmth": self.warmth,
            "flags": dict(self.flags),
            "notes": self.notes,
        }


_NEG = {
    "besit", "dostal", "nadoelo", "zadolbal", "plokho", "uzhas", "koshmar", "gavno", "idiot",
    "oshibka", "slomalos", "ne rabotaet", "pochemu", "kakogo", "tupo", "khren",
}
_POS = {"spasibo", "klass", "otlichno", "super", "khorosho", "molodets", "kruto", "👍", "🙂", "😁", "😄"}
_ANX = {"strashno", "trevozhno", "opasno", "panika", "voln", "perezhiva", "somnevayus"}
_URG = {"srochno", "seychas", "nemedlenno", "pryamo seychas", "bystro"}
_INTEREST = {"interesno", "ideya", "vopros", "pochemu", "kak", "chto esli", "vozmozhno"}
_WARM = {"pozhaluysta", "mozhesh", "davay", "pomogi", "druzheski", "spokoyno"}

_RE_PUNCT = re.compile(r"[!?.]{2,}")
_RE_ALLCAPS = re.compile(r"\b[A-YaA-Z]{3,}\b")


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _fingerprint(text: str) -> str:
    import hashlib
    h = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
    return h[:8].hex()


def dummy_llm_analyze_tone(message: str) -> Dict[str, Any]:
    """Lokalnyy analiz (bez LLM). Nikogda ne padaet."""
    msg = _norm_text(message).lower()
    if not msg:
        return ToneAnalysis(
            tone="neytralnyy", polarity=0.0, anxiety=0.0, interest=0.0, warmth=0.0, flags={}, notes="empty"
        ).to_dict()

    flags: Dict[str, bool] = {
        "urgent": any(w in msg for w in _URG),
        "anxious": any(w in msg for w in _ANX),
        "negative": any(w in msg for w in _NEG),
        "positive": any(w in msg for w in _POS),
        "question": "?" in msg or any(w in msg for w in ("kak", "pochemu", "chto", "gde", "kogda")),
        "caps": bool(_RE_ALLCAPS.search(message or "")),
        "punct": bool(_RE_PUNCT.search(message or "")),
    }

    polarity = 0.0
    if flags["negative"] and not flags["positive"]:
        polarity -= 0.6
    if flags["positive"] and not flags["negative"]:
        polarity += 0.6
    if flags["caps"] or flags["punct"]:
        polarity -= 0.1 if polarity <= 0 else 0.05

    anxiety = 0.0 + (0.6 if flags["anxious"] else 0.0) + (0.2 if flags["urgent"] else 0.0)
    interest = 0.1 + (0.5 if any(w in msg for w in _INTEREST) else 0.0) + (0.2 if flags["question"] else 0.0)
    warmth = 0.1 + (0.4 if any(w in msg for w in _WARM) else 0.0) + (0.2 if flags["positive"] else 0.0)

    anxiety = _clip(anxiety, 0.0, 1.0)
    interest = _clip(interest, 0.0, 1.0)
    warmth = _clip(warmth, 0.0, 1.0)
    polarity = _clip(polarity, -1.0, 1.0)

    if polarity < -0.4 or flags["negative"]:
        tone = "razdrazhennyy/negativnyy"
    elif flags["anxious"] or anxiety > 0.5:
        tone = "trevozhnyy"
    elif flags["positive"] and polarity > 0.2:
        tone = "pozitivnyy"
    else:
        tone = "neytralnyy"

    return ToneAnalysis(
        tone=tone,
        polarity=polarity,
        anxiety=anxiety,
        interest=interest,
        warmth=warmth,
        flags=flags,
        notes="heuristic",
    ).to_dict()


def _safe_json_loads(s: Optional[str]) -> List[Dict[str, Any]]:
    try:
        if not s:
            return []
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _trim_history(hist: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not EMPATHY_V2_ENABLED:
        return hist
    if EMPATHY_HISTORY_MAX <= 0:
        return []
    return hist if len(hist) <= EMPATHY_HISTORY_MAX else hist[-EMPATHY_HISTORY_MAX:]


def _sanitize_record_for_storage(rec: Dict[str, Any]) -> Dict[str, Any]:
    if not EMPATHY_REDACT:
        return rec
    msg = rec.get("message") or ""
    fp = rec.get("fp") or _fingerprint(str(msg))
    return {
        "ts": rec.get("ts"),
        "fp": fp,
        "analysis": rec.get("analysis") or {},
        "meta": rec.get("meta") or {},
    }


# -------------------- Osnovnoy klass --------------------
class EmpathyModule:
    """Empatiya: analiz → vybor stilya → pamyat.

    Nichego ne trebuet izvne: esli proekt daet storage/zhurnal — ispolzuem, inache tikhiy fallback.
    """

    def __init__(
        self,
        user_id: str = "default_user",
        empathy_level: int = EMPATHY_DEFAULT_LEVEL,  # 1..10
        *,
        analyzer: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.user_id = user_id
        self.empathy_level = int(empathy_level) if empathy_level is not None else EMPATHY_DEFAULT_LEVEL
        self.empathy_level = 1 if self.empathy_level < 1 else 10 if self.empathy_level > 10 else self.empathy_level
        self.analyzer = analyzer or dummy_llm_analyze_tone
        self.user_history: List[Dict[str, Any]] = []
        self.load_from_db()

    def analyze_user_message(self, message: str) -> Dict[str, Any]:
        """Analiziruet ton soobscheniya i vybiraet 'prefix' i stil."""
        message = _norm_text(message)
        try:
            analysis = self.analyzer(message) or {}
        except Exception:
            analysis = dummy_llm_analyze_tone(message)
        # Enrich with full emotional scores if available (non-fatal).
        if _ee_analyze_emotions:
            try:
                analysis["emo_scores"] = _ee_analyze_emotions(message, user_ctx=None) or {}
            except Exception:
                pass

        rec: Dict[str, Any] = {
            "ts": time.time(),
            "message": message,
            "fp": _fingerprint(message),
            "analysis": analysis,
            "meta": {"node": NODE_IDENTITY},
        }
        self.user_history.append(_sanitize_record_for_storage(rec))
        self.user_history = _trim_history(self.user_history)

        tone = (analysis.get("tone") or "").lower()
        low = message.lower()

        if EMPATHY_ALLOW_UPSELL and ("podpisk" in low or "plan" in low):
            return {
                "response_style": "myagkiy",
                "prefix": "Esli interesno — mogu predlozhit variant po planu, no bez speshki: snachala reshim zadachu. ",
                "analysis": analysis,
            }

        if "razdrazh" in tone or "negativ" in tone or (analysis.get("flags") or {}).get("negative"):
            return {
                "response_style": "empatiya",
                "prefix": "Ponyal. Eto realno mozhet besit. Davay spokoyno razlozhim po shagam i dobem. ",
                "analysis": analysis,
            }

        if "trevozh" in tone or (analysis.get("flags") or {}).get("anxious"):
            return {
                "response_style": "podderzhka",
                "prefix": "Ok, vizhu trevogu. Davay snachala snimem neopredelennost: chto izvestno, chto net, i kakoy sleduyuschiy shag. ",
                "analysis": analysis,
            }

        return {"response_style": "standart", "prefix": "", "analysis": analysis}

    def generate_friendly_response(self, base_response: str, analysis_pack: Dict[str, Any]) -> str:
        """Dobavlyaet k otvetu prefix i legkiy yumor (esli umestno)."""
        prefix = analysis_pack.get("prefix", "") or ""
        style = (analysis_pack.get("response_style") or "").lower()

        slot = (EMPATHY_FORCE_SLOT or "B").upper()
        if slot == "A":
            prefix = ""

        humor_add = ""
        if self.empathy_level >= 8 and slot != "A":
            if style not in ("podderzhka", "empatiya"):
                humor_add = " 🙂"

        return f"{prefix}{base_response}{humor_add}"

    def suggest_improvement(self) -> str:
        if self.empathy_level >= 7:
            return "Esli khochesh — skazhi, chto uluchshit v stile/formate. Bez davleniya."
        return "Esli budet zhelanie — mozhno skazat, chto uluchshit."

    def save_to_db(self) -> None:
        """Persist empathy history (best-effort)."""
        if EMPATHY_HISTORY_MAX == 0:
            return
        try:
            data = json.dumps(self.user_history, ensure_ascii=False)
            metadata = {
                "user_id": self.user_id,
                "timestamp": time.time(),
                "type": "empathy_history",
                "node": NODE_IDENTITY,
            }
            coll = get_empathy_collection()

            if isinstance(coll, dict):
                coll[self.user_id] = data
                return

            if _writer_enabled():
                try:
                    upsert = getattr(coll, "upsert", None)
                    if callable(upsert):
                        upsert(documents=[data], metadatas=[metadata], ids=[self.user_id])
                        return
                except Exception:
                    pass

                try:
                    delete = getattr(coll, "delete", None)
                    if callable(delete):
                        delete(ids=[self.user_id])
                except Exception:
                    pass
                add = getattr(coll, "add", None)
                if callable(add):
                    add(documents=[data], metadatas=[metadata], ids=[self.user_id])
        except Exception as e:
            log.error("[EmpathyModule] Save failed: %s", e)

    def load_from_db(self) -> None:
        """Load empathy history (best-effort)."""
        coll = get_empathy_collection()
        try:
            raw_data = None
            if isinstance(coll, dict):
                raw_data = coll.get(self.user_id)
            else:
                get_ = getattr(coll, "get", None)
                if callable(get_):
                    result = get_(ids=[self.user_id])
                    docs = (result.get("documents") or []) if isinstance(result, dict) else []
                    raw_data = docs[0] if docs else None
            self.user_history = _safe_json_loads(raw_data)
        except Exception as e:
            log.warning("[EmpathyModule] Load failed: %s", e)
            self.user_history = []
        self.user_history = _trim_history(self.user_history)

    def observe(self, user_text: str, bot_text: Optional[str] = None, *, slot: str = "B") -> Dict[str, Any]:
        """Udobnyy khuk: analiziruet soobschenie, optsionalno pishet v zhurnal sobytiy."""
        pack = self.analyze_user_message(user_text)
        pack["slot"] = slot

        try:
            from modules.memory.journal import record_event  # type: ignore
            a = pack.get("analysis") or {}
            tone = a.get("tone", "unknown")
            record_event(
                f"empathy:tone={tone}",
                etype="empathy",
                result="ok",
                extra={"user_id": self.user_id, "tone": tone, "slot": slot},
            )
        except Exception:
            pass

        try:
            self.save_to_db()
        except Exception:
            pass

        return pack

    def get_user_state(self) -> Dict[str, Any]:
        last = self.user_history[-1] if self.user_history else {}
        a = (last.get("analysis") or {}) if isinstance(last, dict) else {}
        return {
            "user_id": self.user_id,
            "history_len": len(self.user_history),
            "tone": a.get("tone"),
            "polarity": a.get("polarity"),
            "anxiety": a.get("anxiety"),
            "interest": a.get("interest"),
            "warmth": a.get("warmth"),
        }

    def should_be_gentle(self) -> bool:
        st = self.get_user_state()
        try:
            anx = float(st.get("anxiety") or 0.0)
        except Exception:
            anx = 0.0
        tone = (st.get("tone") or "").lower()
        return anx >= 0.55 or "negativ" in tone or "razdrazh" in tone

    # ---- Runtime hooks for EsterCore broadcast_event ----
    def on_message_received(
        self,
        text: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        address_as: Optional[str] = None,
    ) -> Dict[str, Any]:
        # EmpathyModule is per-user; hub/router may pass user_id.
        # We just observe text and update internal state.
        _ = user_id, user_name, address_as
        return self.observe(text, slot="B")

    def get_reply_tone(self, address_as: Optional[str] = None) -> str:
        """
        Korotkaya instruktsiya po tonu dlya prompta.
        Ne zapreschaet «imya/laskovost», a reguliruet umestnost.
        """
        st = self.get_user_state()
        tone = (st.get("tone") or "neytralnyy").strip()
        try:
            warmth = float(st.get("warmth") or 0.0)
        except Exception:
            warmth = 0.0
        try:
            anxiety = float(st.get("anxiety") or 0.0)
        except Exception:
            anxiety = 0.0
        try:
            interest = float(st.get("interest") or 0.0)
        except Exception:
            interest = 0.0

        parts: List[str] = [f"Ton: {tone}"]
        if warmth >= 0.55:
            parts.append("teplo/berezhno")
        if anxiety >= 0.55:
            parts.append("podderzhka/uspokoenie")
        if interest >= 0.60:
            parts.append("vovlekay i poyasnyay")
        if address_as:
            parts.append(f"obraschenie: {address_as} (umerenno, esli umestno)")

        # Ne zapreschaem frazy polnostyu — tolko po umestnosti.
        parts.append("frazy pro 'sistemy/gotovnost' — tolko po zaprosu")
        return " | ".join(parts)


# -------------------- Detektory intentov --------------------
def is_daily_contacts_query(text: str) -> bool:
    """Detektor zaprosov k zhurnalu kontaktov za den."""
    low = (text or "").strip().lower()
    if not low:
        return False

    patterns = [
        "s kem ty govorila segodnya",
        "s kem ty obschalas segodnya",
        "kto pisal segodnya",
        "kto tebe pisal segodnya",
        "kto segodnya pisal",
        "s kem ty razgovarivala segodnya",
        "s kem ty obschalas krome menya",
        "krome menya s kem",
        "kto krome menya",
        "pokazhi zhurnal dnya",
        "pokazhi kto pisal",
        "kto byl segodnya",
        "spisok kontaktov segodnya",
        "aktivnost za segodnya",
        "kto zakhodil segodnya",
    ]

    if any(p in low for p in patterns):
        return True

    has_target = "s kem" in low or "kto" in low
    has_time = "segodnya" in low or "za den" in low
    has_action = any(m in low for m in ("govor", "obschal", "razgovor", "pisal", "byl", "zakhod"))

    return (has_target and has_time and has_action) or (has_time and "zhurnal" in low)


def is_whois_query(text: str) -> Optional[str]:
    """Encoding-safe detector for queries like 'kto takoy <Imya>'.

    VAZhNO: regex soderzhit kirillitsu tolko cherez \\uXXXX, chtoby ne stradat ot polomannoy kodirovki iskhodnikov.
    """
    try:
        s = (text or "").strip()
        if not s:
            return None

        pat_whois = (
            r"(?i)\b(?:\u043a\u0442\u043e)\s+"
            r"(?:\u0442\u0430\u043a\u043e\u0439|\u0442\u0430\u043a\u0430\u044f|\u044d\u0442\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )
        pat_tell = (
            r"(?i)\b(?:\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438)\s+(?:\u043f\u0440\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )
        pat_know = (
            r"(?i)\b(?:\u0447\u0442\u043e)\s+(?:.*\s+)?(?:\u0437\u043d\u0430\u0435\u0448\u044c)\s+(?:\u043e|\u043e\u0431)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        for pat in (pat_whois, pat_tell, pat_know):
            m = re.search(pat, s)
            if m:
                name = (m.group(1) or "").strip()
                name = re.sub(r"\s{2,}", " ", name)
                return name if len(name) >= 2 else None
        return None
    except Exception:
        return None


__all__ = [
    "EmpathyModule",
    "dummy_llm_analyze_tone",
    "get_empathy_collection",
    "is_daily_contacts_query",
    "is_whois_query",
    "EMPATHY_V2_ENABLED",
    "EMPATHY_HISTORY_MAX",
]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Empatiya — eto ne “sladost”, a sistema dempfirovaniya: kak amortizator v podveske.
Ona ne delaet mashinu bystree, ona delaet ee upravlyaemoy na yamakh.
Inzhenerno:
- ton/trevoga/srochnost — eto vkhodnye signaly regulyatora;
- esli ikh ne fiksirovat, sistema nachinaet “raskachivatsya” (perespam, povtornye obyasneniya, razdrazhenie).
Poetomu my khranim korotkiy fingerprint i metriki — kak datchiki vibratsii, a ne polnyy razgovor.
"""