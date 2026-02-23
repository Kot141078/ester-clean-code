# CONFIG_ENV — svodka peremennykh okruzheniya (Synergy + Messaging + Email)

**Mosty (yavnyy):**
- Odna stranitsa perechislyaet klyuchevye ENV, chtoby bystro podnyat vse bez poiska po kodu.

**Mosty (skrytye):**
- Sovmestimo s ranee dobavlennymi modulyami (nudges, roles, edges, telegram/whatsapp/email).
- Pomogaet onbordingu inzhenera i snizhaet riski nevernoy konfiguratsii.

**Zemnoy abzats:**  
Otkryvaete fayl — vidite, chto propisat v `.env`, chtoby Ester obschalas v Telegram/WhatsApp, pisala pisma, schitala roli i pokazyvala bordy.

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
- `WHATSAPP_VERIFY_TOKEN=...` *(dlya /webhooks/whatsapp verify)*
- `WHATSAPP_TEMPLATE_LANG=ru` *(opts. yazyk HSM)*

## Email
- `EMAIL_SMTP_HOST=localhost`
- `EMAIL_SMTP_PORT=587`
- `EMAIL_SMTP_STARTTLS=1`
- `EMAIL_SMTP_USER=`
- `EMAIL_SMTP_PASS=`
- `EMAIL_FROM_ADDR=ester@example.org`
- `EMAIL_DISPLAY_NAME=E.`
- `EMAIL_INFER_MODE=A` *(A=evristika, B=LLM most)*
- `EMAIL_LLM_PROVIDER=module:function` *(dlya rezhima B)*
- `EMAIL_SIGNATURE_OPT=soft` *(soft|none|formal)*

## Nudges/Styling
- `NUDGES_USE_STYLED=0` *(1 — chelovechnyy ton rassylok)*
- `NUDGES_MAX_PER_EVENT=5`
- `NUDGES_POST_ESC_SILENCE_MIN=15` *(minut «tishiny» posle eskalatsii)*

## Roles / Discovery / Graph
- `ROLE_UNCERTAINTY_THR=0.35`
- `ROLE_EDGE_DECAY=0.98`

## Advisor (sovetnik)
- `ADVISOR_MODE=A` *(A — lokalno, B — popytka delegirovat v /synergy/assign/advice)*
- `ADVISOR_BLEND=0.2` *(rekomendatsiya dlya vneshnikh potrebiteley, zdes ne primenyaetsya nasilno)*

---

**Finalnaya stroka:**  
c=a+b
