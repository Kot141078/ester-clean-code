#!/usr/bin/env bash
# -*- coding: utf-8 -*-
: <<'DOC'
Mosty:
- Yavnyy: (Matritsa ↔ P2P) obedinennyy smouk: bazovye testy + P2P blok.
- Skrytyy #1: (Sovmestimost ↔ Nenarushaemost) suschestvuyuschiy scripts/smoke_matrix.sh ne trogaem — prosto zovem.
- Skrytyy #2: (Avtonomnost ↔ Planirovschik) podkhodit dlya cron/CI/ruchnogo zapuska.

Zemnoy abzats:
Eto «master-tester»: esli bazovyy smouk proyden — dobivaem P2P, inache srazu padaem.

c=a+b
DOC
set -euo pipefail

if [[ -x "scripts/smoke_matrix.sh" ]]; then
  echo "[matrix] base smoke_matrix.sh"
  bash scripts/smoke_matrix.sh
else
  echo "[matrix] WARN: scripts/smoke_matrix.sh not found — propusk bazovogo smouka."
fi

echo "[matrix] p2p smoke"
bash scripts/smoke_p2p.sh
echo "[matrix] OK"
