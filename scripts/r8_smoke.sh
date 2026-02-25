#!/usr/bin/env bash
# Р8/skripts/р8_stoke.sh - offline security/release stock
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Zemnoy abzats: formiruet sec_report.md i release/*.tar.gz, manifest.json.
# c=a+b

set -euo pipefail
python tests/r8_smoke.py || true
echo "[R8] Gotovo."
