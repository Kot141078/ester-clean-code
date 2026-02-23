# Contribution Guide

## Stil i instrumenty
- Formatirovanie: **black**, sortirovka importov: **isort**, lint: **ruff**, tipy: **mypy**.
- Vse konfigi — v `pyproject.toml`.  
- Khuki: `pre-commit` (linty/format, sekrety), `pre-push` (zapret privatnykh putey).

```bash
pip install pre-commit
pre-commit install --install-hooks
pre-commit run -a
