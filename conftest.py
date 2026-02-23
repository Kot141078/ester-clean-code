# -*- coding: utf-8 -*-
"""Global test configuration for Ester project.

Tsel:
- Garantirovat, chto koren proekta dobavlen v sys.path ranshe site-packages.
- Eto ustranyaet kollizii s vneshnimi paketami `routes` i pozvolyaet
  korrektno importirovat lokalnye moduli vida `routes.*` i `modules.*`.

Drop-in:
- Ne menyaet logiku prilozheniya.
- Aktiven tolko pri zapuske pytest.
"""

import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)