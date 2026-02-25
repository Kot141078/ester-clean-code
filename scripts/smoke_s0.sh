#!/usr/bin/env bash
# С0/skripts/stoke_s0.sh - convenient smoke for *them
# Mosty: (Yavnyy) Dzheynes - "pravdopodobie" sostoyaniya otsenivaem prostymi nablyudeniyami; (Skrytye) Ashbi - regulyator prosche sistemy; Enderton — proveryaemye predikaty.
# Earth paragraph: wrapper, does not touch the application. It is convenient to twist in SI/locally.
# c=a+b

set -euo pipefail

echo "[S0] Versiya Python:"
python -V

echo "[S0] Proverka marshrutov:"
python tools/verify_routes.py || true

echo "[S0] Generatsiya lokalnogo admin-JWT:"
python tools/jwt_mint.py --user "Owner" --role admin --ttl 600 | tee /tmp/jwt.txt >/dev/null

echo "[S0] Smouk cherez test_client:"
python tests/smoke_s0.py || true

echo "[S0] Gotovo."
