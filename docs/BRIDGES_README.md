# CommsBridge dlya Ester

**Chto eto:** izolirovannyy sloy dlya Telegram i WhatsApp, kotoryy:
- Ne menyaet suschestvuyuschie kontrakty (drop-in).
- Umeet «maskirovatsya» pod obychnogo cheloveka.
- Podbiraet stil pisma pod adresata (advokat/shkolnik/drug).

## Bystryy start (standalone)
```bash
pip install fastapi uvicorn httpx pydantic python-dotenv
cp config/messaging.example.env .env
uvicorn bridges.messenger_bridge:app --port 8088
