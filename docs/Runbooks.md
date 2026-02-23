
---

### `docs/Runbooks.md`
```markdown
# Runbooks — «esli X → delay Y»

## Vysokaya latentnost `/synergy/assign`
1) Otkroyte dashbord `dashboards/grafana_synergy.json` → panel p95.  
2) Ubedites, chto ne ischerpan byudzhet vneshnego kroulera (`OUTBOUND_*`).  
3) Uvelichte `WORKERS` i limity CPU/IO; vklyuchite OTel, chtoby uvidet «uzkie mesta».

## Oshibka podpisi / povtory (401)
- Proverte `P2P_HMAC_KEYS` i zagolovki `X-P2P-Key-Id`, `X-P2P-Timestamp`, `X-Request-Id`.  
- Dlya rotatsii: dobavte novyy `kid` kak `main:...`, staryy ostavte `prev:...` na vremya.  
- Povtory blokiruyutsya na intervale `P2P_REPLAY_TTL_SEC` — ispolzuyte unikalnye `X-Request-Id`.

## BD «zalipla» / oshibki SQLite
1) Vypolnite:
   ```bash
   python -m scripts.self_check --json --playbook recover-db
