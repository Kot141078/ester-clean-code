# CommsBridge for Esther

**What is it:** an isolated layer for Telegram and WhatsApp, which:
- Does not change existing contracts (drop-in).
- Knows how to “disguise” as an ordinary person.
- Podbiraet stil pisma pod adresata (advokat/shkolnik/drug).

## Bystryy start (standalone)
```bash
pip install fastapi uvicorn httpx pydantic python-dotenv
cp config/messaging.example.env .env
uvicorn bridges.messenger_bridge:app --port 8088
