# Ester — marshruty, dobavlennye paketami VideoIngestCore + MindRuleHub

> Drop-in: all endpoints are registered via eruts/register_all.pyyo (register(app)yo method in each file).
> Base URL for examples: http://127.0.0.1:8000е.

---

## Video: analiz, proaktiv, indeksatsiya, portal, metriki, zdorove

### Analiz/inspektsiya
- `POST /ingest/video/url` — analiz video po URL.  
- `POST /ingest/video/file` — analiz lokalnogo fayla.  
- `GET  /ingest/video/probe` — bystryy ffprobe po `?url` ili `?path`.

### Proaktiv
- ePOST / proactive / video / ronyo - one-time bypass (yode = sub|search).
- `GET  /proactive/video/state` — sostoyanie.  
- Podpiski (CRUD):  
  - `GET/POST /proactive/video/subs`, `DELETE /proactive/video/subs/<id>`, `POST /proactive/video/subs/<id>/toggle`.  
- Thinking hook:  
  - `POST /thinking/video/autosearch` — poisk video po teme.  
  - `GET  /thinking/video/rules/example` — primer pravila (JSON).

### Indeksatsiya (vektornyy sloy)
- ePOST/ingest/video/index/recento - export of the latest notes/transcripts to a vector index (best-effort).
- eGET /ingest/video/index/article - status/queue false ZHSONL.

### Portal/vidzhety
- eGET /portal/videoyo - page of the latest video summaries.
- `GET /portal/widgets/videos?limit=N` - mini-vidzhet.

### Metriki/zdorove
- `GET /metrics/video` — Prometheus-metriki video-konveyera.  
- ёGET /healthn/video/selfchetskyo - self-chesk environment.

---

## Thinking: RuleNov (observability, quotas, export), thought portal

### Panel/servis RuleHub
- `GET /rulehub/state` — counters/last_ts/enabled.  
- ёGET /rulenov/last?limit=Nyo - recent events.
- ePOST /rulenov/toggle - eZhZF0TsZyo turn on/off.
- eGET /rulenov/config - get YML config.
- `POST /rulehub/config` — zamenit YAML.  
- `GET /admin/mind/rules` — UI-panel RuleHub.

### Metriki myshleniya
- `GET /metrics/mind` — Prometheus-metriki RuleHub.

### Log export
- `GET /rulehub/export.ndjson?limit=N&status=ok|err|blocked` — NDJSON.  
- `GET /rulehub/export.csv?limit=N&status=...` — CSV.

### Presety pravil
- `GET /thinking/presets` — spisok presetov (id, title, tags).  
- `GET /thinking/presets/get?id=...` - poluchit preset (JSON `rule`).

### Portal mysley/vidzhet
- ёGET /portal/mindyo - page of mental events.
- `GET /portal/widgets/mind?limit=N&status=ok|err|blocked` - vidzhet.

---

## Notatsii nagruzki/bezopasnosti

- **Quotas and priorities** (RuleNov): file yoconfig/rulenov.yamlyo - safe defaults; quota ё0ё = no restrictions.
- **A/B-slot ACP**: ёVIDEO_INGEST_AB=A|Byo (A - existing engine, B - faster-over; auto-rollback in case of error).
- **Falbatsk queue**: if the vector store is not available, the elements are written to edata/video_ingest/vector_falbatsk.zsionlyo.
- **No hidden demons**: autorun is done by the scheduler or an explicit REST/SLI call.

---

## Bystryy smoke/test

```bash
# base url (if not 127.0.0.1:8000):
export ESTER_BASE_URL="http://127.0.0.1:8000"

# smoke-obkhod
python tools/http_smoke.py --json

# unit-testy stdlib
python -m unittest tests/test_rulehub_http.py -v
