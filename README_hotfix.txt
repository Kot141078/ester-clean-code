Ester — Hotfix Package (2025-10-23)

Sostav:
- routes/portal_routes_alias.py      — alias /portal s bezopasnym fallback
- routes/favicon_routes_alias.py     — stabilnyy /favicon.ico
- app_plugins/autoregister_compat_pydantic.py — filtr preduprezhdeniya pydantic v2
- scripts/env_sanitize.py|ps1        — ochistka .env
- scripts/patch_video_ingest.py      — fikc SyntaxWarning (yt-dlp)
- config/.env.example                — primer peremennykh okruzheniya
- tools/smoke_portal.ps1             — smouk‑test

Registratsiya (cherez data/app/extra_routes.json):
  [
    "routes.portal_routes_alias",
    "routes.favicon_routes_alias",
    "app_plugins.autoregister_compat_pydantic"
  ]

AB‑flagi (po umolchaniyu):
  ESTER_PORTAL_AB=A  (vklyuchite B, chtoby zadeystvovat alias /portal)
  ESTER_FAVICON_AB=B (vklyucheno)
  ESTER_PYDANTIC_AB=B (vklyucheno)

Smoke:
  scripts\env_sanitize.ps1
  tools\smoke_portal.ps1

c=a+b
