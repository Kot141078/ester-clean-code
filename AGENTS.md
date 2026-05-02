# Repository Guidelines

## Project Structure & Module Organization

Ester is a Python-first runtime repository. Core implementation lives in `modules/`, HTTP and UI entry points in `routes/`, service adapters in `bridges/`, `cloud/`, `listeners/`, and provider wiring in `providers/`. Operational tools are in `tools/` and `scripts/`. Architecture notes and public implementation guidance live in `docs/`. Tests mirror runtime areas under `tests/`, for example `tests/test_synaps_*.py` covers `modules/synaps/` and related CLI tools.

Do not store private runtime state, secrets, local memories, tokens, or machine-specific logs in this public repository.

## Build, Test, and Development Commands

Use Python 3.10+; Python 3.11 is the main tool target in config.

```bash
python -m pytest
python -m pytest tests/test_synaps_protocol.py -q
python -m py_compile modules/synaps/protocol.py
python tools/route_registry_check.py
git diff --check
```

`pytest` runs the test suite configured by `pyproject.toml`. `py_compile` is useful for focused runtime files. `route_registry_check.py` validates route registration consistency. `git diff --check` catches whitespace issues before commit.

## Coding Style & Naming Conventions

Use 4-space indentation, typed function signatures where practical, and small functions with explicit gate checks for privileged behavior. Python modules and test files use `snake_case`; constants use `UPPER_SNAKE_CASE`; dataclasses and classes use `PascalCase`.

Ruff, Black, isort, and mypy settings are defined in `pyproject.toml`; `ruff.toml` also carries repository lint defaults. Preserve existing style in touched files and avoid broad formatting-only rewrites.

## Testing Guidelines

Tests use `pytest`. Name tests `test_<behavior>` and keep fixtures local unless reused across several files. For SYNAPS and other safety-sensitive code, include dry-run, fail-closed, and apply-path assertions. New gates should prove that unsafe flags, missing confirmations, and unexpected payloads do not write state.

## Commit & Pull Request Guidelines

Recent commits use concise Conventional Commit style, such as `feat: add expected codex report observer` or `fix: require worker capability for codex runner`. Keep commits focused and include tests with behavior changes.

Pull requests should describe the changed runtime surface, safety gates, commands run, and any intentional exclusions. Link related issues or docs when applicable.

## Security & Configuration Tips

Never commit `.env`, tokens, payload dumps, private memory, vector stores, or local quarantine contents. Prefer dry-run defaults and explicit confirmation phrases for any action that writes, sends, schedules, or starts workers.
