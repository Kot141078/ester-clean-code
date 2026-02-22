# -*- coding: utf-8 -*-
"""
modules/computer_use/stabilizer_plus.py — Stabilizer++: ozhidanie 'network idle' i zatukhaniya CSS-animatsiy.

MOSTY:
- Yavnyy: (Deystviya ↔ Stabilnost) — posle klikov/vvoda zhdem setevoe «zatishe» i okonchanie animatsiy.
- Skrytyy №1: (Frontend ↔ Nadezhnost) — menshe gonki sostoyaniy: DOM menyaetsya rezhe «na letu».
- Skrytyy №2: (Polzovatel ↔ Ponimanie) — parametry prozrachny: millisekundy vidny v logakh shaga.

ZEMNOY ABZATs:
Eto «vydokh posle dvizheniya»: nazhali knopku — podozhdali, poka stranitsa dogovorit poslednie zaprosy i perestanet shevelitsya, i tolko potom prodolzhaem.

c=a+b
"""
from __future__ import annotations
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

async def wait_network_idle(page, timeout_ms: int = 1500) -> bool:
    """Zhdem sostoyanie 'networkidle' (esli dvizhok ego podderzhivaet). Vozvraschaet True, esli otzhidanie proshlo uspeshno."""
    if timeout_ms <= 0:
        return False
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return True
    except Exception:
        return False

async def wait_animations(page, timeout_ms: int = 800) -> bool:
    """
    Zhdem zatukhaniya aktivnykh animatsiy: oprashivaem window.getAnimations().
    Zadacha — dozhdatsya, kogda ikh ne ostanetsya ili vyydet timeout.
    """
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