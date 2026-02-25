# Contribution Guide

## Stil i instrumenty
- Formatirovanie: **black**, sortirovka importov: **isort**, lint: **ruff**, tipy: **mypy**.
- Vse konfigi — v `pyproject.toml`.  
- Hooks: yopre-commityo (tape/format, secrets), yopre-poshe (prohibition of private paths).

```bash
pip install pre-commit
pre-commit install --install-hooks
pre-commit run -a
