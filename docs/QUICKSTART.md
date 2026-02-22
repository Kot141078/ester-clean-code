# Quick Start

## Purpose

This document is the minimal local runbook for repository checks.

## Preconditions

- Python is installed.
- You are in repository root.
- Secrets remain outside git.

## 1) Optional Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

## 2) Compile Gates

```bash
python -m compileall ESTER
python -m compileall modules
```

## 3) Scanner Gate

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

Expected result:

- HIGH findings = 0
- MEDIUM findings = 0

## 4) Git Hygiene

- Keep commits focused.
- Keep runtime files untracked.
- Confirm docs remain multiline and readable.

## 5) Runtime Exclusions

- `.env` is local-only.
- `data/`, `state/`, `logs/` are runtime-only.
- dumps and private artifacts must not be committed.

## 6) Before Push

- Re-run compile gates.
- Re-run scanner gate.
- Review staged diff for policy consistency.
