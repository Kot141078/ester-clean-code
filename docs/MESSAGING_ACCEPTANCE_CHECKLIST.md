# Ester · Chek-list priemki TG/WA Messaging

## A. Registratsiya i health
- [ ] Vypolnen `GET /messaging/register_all_plus` → spisok `registered` nepustoy.
- [ ] `GET /messaging/health` → `ok:true`, rezhimy kanalov korrektno otrazhayut nalichie klyuchey (real/dry).
- [ ] `GET /messaging/readiness` → `rules_loaded:true` (esli polozhili `config/messaging_rules.yaml`) i `will_map_loaded:true` (esli polozhili `config/will_messaging_map.yaml`).

## B. Vebkhuki
- [ ] Telegram: vypolnen `python -m bin.messaging_webhooks --tg-set https://<host>/api/telegram/webhook --secret <TOKEN>` (ili dry-run).
- [ ] Telegram: vklyuchena proverka zagolovka `X-Telegram-Bot-Api-Secret-Token` (ENV `TELEGRAM_SECRET_TOKEN`).
- [ ] WhatsApp: nastroen webhook v Meta App Dashboard na `https://<host>/api/whatsapp/webhook`, verify token = `WHATSAPP_VERIFY_TOKEN`.

## C. Proaktivnost
- [ ] `POST /proactive/dispatch` c `audience/intent/content` marshrutiziruetsya v nuzhnyy kanal (dry-run bez klyuchey).
- [ ] `POST /proactive/hook/will` prinimaet sobytiya ot vashey «voli» i delegiruet ikh v `/proactive/dispatch`.
- [ ] Idempotentnost po `source_id` isklyuchaet dubli pri povtornykh triggerakh.

## D. Stil/pisma
- [ ] `POST /mail/compose/preview` generiruet korrektnyy ton (advokat/shkolnik/drug/biznes/medik/bank/gos/inzhener/uchitel/investor).
- [ ] UI `/mail/compose/admin` i `/wa/style/admin` dostupny i rabotayut (predprosmotr, dry-run otpravka).

## E. Nablyudaemost
- [ ] `GET /metrics/messaging` otdaet Prometheus-metriki (`ester_msg_*`).
- [ ] Logiruyutsya oshibki otpravki i setevye sboi bez utechki PII.

## F. Prod
- [ ] V boyu klyuchi vystavleny cherez ENV, ne v kode.
- [ ] V nginx proksiruyutsya `/api/telegram/webhook`, `/api/whatsapp/webhook`, `/metrics/messaging`, health-routy.

**Gotovo k ekspluatatsii** — kogda vse punkty otmecheny.

c=a+b
