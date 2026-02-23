#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bezopasnyy patching kriticheskikh faylov cherez A/B-sloty s avtootkatom.

YaVNYY MOST: c=a+b → izmeneniya v kriticheskikh faylakh tolko cherez A/B-sloty i proverku kompilyatsii.

SKRYTYE MOSTY:
  - Ashby: "stability by constraint" — patch libo prokhodit proverku, libo otkatyvaetsya.
  - Guyton/Hall: gomeostaz — net stabilnosti bez otritsatelnoy obratnoy svyazi (proverka -> otkat).

ZEMNOY ABZATs:
  Eto kak zamena predokhranitelya: snachala otklyuchaem pitanie, potom menyaem, potom proveryaem.
  Ne naoborot.
"""

import sys
import shutil
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def timestamp() -> str:
    """Generiruet metku vremeni dlya bekapov."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(filepath: Path, tag: str) -> Path:
    """
    Sozdaet bekap fayla s tegom i taymstampom.
    
    Returns:
        Path k sozdannomu bekapu
    """
    ts = timestamp()
    backup_path = filepath.parent / f"{filepath.name}.{tag}.{ts}.bak"
    shutil.copy2(filepath, backup_path)
    print(f"  [BACKUP] {backup_path.name}")
    return backup_path


def py_compile(filepath: Path) -> bool:
    """
    Proveryaet kompilyatsiyu Python-fayla cherez py_compile.
    
    Returns:
        True esli kompilyatsiya uspeshna, False inache
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(filepath)],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  [ERROR] Compile check failed: {e}")
        return False


def safe_patch(
    filepath: Path,
    patch_func: Callable[[str], str],
    description: str = "patch"
) -> bool:
    """
    Bezopasno primenyaet patch k faylu cherez A/B-sloty s avtootkatom.
    
    Args:
        filepath: put k faylu
        patch_func: funktsiya, prinimayuschaya soderzhimoe fayla i vozvraschayuschaya modifitsirovannoe
        description: opisanie patcha dlya logov
        
    Returns:
        True esli patch uspeshen, False esli otkat
        
    Raises:
        Exception esli kriticheskaya oshibka
    """
    print(f"\n[PATCH] {filepath}")
    print(f"  Opisanie: {description}")
    
    if not filepath.exists():
        print(f"  [SKIP] Fayl ne nayden")
        return False
    
    # 1. Chitaem original
    try:
        original_content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] Ne mogu prochitat fayl: {e}")
        return False
    
    # 2. Bekap A (original)
    backup_a = backup_file(filepath, "A")
    
    # 3. Primenyaem patch
    try:
        patched_content = patch_func(original_content)
    except Exception as e:
        print(f"  [ERROR] Patch-funktsiya upala: {e}")
        return False
    
    # Proverka chto chto-to izmenilos
    if patched_content == original_content:
        print(f"  [WARN] Patch nichego ne izmenil")
        return False
    
    # 4. Zapisyvaem v vremennyy fayl B
    temp_b = filepath.parent / f"{filepath.name}.B.new"
    try:
        temp_b.write_text(patched_content, encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] Ne mogu zapisat vremennyy fayl: {e}")
        return False
    
    # 5. Proveryaem kompilyatsiyu B
    if not py_compile(temp_b):
        print(f"  [FAIL] Kompilyatsiya B provalilas → otkat k A")
        temp_b.unlink(missing_ok=True)
        return False
    
    # 6. Bekap pered svopom
    backup_pre_swap = backup_file(filepath, "preSwap")
    
    # 7. SWAP: B → osnovnoy fayl
    try:
        shutil.copy2(temp_b, filepath)
        temp_b.unlink()
    except Exception as e:
        print(f"  [ERROR] Swap provalilsya: {e}")
        # otkat k preSwap
        shutil.copy2(backup_pre_swap, filepath)
        raise Exception(f"Swap failed for {filepath}")
    
    # 8. Finalnaya proverka kompilyatsii
    if not py_compile(filepath):
        print(f"  [FAIL] Kompilyatsiya posle svopa provalilas → otkat k preSwap")
        shutil.copy2(backup_pre_swap, filepath)
        raise Exception(f"Compile failed after swap for {filepath}")
    
    print(f"  [OK] Patch primenen + proveren")
    print(f"       Bekap A: {backup_a.name}")
    return True


# =============================================================================
# KONKRETNYE PATChI
# =============================================================================

def patch_providers_block(content: str) -> str:
    """
    Patchit blok initsializatsii Providers na kanonicheskuyu versiyu.
    """
    pattern = r'(?s)# --- 8\) Providers ---.*?\r?\n\r?\nPROVIDERS\s*=\s*ProviderPool\(\)\s*\r?\n'
    
    replacement = """# --- 8) Providers (canonical) ---
from providers.pool import ProviderPool, ProviderConfig, PROVIDERS
# --- 8) Providers end ---
"""
    
    if not re.search(pattern, content):
        raise ValueError("Pattern bloka Providers ne nayden")
    
    return re.sub(pattern, replacement, content)


def patch_add_stt_support(content: str) -> str:
    """
    Dobavlyaet STT-funktsional cherez Whisper.
    """
    # Proveryaem chto import esche ne dobavlen
    if "import whisper" in content or "from faster_whisper import" in content:
        raise ValueError("STT uzhe dobavlen")
    
    # Ischem blok importov v nachale
    import_section_end = content.find("\n# ---")
    if import_section_end == -1:
        raise ValueError("Ne nashel sektsiyu importov")
    
    stt_code = '''
# --- STT (Speech-to-Text) ---
try:
    from faster_whisper import WhisperModel
    STT_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    STT_AVAILABLE = True
except ImportError:
    STT_MODEL = None
    STT_AVAILABLE = False

def transcribe_audio(audio_path: str) -> str:
    """Raspoznavanie rechi → tekst (Whisper)"""
    if not STT_AVAILABLE:
        raise RuntimeError("STT ne dostupen (ustanovi: pip install faster-whisper)")
    segments, info = STT_MODEL.transcribe(audio_path, language="ru")
    return " ".join(seg.text for seg in segments).strip()
'''
    
    # Vstavlyaem pered pervym "# ---"
    return content[:import_section_end] + stt_code + content[import_section_end:]


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Glavnaya funktsiya - primenyaet patchi k tselevym faylam."""
    
    root = Path.cwd()
    
    targets = [
        root / "run_ester_fixed.py",
        root / "run_ester_fixed1.py",
    ]
    
    # Patch 1: Pereklyuchenie na canonical providers.pool
    print("\n" + "="*70)
    print("PATCh 1: Canonical Providers Block")
    print("="*70)
    
    for target in targets:
        if target.exists():
            try:
                safe_patch(
                    target,
                    patch_providers_block,
                    "Pereklyuchenie na canonical providers.pool"
                )
            except Exception as e:
                print(f"  [ERROR] {e}")
        else:
            print(f"\n[SKIP] {target} ne nayden")
    
    # Patch 2: Dobavlenie STT (optsionalno)
    # Raskommentiruy esli nuzhno
    # print("\n" + "="*70)
    # print("PATCh 2: STT Support (Whisper)")
    # print("="*70)
    # for target in targets:
    #     if target.exists():
    #         try:
    #             safe_patch(
    #                 target,
    #                 patch_add_stt_support,
    #                 "Dobavlenie STT cherez faster-whisper"
    #             )
    #         except Exception as e:
    #             print(f"  [ERROR] {e}")
    
    print("\n" + "="*70)
    print("[DONE] Vse patchi obrabotany")
    print("="*70)


if __name__ == "__main__":
    main()