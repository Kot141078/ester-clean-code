# Ester — bystryy start (bordy, kanaly, sovetnik, pisma)

**Chto eto:** minimalnyy nabor shagov, chtoby zapustit novye vozmozhnosti bez izmeneniya suschestvuyuschikh kontraktov.

## 1) Ustanovka i ENV

Sozdayte `.env` (ili peremennye okruzheniya), podstaviv svoi znacheniya:

```bash
MESSAGING_DB_PATH=./data/messaging.db

# Telegram
TELEGRAM_BOT_TOKEN=...                 # token bota
TELEGRAM_WEBHOOK_SECRET=...            # sekret dlya zagolovka
TELEGRAM_WEBHOOK_URL=https://<host>/webhooks/telegram
TELEGRAM_ALLOWED_CHATS=                 # optsionalno
TELEGRAM_TYPING_DELAY_MS=0

# WhatsApp Cloud
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_TEMPLATE_LANG=ru

# Email
EMAIL_SMTP_HOST=localhost
EMAIL_SMTP_PORT=587
EMAIL_SMTP_STARTTLS=1
EMAIL_SMTP_USER=
EMAIL_SMTP_PASS=
EMAIL_FROM_ADDR=ester@example.org
EMAIL_DISPLAY_NAME=E.
EMAIL_INFER_MODE=A
EMAIL_SIGNATURE_OPT=soft

# Sovetnik
ADVISOR_MODE=A
ADVISOR_BLEND=0.2
ROLE_CLARIFY_THRESHOLD=0.35
ROLE_EDGE_DECAY=0.98
