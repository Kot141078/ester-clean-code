# Quick Start

## Purpose

This guide provides the minimal local path to verify repository hygiene and compile integrity.

## Preconditions

- Python is installed and available in PATH.
- You are inside the repository root.
- Runtime secrets are outside git (`.env`, key files, private dumps).

## 1) Environment Setup

Create and activate a virtual environment if needed.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

## 2) Compile Checks

Run both compile gates before commit:

```bash
python -m compileall ESTER
python -m compileall modules
```

## 3) Repository Scanner

Run the safety scanner and require a clean result:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

Expected result: `HIGH=0` and `MEDIUM=0`.

## 4) Publish Hygiene

- Confirm no secrets were added.
- Confirm `git status` contains only intended files.
- Confirm docs mention L4/L4W constraints accurately.

## 5) Local Runtime Policy

- `.env` is local-only and ignored.
- `data/`, `state/`, `logs/` are runtime-only and ignored.
- Do not commit transient artifacts or personal data.

## Troubleshooting

- If scanner fails, remove sensitive content and rerun.
- If compileall fails, fix syntax/import errors before push.
- If status is noisy, verify `.gitignore` and cleanup local junk.
