
# API dokumentatsiya

## Dostup onlayn (esli zapuscheno FastAPI)
- Swagger UI: `GET /docs`
- Redoc: `GET /redoc`
- Skhema: `GET /openapi.json`

## Generatsiya artefakta
```bash
python scripts/docs/generate_openapi.py --out docs/API/openapi.json
