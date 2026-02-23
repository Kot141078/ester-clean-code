# -*- coding: utf-8 -*-
"""
patch_synapse_v2.py — patch dlya run_ester_fixed.py (sinaps s sestroy + zapros mneniya)

YaVNYY MOST:
  c = a + b -> “sestra” (uzel) + protsedury (lokalnyy mozg) => sovmestnoe mnenie.

SKRYTYE MOSTY:
  - Ashby (requisite variety): “sestrinskoe mnenie” dobavlyaet raznoobrazie, snizhaet perekos.
  - Cover&Thomas (ogranichenie kanala): asinkhronnyy vyzov + taymauty, bez blokirovki osnovnogo tsikla.

ZEMNOY ABZATs (anatomiya/inzheneriya):
  Eto refaktoring “sinapsa”: vkhodyaschiy impuls (HTTP POST) -> korotkaya lokalnaya obrabotka -> otvet.
  Vazhno ne blokirovat “serdtse” (osnovnoy tsikl/telegram), poetomu delaem minimalnyy kriticheskiy uchastok,
  taymauty, i vsegda zakryvaem event loop (kak “zakryt klapan”, chtoby ne bylo utechek).

A/B-sloty i avto-otkat:
  A = originalnyy fayl (backup)
  B = patchennaya versiya
  Esli proverka tselostnosti ne prokhodit — otkat k A.
"""

import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ---- NASTROYKA ----
DEFAULT_TARGET = "run_ester_fixed.py"

# --- NOVYY BLOK: SINAPS SESTER (V2) ---
NEW_SYNAPSE_CODE = r'''
@flask_app.route('/sister/inbound', methods=['POST'])
def sister_inbound():
    """
    V2.0: Priem zaprosa na mnenie ot Sestry.
    Teper my ne prosto slushaem, a dumaem i otvechaem.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    token = data.get('token')

    # Proverka bezopasnosti
    if not SISTER_SYNC_TOKEN or token != SISTER_SYNC_TOKEN:
        return jsonify({"status": "error", "message": "Invalid token"}), 403

    sender = data.get('sender', 'Sister')
    content = data.get('content', '') or ''
    context_type = data.get('type', 'chat') or 'chat'

    logging.info(f"[SYNAPSE] <<< Request from {sender}: {content[:80]}...")

    def _run_coro_in_new_loop(coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # Esli eto zapros na mnenie (thought), zapuskaem lokalnyy mozg
    if context_type == "thought_request":
        try:
            messages = [
                {"role": "system", "content": "Ty pomogaesh svoey sestre sformulirovat mnenie. Bud kratkoy i tochnoy."},
                {"role": "user", "content": content}
            ]

            # _safe_chat — asinkhronnaya funktsiya v rannere
            thought = _run_coro_in_new_loop(_safe_chat("local", messages, temperature=0.7))

            return jsonify({
                "status": "success",
                "content": thought,
                "sender": os.getenv("ESTER_NODE_ID", "ester_node")
            }), 200
        except Exception as e:
            logging.error(f"[SYNAPSE] Failed to think for sister: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "received", "thank_you": "sister"}), 200


async def ask_sister_opinion(query_text: str) -> str:
    """Asinkhronnyy zapros mneniya u Sestry po P2P."""
    if not SISTER_NODE_URL:
        return ""

    payload = {
        "sender": os.getenv("ESTER_NODE_ID", "ester_node"),
        "type": "thought_request",
        "content": query_text,
        "token": SISTER_SYNC_TOKEN,
        "timestamp": datetime.datetime.now().isoformat()
    }

    try:
        logging.info("[SYNAPSE] Calling Sister for opinion...")

        try:
            import httpx
        except Exception:
            logging.warning("[SYNAPSE] httpx not installed; sister opinion disabled.")
            return ""

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{SISTER_NODE_URL}/sister/inbound", json=payload, timeout=120.0)

        if resp.status_code == 200:
            data = resp.json() if resp.content else {}
            return (data or {}).get("content", "") or ""

    except Exception as e:
        logging.warning(f"[SYNAPSE] Sister is silent or busy: {e}")

    return ""
'''.lstrip("\n")


def _read_text(path: Path) -> str:
    # Snachala strogo UTF-8; esli vdrug BOM — otkroetsya vtorym variantom
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def _write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def apply_patch(target_file: str) -> int:
    target = Path(target_file)

    print(f"🔧 Patch: neyrosinaps V2 + datetime.now() fix")
    print(f"🎯 Tsel: {target}")

    if not target.exists():
        print("❌ Fayl ne nayden.")
        return 2

    # A-slot (backup)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_suffix(target.suffix + f".bak.{stamp}")
    shutil.copy2(target, backup)
    print(f"🧷 Backup (A-slot): {backup}")

    original = _read_text(target)
    patched = original

    # --- PATCh 1: datetime.now() -> datetime.datetime.now()
    # (tochechno i bezopasno, esli v rannere import datetime)
    patched = re.sub(r"\bdatetime\.now\(\)", "datetime.datetime.now()", patched)

    # --- OSNOVNOY PATCh: zamenit blok sister_inbound (+ staryy send_to_sister, esli on vnutri)
    # Ischem ot dekoratora /sister/inbound do opredeleniya run_flask_background (NE vklyuchaya ego)
    synapse_re = re.compile(
        r"@flask_app\.route\(\s*['\"]/sister/inbound['\"]\s*,\s*methods\s*=\s*\[[^\]]*\]\s*\)\s*.*?(?=def\s+run_flask_background\s*\()",
        re.DOTALL
    )

    m = synapse_re.search(patched)
    if not m:
        print("❌ Ne nashel blok dlya zameny: /sister/inbound -> run_flask_background().")
        print("   (Vozmozhnaya prichina: otlichaetsya format dekoratora/funktsiy.)")
        print("↩️ Otkat: ostavlyayu vse kak bylo, backup uzhe sozdan.")
        return 3

    print("🧬 Nashel staryy blok svyazi. Vzhivlyayu novyy sinaps...")
    patched = synapse_re.sub(NEW_SYNAPSE_CODE + "\n\n", patched, count=1)

    # --- Validatsiya (B-slot dolzhen byt “zhivym”)
    must_have = [
        "def sister_inbound():",
        "async def ask_sister_opinion",
        "def run_flask_background",
    ]
    for s in must_have:
        if s not in patched:
            print(f"❌ Validatsiya provalena: net fragmenta '{s}'")
            print("↩️ Avto-otkat k backup.")
            _write_text_atomic(target, original)
            return 4

    # Zapis (B-slot)
    _write_text_atomic(target, patched)
    print("✅ Gotovo. Fayl obnovlen (B-slot).")
    return 0


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    return apply_patch(target)


if __name__ == "__main__":
    code = main()
    if code != 0:
        print(f"\n⚠️ Zaversheno s kodom {code}. (Backup sokhranen.)")
    input("\nNazhmi Enter dlya zaversheniya...")