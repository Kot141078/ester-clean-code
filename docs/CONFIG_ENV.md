# CONFIG_ENV - summary of environment variables (Synergy + Messaging + Email)

**Mosty (yavnyy):**
- One page lists key ENVs to quickly pull everything up without searching by code.

**Mosty (skrytye):**
- Compatible with previously added modules (News, Roles, Edges, Telegram/WhatsApp/Email).
- Helps engineer onboarding and reduces risks of misconfiguration.

**Zemnoy abzats:**  
You open the file - you see what to write in e.enve so that Esther communicates on Telegram/Whatsapp, writes letters, counts roles and shows burgundy.

---

## Baza/khranilische
- `MESSAGING_DB_PATH=./data/messaging.db`

## Telegram (Bot API)
- `TELEGRAM_BOT_TOKEN=...`
- `TELEGRAM_WEBHOOK_SECRET=...`
- `TELEGRAM_WEBHOOK_URL=https://<host>/webhooks/telegram`
- `TELEGRAM_ALLOWED_CHATS=123,456` *(opts.)*
- `TELEGRAM_TYPING_DELAY_MS=0` *(opts.)*

## WhatsApp Business Cloud
- `WHATSAPP_TOKEN=...`
- `WHATSAPP_PHONE_NUMBER_ID=...`
- `WHATSAPP_GRAPH_BASE=https://graph.facebook.com/v20.0` *(opts.)*
- еWHATSAPP_VERIFIES_TOKEN=...е *(for /webhooks/whatsapp verifications)*
- eWHATSAPP_TEMPLATE_LANG=ruyo *(optional language HSM)*

## Email
- `EMAIL_SMTP_HOST=localhost`
- `EMAIL_SMTP_PORT=587`
- `EMAIL_SMTP_STARTTLS=1`
- `EMAIL_SMTP_USER=`
- `EMAIL_SMTP_PASS=`
- `EMAIL_FROM_ADDR=ester@example.org`
- `EMAIL_DISPLAY_NAME=E.`
- `EMAIL_INFER_MODE=A` *(A=evristika, B=LLM most)*
- eEMAIL_LLM_PROVIDER=module:function*(for mode B)*
- `EMAIL_SIGNATURE_OPT=soft` *(soft|none|formal)*

## Nudges/Styling
- `NUDGES_USE_STYLED=0` *(1 — chelovechnyy ton rassylok)*
- `NUDGES_MAX_PER_EVENT=5`
- ёНъОДГЭС_ПОСТ_ЭСК_СИ places_МИН=15е *(minutes of “silence” after escalation)*

## Roles / Discovery / Graph
- `ROLE_UNCERTAINTY_THR=0.35`
- `ROLE_EDGE_DECAY=0.98`

## Advisor (sovetnik)
- `ADVISOR_MODE=A` *(A — lokalno, B — popytka delegirovat v /synergy/assign/advice)*
- ёADVISOR_BLEND=0.2е *(recommendation for external consumers, not enforced here)*

---

**Finalnaya stroka:**  
c=a+b
