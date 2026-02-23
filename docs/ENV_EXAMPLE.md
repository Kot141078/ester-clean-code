# ENV Example and Usage

This project includes a safe template: `.env.example`.

## What this gives you

- A GitHub-safe baseline config (no real keys).
- One place to fill local secrets without editing source code.
- A predictable startup profile for local run and CI.

## Quick start (PowerShell)

```powershell
Set-Location "D:\Ester Code"
Copy-Item ".env.example" ".env"
```

Then open `.env` and set your local values.

## Minimal required values

For local start without external integrations:

- `ESTER_HOST`
- `ESTER_PORT`
- `JWT_SECRET`

Everything else can stay empty until you enable integrations.

## If you use integrations

- Telegram: fill `TELEGRAM_*`
- WhatsApp: fill `WHATSAPP_*`
- Email: fill `EMAIL_*`
- LLM APIs: fill provider keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.)

## Pre-publish checklist (GitHub-safe)

1. Keep `.env.example` in repo.
2. Do **not** commit `.env`.
3. Do **not** commit `secrets/` or key JSON files.
4. Run secret scan:

```powershell
python -B tools/dump_secret_scan.py --path .
```

## Notes

- Keep personal identity fields empty in public code:
  - `ESTER_OWNER_GIVEN_NAMES`
  - `ESTER_OWNER_ALIASES`
- Fill them only in your local `.env` if needed.
