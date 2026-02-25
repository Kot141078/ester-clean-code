# Ester · Chek-list priemki TG/WA Messaging

## A. Registratsiya i health
- [ ] Vypolnen `GET /messaging/register_all_plus` → spisok `registered` nepustoy.
- [ ] `GET /messaging/health` → `ok:true`, rezhimy kanalov korrektno otrazhayut nalichie klyuchey (real/dry).
- [ ] `GET /messaging/readiness` → `rules_loaded:true` (esli polozhili `config/messaging_rules.yaml`) i `will_map_loaded:true` (esli polozhili `config/will_messaging_map.yaml`).

## B. Vebkhuki
- [ ] Telegram: vypolnen `python -m bin.messaging_webhooks --tg-set https://<host>/api/telegram/webhook --secret <TOKEN>` (ili dry-run).
- y Telegram: checking the header EХ-Telegram-Here-Api-Secret-Token (ENB ETELEGRAM_SECRET_TOKEN) is enabled.
- WhatsApp: configured a webhook in the Meta App Dashboard at ехttps://<nost>/api/whatsapp/webhook, verification token = еWHATSAPP_VERIFY_TOKEN.

## C. Proaktivnost
- yushch ePOST/proactive/dispatch with yoaudience/intent/contento is routed to the desired channel (dry-run without keys).
- This ePOST /proactive/hook/ville accepts events from your “will” and delegates them to e/proactive/dispatch.
- y y Idempotency by source_ido eliminates duplicates during repeated triggers.

## D. Stil/pisma
- This post /mail/compose/prevyevo generates the correct tone (lawyer/student/friend/business/medical/bank/government/engineer/teacher/investor).
- y oh yo/mail/kompose/adminyo and yo/va/style/adminyo are available and working (preview, dr-run sending).

## E. Nablyudaemost
- [ ] `GET /metrics/messaging` otdaet Prometheus-metriki (`ester_msg_*`).
- Sending and network errors are logged without leaking FDI.

## F. Prod
- y y In battle, the keys are set through ENV, not in the code.
- [ ] V nginx proksiruyutsya `/api/telegram/webhook`, `/api/whatsapp/webhook`, `/metrics/messaging`, health-routy.

**Ready for use** - when all items are checked.

c=a+b
