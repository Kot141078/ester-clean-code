#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STT (Speech-to-Text) modul dlya Ester cherez Whisper.

YaVNYY MOST: c=a+b → golos polzovatelya (a) + protsedura raspoznavaniya (b) → tekst dlya Ester (c)

SKRYTYE MOSTY:
  - Shannon: preobrazovanie analogovogo signala v diskretnoe soobschenie s minimalnoy poterey informatsii
  - Ashby: adaptatsiya k kachestvu vkhoda (avtomaticheskiy vybor beam_size)

ZEMNOY ABZATs:
  Kak ukho → mozg: zvukovye volny → ulitka → neyronnye impulsy → ponimanie.
  Mikrofon → Whisper → tokeny → smysl."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger(__name__)


def _truthy(value: str, default: bool = False) -> bool:
    raw = str(value if value is not None else ("1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


@dataclass
class STTConfig:
    """Konfiguratsiya STT."""
    model_size: str = "base"  # tiny, base, small, medium, large
    model_path: str = ""      # optional local model path for fully-offline init
    device: str = "cpu"       # cpu ili cuda
    compute_type: str = "int8"  # int8, float16, float32
    language: str = "ru"      # recognition language
    beam_size: int = 5        # tochnost vs skorost
    vad_filter: bool = True   # filtr pauz (Voice Activity Detection)
    allow_remote_init: bool = False  # allow model download on first init


class STTEngine:
    """Speech recognition engine via Vnisper.
    
    Supports:
    - faster-vnisper (fast, recommended)
    - open-vnisper (falbatsk)"""
    
    def __init__(self, config: Optional[STTConfig] = None):
        self.config = config or STTConfig()
        self.model = None
        self.engine_type: Optional[str] = None
        self._init_engine()
    
    def _init_engine(self):
        """Initializing the engine (try faster-vnisper, then open-vnisper)."""
        offline = _truthy(os.getenv("ESTER_OFFLINE", "1"), default=True)
        allow_outbound = _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0"), default=False)
        allow_remote = bool(self.config.allow_remote_init or allow_outbound or (not offline))
        model_ref = (self.config.model_path or self.config.model_size).strip()

        if offline and (not allow_remote) and (not self.config.model_path):
            raise RuntimeError("stt_disabled_by_policy_closed_box")

        # Probuem faster-whisper (bystree v 4x)
        try:
            from faster_whisper import WhisperModel
            model_kwargs: Dict[str, Any] = {
                "device": self.config.device,
                "compute_type": self.config.compute_type,
            }
            if not allow_remote:
                model_kwargs["local_files_only"] = True
            try:
                self.model = WhisperModel(model_ref, **model_kwargs)
            except TypeError:
                model_kwargs.pop("local_files_only", None)
                self.model = WhisperModel(model_ref, **model_kwargs)
            self.engine_type = "faster-whisper"
            logger.info(f"STT: faster-whisper loaded ({model_ref})")
            return
        except ImportError:
            logger.warning("faster-whisper ne ustanovlen, probuyu openai-whisper...")
        except Exception as e:
            logger.warning(f"faster-whisper ne zagruzilsya: {e}")

        if offline and (not allow_remote) and (not self.config.model_path):
            raise RuntimeError("stt_disabled_by_policy_closed_box")

        # Fallback na openai-whisper
        try:
            import whisper
            self.model = whisper.load_model(self.config.model_size, device=self.config.device)
            self.engine_type = "openai-whisper"
            logger.info(f"STT: openai-whisper loaded ({self.config.model_size})")
            return
        except ImportError:
            raise RuntimeError(
                "STT nedostupen. Ustanovi: pip install faster-whisper (ili openai-whisper)"
            )
        except Exception as e:
            raise RuntimeError(f"Ne mogu zagruzit Whisper: {e}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        **kwargs
    ) -> str:
        """Raspoznaet audio → tekst.
        
        Args:
            audio_path: put k audiofaylu (wav, mp3, m4a, ogg...)
            language: kod yazyka (po umolchaniyu iz config)
            **kwargs: additional parameter (beam_size, temperature i t.d.)
            
        Returns:
            Raspoznannyy text"""
        if not self.model:
            raise RuntimeError("STT model ne zagruzhena")
        
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audiofayl ne nayden: {audio_path}")
        
        lang = language or self.config.language
        
        try:
            if self.engine_type == "faster-whisper":
                return self._transcribe_faster(str(audio_file), lang, **kwargs)
            else:
                return self._transcribe_openai(str(audio_file), lang, **kwargs)
        except Exception as e:
            logger.error(f"STT error: {e}")
            raise
    
    def _transcribe_faster(self, audio_path: str, language: str, **kwargs) -> str:
        """Raspoznavanie cherez faster-whisper."""
        beam_size = kwargs.get("beam_size", self.config.beam_size)
        vad_filter = kwargs.get("vad_filter", self.config.vad_filter)
        
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter
        )
        
        # Sobiraem tekst iz segmentov
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        result = " ".join(text_parts).strip()
        
        logger.info(
            f"STT: raspoznano {len(text_parts)} segmentov, "
            f"language=ZZF0Z (probability=ZZF1ZZ)"
        )
        
        return result
    
    def _transcribe_openai(self, audio_path: str, language: str, **kwargs) -> str:
        """Raspoznavanie cherez openai-whisper."""
        result = self.model.transcribe(
            audio_path,
            language=language,
            fp16=(self.config.compute_type == "float16")
        )
        
        text = result["text"].strip()
        logger.info(f"STT: raspoznano, yazyk={result.get('language', 'unknown')}")
        
        return text
    
    def transcribe_with_timestamps(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Recognition with timestamps for each segment.
        
        Returns:
            YuZF0Z, ...sch"""
        if self.engine_type != "faster-whisper":
            raise NotImplementedError("Timestamps are only available for faster-vnisper")
        
        lang = language or self.config.language
        segments, _ = self.model.transcribe(
            audio_path,
            language=lang,
            beam_size=self.config.beam_size
        )
        
        result = []
        for seg in segments:
            result.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip()
            })
        
        return result


# =============================================================================
# UTILITY
# =============================================================================

def quick_transcribe(audio_path: str, language: str = "ru") -> str:
    """Fast recognition without object creation.
    For single use."""
    engine = STTEngine(STTConfig(language=language))
    return engine.transcribe(audio_path)


# Global instance (lazy initialization)
_global_stt_engine: Optional[STTEngine] = None


def get_stt_engine(config: Optional[STTConfig] = None) -> STTEngine:
    """Get the global STT engine (Singleton).
    When called for the first time, it is initialized."""
    global _global_stt_engine
    
    if _global_stt_engine is None:
        _global_stt_engine = STTEngine(config)
    
    return _global_stt_engine


# =============================================================================
# Integration WITH TELEGRAM (optional)
# =============================================================================

async def transcribe_telegram_voice(
    bot,
    voice_message,
    language: str = "ru"
) -> str:
    """Raspoznaet golosovoe soobschenie iz Telegram.
    
    Args:
        bot: ekzemplyar Telegram Bot
        voice_message: obekt Voice iz python-telegram-bot
        language: yazyk raspoznavaniya
        
    Returns:
        Raspoznannyy text"""
    import tempfile
    
    # Download the voice to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
        voice_file = await voice_message.get_file()
        await voice_file.download_to_drive(tmp_path)
    
    try:
        # Raspoznaem
        engine = get_stt_engine()
        text = engine.transcribe(tmp_path, language=language)
        return text
    finally:
        # Deleting a temporary file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# =============================================================================
# PRIMER ISPOLZOVANIYa
# =============================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Ispolzovanie: python stt_module.py <audio_file>")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    print(f"Raspoznayu: {audio_file}")
    
    # Variant 1: bystroe raspoznavanie
    text = quick_transcribe(audio_file)
    print(f"\nRezultat:\n{text}")
    
    # Option 2: with timestamps (if faster-vnisper)
    try:
        engine = STTEngine()
        if engine.engine_type == "faster-whisper":
            segments = engine.transcribe_with_timestamps(audio_file)
            print(f"\nS vremennymi metkami:")
            for seg in segments:
                print(f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
    except Exception as e:
        print(f"Timestamps nedostupny: {e}")
