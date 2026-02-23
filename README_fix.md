# Goryachiy fiks: /portal 500, /favicon.ico 500, .env parsing

## Chto eto
Nabor drop-in faylov bez pravki suschestvuyuschikh moduley: alias portala, favikon‑fallback i myagkaya zagruzka `.env` cherez `sitecustomize.py`.

## Kak primenit
1. **Raspakovat** v koren proekta (`D:\ester-project`), chtoby fayly legli kak:
   - `sitecustomize.py`
   - `routes\portal_routes_alias.py`
   - `routes\favicon_fallback_routes.py`
   - `tools\dotenv_sanitize.py`
   - `scripts\patch_extra_routes.ps1`
   - `scripts\smoke_portal.ps1`
   - `config\.env.example`
2. **Zaregistrirovat routy** (odin raz):
   ```powershell
   cd D:\ester-project
   .\scripts\patch_extra_routes.ps1
   ```
3. **Perezapustit** prilozhenie.
4. **Smoke‑test**:
   ```powershell
   .\scripts\smoke_portal.ps1 -Port 8080
   ```
5. **Proverit .env** (optsionalno):
   ```powershell
   python tools\dotenv_sanitize.py --env .env
   Get-Content data\.env.sanitize.log -Raw
   ```

## Pochemu eto chinit vashu oshibku
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
