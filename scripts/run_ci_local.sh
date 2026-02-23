# scripts/run_ci_local.sh
#!/usr/bin/env bash
set -euo pipefail

export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export DOD_LINES_MIN="${DOD_LINES_MIN:-0.85}"
export DOD_BRANCH_MIN="${DOD_BRANCH_MIN:-0.85}"

echo "➡️  Installing deps (if needed)"
python -m pip install -U pip wheel >/dev/null
if [[ -f "requirements.txt" ]]; then
  pip install -r requirements.txt
else
  pip install flask gunicorn requests pyyaml pytest pytest-cov coverage
fi

echo "➡️  Running unit tests"
pytest -q --disable-warnings --maxfail=1

echo "➡️  Running coverage"
pytest --cov=. --cov-branch \
       --cov-report=term-missing:skip-covered \
       --cov-report=xml:coverage.xml -q

echo "➡️  DoD (quality gate)"
bash ci/check_dod.sh

echo "✅ All good"
