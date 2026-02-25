# -*- coding: utf-8 -*-
"""ESTER/routes/register_guard_alias.py - sovmestimost.

Mosty:
- Yavnyy: (ESTER.* ↔ routes.*) — reeksport simvolov bez obratnogo importa (isklyuchaet tsikl).
- Skrytyy #1: (Starye importy ↔ Novye fayly) - kod, zovuschiy ESTER.routes.*, prodolzhaet rabotat.
- Skrytyy #2: (Instrumenty registratsii ↔ Pomoschniki) - nalichie register(app) udovletvoryaet avtoproverki.

Zemnoy abzats:
Eto “perekhodnaya ramka” mezhdu starym i novym shkafom: bolty sovpadayut, provoda ne perekrucheny, vse nadezhno.

# c=a+b"""
from __future__ import annotations

# Important: import in one direction only, so as not to create a cycle.
from routes.register_guard_alias import (  # type: ignore
    AddRuleGuard,
    import_route_module,
    with_guard_if_B,
    register,
)

__all__ = ["AddRuleGuard", "import_route_module", "with_guard_if_B", "register"]
