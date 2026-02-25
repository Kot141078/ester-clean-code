# -*- coding: utf-8 -*-
"""messaging/styled_broadcast.py - obertka nad messaging.broadcast s gruppovym stilem.

MOSTY:
- (Yavnyy) send_styled_broadcast(keys, intent, adapt_kind=None) → ispolzuet styler i vyzyvaet iskhodnyy send_broadcast().
- (Skrytyy #1) Signatury bazovogo API ne menyayutsya; eto otdelnaya funktsiya/modul.
- (Skrytyy #2) Esli styler ne mozhet postroit profil — peredaet iskhodnyy intent.

ZEMNOY ABZATs:
Dazhe v obschem chat odno i to zhe soobschenie zvuchit “pod auditoriyu”, ostavayas odnim tekstom dlya vsey gruppy.

# c=a+b"""
from __future__ import annotations

from typing import List, Optional
from messaging.styler import render_for_keys
from messaging.broadcast import send_broadcast
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def send_styled_broadcast(keys: List[str], intent: str, adapt_kind: Optional[str] = None):
    text = render_for_keys(keys, intent, adapt_kind=adapt_kind)
    return send_broadcast(keys, text, adapt_kind=adapt_kind)