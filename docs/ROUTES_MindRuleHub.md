# Ester — marshruty, dobavlennye paketami VideoIngestCore + MindRuleHub

> Drop-in: vse endpointy registriruyutsya cherez `routes/register_all.py` (metod `register(app)` v kazhdom fayle).  
> Bazovyy URL dlya primerov: `http://127.0.0.1:8000`.

---

## Video: analiz, proaktiv, indeksatsiya, portal, metriki, zdorove

### Analiz/inspektsiya
- `POST /ingest/video/url` — analiz video po URL.  
- `POST /ingest/video/file` — analiz lokalnogo fayla.  
- `GET  /ingest/video/probe` — bystryy ffprobe po `?url` ili `?path`.

### Proaktiv
- `POST /proactive/video/run` — razovyy obkhod (`mode=subs|search`).  
- `GET  /proactive/video/state` — sostoyanie.  
- Podpiski (CRUD):  
  - `GET/POST /proactive/video/subs`, `DELETE /proactive/video/subs/<id>`, `POST /proactive/video/subs/<id>/toggle`.  
- Thinking hook:  
  - `POST /thinking/video/autosearch` — poisk video po teme.  
  - `GET  /thinking/video/rules/example` — primer pravila (JSON).

### Indeksatsiya (vektornyy sloy)
- `POST /ingest/video/index/recent` — eksport poslednikh konspektov/transkriptov v vektornyy indeks (best-effort).  
- `GET  /ingest/video/index/state` — sostoyanie/ochered fallback JSONL.

### Portal/vidzhety
- `GET /portal/video` — stranitsa poslednikh video-konspektov.  
- `GET /portal/widgets/videos?limit=N` — mini-vidzhet.

### Metriki/zdorove
- `GET /metrics/video` — Prometheus-metriki video-konveyera.  
- `GET /health/video/selfcheck` — self-check okruzheniya.

---

## Myshlenie: RuleHub (nablyudaemost, kvoty, eksport), portal mysley

### Panel/servis RuleHub
- `GET /rulehub/state` — counters/last_ts/enabled.  
- `GET /rulehub/last?limit=N` — poslednie sobytiya.  
- `POST /rulehub/toggle` — `{"enabled":1|0}` vklyuchit/vyklyuchit.  
- `GET /rulehub/config` — poluchit YAML-konfig.  
- `POST /rulehub/config` — zamenit YAML.  
- `GET /admin/mind/rules` — UI-panel RuleHub.

### Metriki myshleniya
- `GET /metrics/mind` — Prometheus-metriki RuleHub.

### Eksport zhurnala
- `GET /rulehub/export.ndjson?limit=N&status=ok|err|blocked` — NDJSON.  
- `GET /rulehub/export.csv?limit=N&status=...` — CSV.

### Presety pravil
- `GET /thinking/presets` — spisok presetov (id, title, tags).  
- `GET /thinking/presets/get?id=...` — poluchit preset (JSON `rule`).

### Portal mysley/vidzhet
- `GET /portal/mind` — stranitsa myslitelnykh sobytiy.  
- `GET /portal/widgets/mind?limit=N&status=ok|err|blocked` — vidzhet.

---

## Notatsii nagruzki/bezopasnosti

- **Kvoty i prioritety** (RuleHub): fayl `config/rulehub.yaml` — bezopasnye defolty; kvota `0` = bez ogranicheniy.  
- **A/B-slot ASR**: `VIDEO_INGEST_AB=A|B` (A — suschestvuyuschiy dvizhok, B — faster-whisper; avto-otkat pri oshibke).  
- **Fallback ocheredi**: esli vektornyy stor nedostupen, elementy pishutsya v `data/video_ingest/vector_fallback.jsonl`.  
- **Nikakikh skrytykh demonov**: avtozapusk delaetsya planirovschikom ili yavnym REST/CLI-vyzovom.

---

## Bystryy smoke/test

```bash
# bazovyy URL (esli ne 127.0.0.1:8000):
export ESTER_BASE_URL="http://127.0.0.1:8000"

# smoke-obkhod
python tools/http_smoke.py --json

# unit-testy stdlib
python -m unittest tests/test_rulehub_http.py -v
