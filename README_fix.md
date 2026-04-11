# Goryachiy fiks: /portal 500, /favicon.ico 500, .env parsing

## What is this
A set of drop-in files without editing existing modules: portal alias, favicon-false and soft loading of yo.enve through yositekostomise.pye.

## How to apply
1. **Unpack** into the root of the project (yD:eester-prozhektyo) so that the files go like this:
   - `sitecustomize.py`
   - `routes\portal_routes_alias.py`
   - `routes\favicon_fallback_routes.py`
   - `tools\dotenv_sanitize.py`
   - `scripts\patch_extra_routes.ps1`
   - `scripts\smoke_portal.ps1`
   - `config\.env.example`
2. **Zaregistrirovat routy** (odin raz):
   ```powershell
   cd <repo-root>
   .\scripts\patch_extra_routes.ps1
   ```
3. **Perezapustit** prilozhenie.
4. **Smoke‑test**:
   ```powershell
   .\scripts\smoke_portal.ps1 -Port 8080
   ```
5. **Check .env** (optional):
   ```powershell
   python tools\dotenv_sanitize.py --env .env
   Get-Content data\.env.sanitize.log -Raw
   ```

## Why is it fixing your mistake
- `/portal` teper otrisovyvaetsya napryamuyu iz `templates/portal.html` cherez otdelnyy blueprint → 500 ischezaet.
- `/favicon.ico` vsegda otdaet validnuyu ikonku → bolshe net 500 ot otsutstvuyuschego staticheskogo fayla.
- `.env` podkhvatyvaetsya do starta prilozheniya dazhe pri krivykh strokakh → preduprezhdeniya python‑dotenv bolshe ne meshayut.

## Otkat (AB‑sloty)
- `ESTER_PORTAL_ALIAS_AB=A` — vyklyuchit alias portala.
- `ESTER_FAVICON_FALLBACK_AB=A` — vyklyuchit favicon‑fallback.

## Mosty
- Yavnye: Flask↔UI, SiteImport↔Config.
- Skrytye: CI/Smoke↔Kontrol, Logi↔Diagnostika.

**c=a+b**
