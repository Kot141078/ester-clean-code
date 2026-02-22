# Contributing

## Ground Rules
- Keep changes focused and reviewable.
- No secrets, no personal data, and no runtime artifacts in commits.
- Respect repository boundaries defined by `LICENSE`, `NOTICE`, `TRADEMARK.md`, and `logo/LICENSE`.

## Before Opening a Pull Request
Run the scanner:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

Run compile checks:

```bash
python -m compileall ESTER
python -m compileall modules
```

## Pull Request Expectations
- Describe intent and risk.
- Provide test evidence.
- Update documentation when behavior or policy changes.

## License for Contributions
By contributing, you agree your contribution is provided under AGPL-3.0-or-later.
