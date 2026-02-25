# Ester — Interface Smoke Test (oflayn)

**Goal:** quickly make sure that the interface (ASGI FastAPI + Flask boards/S) is mounted and responds to air gap.

## Bystryy start
```bash
# 1) Aktiviruy venv s zavisimostyami proekta
# 2) (opts.) vystav okruzhenie
set HOST=127.0.0.1
set PORT=8010
set ESTER_AB_INTERFACE=A
# 3) Zapusti
python scripts/run_uvicorn.py
```

## What to check in the browser
- yonttp://127.0.0.1:8010/helpnzyo - OK ZHSION (from Flask observability or FastAPI, depending on the mount).
- http://127.0.0.1:8010/board/hannels.html - message channels.
- `http://127.0.0.1:8010/board/roles.html` — roli.
- `http://127.0.0.1:8010/admin/env` — panel runtime/env.

## Avtoproverka (CLI)
```bash
python tools/verify_routes.py md
# ili JSON:
python tools/verify_routes.py > routes_report.json
```

## Primechaniya
- Kontrakty HTTP/JSON **ne menyalis**.
- If desired, you can run the old yoap.pyyo in parallel; the report will show port/route conflicts.
- All actions are offline.

c=a+b
