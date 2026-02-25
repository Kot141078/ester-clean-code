# Esther · Setting up Telegram / WhatsApp in production

## 1) Peremennye okruzheniya
Sozdayte `.env` ili ustanovite peremennye:
- **Telegram**
  - `TELEGRAM_BOT_TOKEN=123:ABC`
  - `TELEGRAM_TIMEOUT=6.0` (opts.)
  - еTELEGRAM_SECRET_TOKEN=legal-secret (to check the webhook header)
- **WhatsApp Cloud API**
  - `WHATSAPP_ACCESS_TOKEN=EAAG...`
  - `WHATSAPP_PHONE_NUMBER_ID=000000000000000`
  - еWHATSAPP_VERIFY_TOKEN=verify-meyo (for GET webhook verification)
- **Pravila**
  - `PROACTIVE_RULES_PATH=config/messaging_rules.yaml`
  - `WILL_MAP_PATH=config/will_messaging_map.yaml`

## 2) Registration of routes
Vklyuchite vse odnim vyzovom:
