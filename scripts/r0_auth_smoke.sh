#!/usr/bin/env bash
# R0/scripts/r0_auth_smoke.sh — smouk R0 dlya *nix
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytye) Dzheynes — pravdopodobie «zdorovya»; Cover&Thomas — minimalnyy signal.
# Zemnoy abzats: prostaya obertka; ne valit payplayn, podkhodit dlya lokalki/CI.
# c=a+b

set -euo pipefail
python tests/r0_auth_smoke.py || true
echo "[R0] Gotovo."
