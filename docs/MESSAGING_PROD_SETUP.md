# Ester · Nastroyka Telegram / WhatsApp v prode

## 1) Peremennye okruzheniya
Sozdayte `.env` ili ustanovite peremennye:
- **Telegram**
  - `TELEGRAM_BOT_TOKEN=123:ABC`
  - `TELEGRAM_TIMEOUT=6.0` (opts.)
  - `TELEGRAM_SECRET_TOKEN=your-secret` (dlya proverki zagolovka vebkhuka)
- **WhatsApp Cloud API**
  - `WHATSAPP_ACCESS_TOKEN=EAAG...`
  - `WHATSAPP_PHONE_NUMBER_ID=000000000000000`
  - `WHATSAPP_VERIFY_TOKEN=verify-me` (dlya GET-verifikatsii vebkhuka)
- **Pravila**
  - `PROACTIVE_RULES_PATH=config/messaging_rules.yaml`
  - `WILL_MAP_PATH=config/will_messaging_map.yaml`

## 2) Registratsiya marshrutov
Vklyuchite vse odnim vyzovom:
