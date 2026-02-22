# Release Checklist

## Scope
- Public clean-code repository.
- Code license: AGPL-3.0-or-later.
- Trademark and logo rights separated from code license.

## License Source
- Source URL: https://www.gnu.org/licenses/agpl-3.0.txt
- Retrieved on (UTC): 2026-02-22
- LICENSE SHA256: 0D96A4FF68AD6D4B6F1F30F713B18D5184912BA8DD389F86AA7710DB079ABCB0

## Required Local Checks
- `powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .` => PASS (HIGH=0, MEDIUM=0)
- `python -m compileall ESTER` => PASS
- `python -m compileall modules` => PASS
- `git status` clean after commit => PASS

## Post-Push Sanity
- GitHub license detection shows AGPL-3.0: CHECK
- README renders properly: CHECK
- Docs files render properly: CHECK
