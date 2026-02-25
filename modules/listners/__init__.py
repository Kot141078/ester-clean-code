# -*- coding: utf-8 -*-
"""modules/listners - paket-adapter dlya sovmestimosti s opechatkoy v importakh.

Naznachenie: perekhvatyvat obrascheniya k nesuschestvuyuschemu paketu `modules.listners` i perenapravlyat ikh v nastoyaschiy paket `listeners`.

MOSTY:
- Yavnyy: (Oshibki ↔ Korrektnost) - prozrachnyy sloy dlya obrabotki opechatki v imeni paketa.
- Skrytyy 1: (Razrabotka ↔ Ekspluatatsiya) — predotvraschaet sboy vypolneniya iz-za trivialnoy opechatki, povyshaya nadezhnost.
- Skrytyy 2: (Leksika ↔ Logika) — kompyuteru bez raznitsy odna bukva, a cheloveku svoystvenno oshibatsya; etot modul primiryaet ikh.

ZEMNOY ABZATs:
Predstavte dorozhnyy znak, where bukva sterlas. This adapter - kak remontnik, kotoryy znaet, chto “Listners” na samom dele oznachaet “Listeners”, i napravlyaet vas pravilno."""
import importlib, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def __getattr__(name: str):
    """Dinamicheski proksiruet podmoduli iz paketa listeners."""
    try:
        # Trying to import a submodule from a real listeners package
        module = importlib.import_module(f"listeners.{name}")
        # Keshiruem v modules.listners
        setattr(sys.modules[__name__], name, module)
        return module
    except ImportError as e:
        raise AttributeError(f"module 'modules.listners' has no attribute '{name}'") from e

# Disable __path__ to prevent searching for non-existent files.
__path__ = []
# c=a+b