# Release Checklist

## Scope
- Repository scaffold for public release
- Code license under AGPL-3.0-or-later
- Trademark and logo rights separated from code license

## License Source
- Source URL: https://www.gnu.org/licenses/agpl-3.0.txt
- Retrieved on (UTC): 2026-02-22
- LICENSE SHA256: 0D96A4FF68AD6D4B6F1F30F713B18D5184912BA8DD389F86AA7710DB079ABCB0

## Required Local Checks
- `powershell -ExecutionPolicy Bypass -File .\\tools\\scan_repo.ps1 -Root .` => PASS (HIGH=0, MEDIUM=0)
- `python -m compileall ESTER` => PASS
- `python -m compileall modules` => PASS
- `git status` clean after commit => TO_BE_FILLED

## Repository Publishing
- Desired repo order:
  1. `Kot141078/ester-clean-code`
  2. `Kot141078/ester-clean-release`
  3. `Kot141078/ester-core-clean`
  4. `Kot141078/ester-public-core`
- Chosen repo: TO_BE_FILLED
- Main branch pushed: TO_BE_FILLED

## Post-push Sanity
- GitHub license detection visible as AGPL-3.0: TO_BE_FILLED
- README and logo paths render correctly: TO_BE_FILLED
