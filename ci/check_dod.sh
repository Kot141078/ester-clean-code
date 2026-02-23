# ci/check_dod.sh
#!/usr/bin/env bash
set -euo pipefail

COVERAGE_XML="${COVERAGE_XML:-coverage.xml}"
DOD_JSON="${DOD_JSON:-dod_status.json}"
PY="${PYTHON_BIN:-python}"

if [[ ! -f "$COVERAGE_XML" ]]; then
  echo "❌ Ne nayden fayl pokrytiya: $COVERAGE_XML"
  # Sozdadim minimalnyy dod_status.json, chtoby artefakt vsegda suschestvoval.
  cat > "$DOD_JSON" <<JSON
{
  "ok": false,
  "reason": "coverage.xml_not_found",
  "file": "$COVERAGE_XML"
}
JSON
  exit 2
fi

# Porogovye znacheniya iz peremennykh okruzheniya (sm. CI env)
export DOD_LINES_MIN="${DOD_LINES_MIN:-0.85}"
export DOD_BRANCH_MIN="${DOD_BRANCH_MIN:-0.85}"

echo "➡️  Proverka Definition of Done (kachestvo):"
echo "    - Fayl pokrytiya: $COVERAGE_XML"
echo "    - Porog po strokam: ${DOD_LINES_MIN}"
echo "    - Porog po vetvleniyam: ${DOD_BRANCH_MIN}"

# Memory facade lint (strict by default)
echo "➡️  Proverka Memory Facade (no direct writes):"
"$PY" "$(dirname "$0")/memory_facade_lint.py"

# Skript sam sozdaet dod_status.json i vystavlyaet korrektnyy kod vykhoda
"$PY" "$(dirname "$0")/check_dod.py" \
  --coverage-xml "$COVERAGE_XML" \
  --output-json "$DOD_JSON"

rc=$?
if [[ $rc -eq 0 ]]; then
  echo "✅ DoD proyden. Podrobnosti v $DOD_JSON"
elif [[ $rc -eq 1 ]]; then
  echo "❌ DoD NE proyden (pokrytie nizhe poroga). Detali v $DOD_JSON"
else
  echo "❌ Oshibka vypolneniya proverki (rc=$rc). Sm. $DOD_JSON"
fi

exit $rc
