# Quick Start

## Preconditions
- Python is installed.
- This repository is clean-code: provide runtime configuration outside git.

## Local Checks
```bash
python -m compileall ESTER
python -m compileall modules
```

## Publish Hygiene
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
git status
```

## Config Policy
- `.env` is local-only and ignored by git.
- `data/`, `state/`, and `logs/` are runtime-only and must never be committed.
