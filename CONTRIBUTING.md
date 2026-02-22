# Contributing

## Ground Rules
- Keep changes focused and reviewable.
- Keep secrets, personal data, and runtime artifacts out of commits.
- Follow the license and trademark boundaries described in `LICENSE`, `NOTICE`, and `TRADEMARK.md`.

## Development Checks
Run before opening a pull request:
- `powershell -ExecutionPolicy Bypass -File .\\tools\\scan_repo.ps1 -Root .`
- `python -m compileall .`

## Pull Requests
- Describe intent, risks, and test evidence.
- Update docs when behavior or policy changes.
- Keep commit messages clear and specific.

## License for Contributions
By contributing, you agree your contribution is provided under AGPL-3.0-or-later.
