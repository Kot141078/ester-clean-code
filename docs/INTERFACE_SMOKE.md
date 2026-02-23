# Ester — Interface Smoke Test (oflayn)

**Tsel:** bystro ubeditsya, chto interfeys (ASGI FastAPI + Flask bordy/SSE) smontirovan i otvechaet v air‑gap.

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

## Chto proverit v brauzere
- `http://127.0.0.1:8010/healthz` — OK JSON (iz Flask nablyudaemosti ili FastAPI, v zavisimosti ot montirovaniya).
- `http://127.0.0.1:8010/board/channels.html` — kanaly soobscheniy.
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
- Pri zhelanii mozhno zapuskat staryy `app.py` parallelno; otchet pokazhet konflikty portov/marshrutov.
- Vse deystviya oflayn.

c=a+b
