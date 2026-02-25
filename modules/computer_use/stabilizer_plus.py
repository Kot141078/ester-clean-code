# -*- coding: utf-8 -*-
"""modules/computer_use/stabilizer_plus.py — Stabilizer++: ozhidanie 'network idle' i zatukhaniya CSS-animatsiy.

MOSTY:
- Yavnyy: (Deystviya ↔ Stabilnost) - posle klikov/vvoda zhdem setevoe “zatishe” i okonchanie animatsiy.
- Skrytyy No. 1: (Frontend ↔ Nadezhnost) - menshe gonki sostoyaniy: DOM menyaetsya rezhe “na letu”.
- Skrytyy No. 2: (Polzovatel ↔ Ponimanie) - parameter prozrachny: millisekundy vidny v logakh shaga.

ZEMNOY ABZATs:
Eto “vydokh posle dvizheniya”: nazhali knopku - podozhdali, poka stranitsa dogovorit poslednie zaprosy i perestanet shevelitsya, i tolko potom prodolzhaem.

c=a+b"""
from __future__ import annotations
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

async def wait_network_idle(page, timeout_ms: int = 1500) -> bool:
    """We are waiting for the state of the network (if the engine supports it). Returns Three if the waiting was successful."""
    if timeout_ms <= 0:
        return False
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return True
    except Exception:
        return False

async def wait_animations(page, timeout_ms: int = 800) -> bool:
    """We are waiting for the active animations to fade out: we poll Windows.getAnimations().
    The task is to wait until there are no more of them left or the timeout goes out."""
    if timeout_ms <= 0:
        return False
    waited = 0
    step = 120
    try:
        while waited < timeout_ms:
            cnt = await page.evaluate("""() => {
                try {
                    const list = (typeof document.getAnimations === 'function') ? document.getAnimations() : [];
                    return Array.from(list).filter(a => a && a.playState === 'running').length;
                } catch(e){ return 0; }
            }""")
            if (cnt or 0) <= 0:
                return True
            await page.wait_for_timeout(step)
            waited += step
    except Exception:
        return False
    return False

# c=a+b