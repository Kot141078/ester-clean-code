"""CommsBridge - edinaya tochka vkhoda dlya messendzherov (Telegram, WhatsApp)
Ne menyaet suschestvuyuschie puti/kontrakty Ester. Mozhet zapuskatsya otdelno ili byt smontirovannym v osnovnoy FastAPI.

MOSTY (yavnyy):
- Svyaz s already-existing Ester dialogovym yadrom cherez HTTP-shlyuz (adapters call `local_chat_gateway()`), kotoryy sovmestim s vashim `chat_handler.py` (drop-in).

MOSTY (skrytye, 2+):
- Privyazka k `ambient_proactive.py` cherez internal hook (na urovne interfeysa PersonaEvent) — chtoby sokhranit i usilit proaktivnost.
- Integratsiya so stilevym dvizhkom (style_engine.py) i detectorom persony (persona_detector.py) dlya podbora tona i “maskirovki” pod cheloveka.

ZEMNOY ABZATs:
- Etot modul mozhno podnyat kak otdelnyy servis, poka vy ne dadite finalnyy damp: on uzhe prinimaet webkhuki TG/WA i otvechaet “po-chelovecheski”."""

import os
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .telegram_adapter import TelegramAdapter
from .whatsapp_adapter import WhatsAppAdapter
from .style_engine import StyleEngine
from .persona_detector import PersonaDetector
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

app = FastAPI(title="Ester CommsBridge")
router = APIRouter(prefix="/bridge", tags=["CommsBridge"])

# Safe defaults (we don’t break anything, everything is optional)
ESTER_CHAT_GATEWAY = os.getenv("ESTER_CHAT_GATEWAY", "http://localhost:8099/ester/chat")
MASK_HUMANLIKE = os.getenv("ESTER_MASK_HUMANLIKE", "1") == "1"

style = StyleEngine()
detector = PersonaDetector()
tg = TelegramAdapter(chat_gateway=ESTER_CHAT_GATEWAY, style_engine=style, detector=detector, mask_humanlike=MASK_HUMANLIKE)
wa = WhatsAppAdapter(chat_gateway=ESTER_CHAT_GATEWAY, style_engine=style, detector=detector, mask_humanlike=MASK_HUMANLIKE)

class Health(BaseModel):
    ok: bool = True
    messenger_endpoints: list[str] = ["/bridge/tg/webhook", "/bridge/wa/webhook"]

@router.get("/health", response_model=Health)
async def health():
    return Health()

# Telegram webhook (drop-in, standartnaya forma)
@router.post("/tg/webhook")
async def tg_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Bad JSON: {e}") from e
    result = await tg.handle_webhook(payload)
    return JSONResponse(result)

# WhatsApp webhook (Meta Webhooks)
@router.get("/wa/webhook")
async def wa_verify(mode: str = None, challenge: str = None, token: str = None):
    # Hook verification (Meta compatible)
    verify_token = os.getenv("ESTER_WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and token == verify_token:
        return JSONResponse(content=challenge or "")
    raise HTTPException(403, "Verification failed")

@router.post("/wa/webhook")
async def wa_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Bad JSON: {e}") from e
    result = await wa.handle_webhook(payload)
    return JSONResponse(result)

app.include_router(router)

# A/B slot for safe rollback (default A)
# ESTER_MESSAGING_IMPL=A|B — u adapterov dva steka HTTP-klienta, pereklyuchaetsya env.
# Quick cutback: in case of errors, network B returns to A.
# c=a+b