"""PersonaDetector - legkaya evristika dlya opredeleniya tipa sobesednika bez “tupykh oprosov”.
Mozhno zamenit/usilit na ML, ne lomaya kontrakt.

MOSTY (yavnyy):
- Napryamuyu ispolzuetsya adapterami i mozhet byt vyzvan yadrom (drop-in).

MOSTY (skrytye):
- Skreschivaetsya s profilyami iz cards_memory/data (esli est v proekte), chtoby uchityvat izvestnye kontakty.
- Mozhet uchityvat politiku “caution_rules” pri somneniyakh — podbiraet bezopasnyy neytralnyy stil.

ZEMNOY ABZATs:
- Rabotaet iz korobki i uzhe daet zametno menshe “mashinnosti” v soobscheniyakh."""

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class PersonaDetector:
    def infer_role(self, text: str, meta: Dict[str, Any] | None = None) -> str:
        t = (text or "").lower()
        # Prostaya semantika
        if any(x in t for x in ["st. ", "chast ", "gk", "ugolov", "isk", "sud", "dogovor", "pretenzi"]):
            return "lawyer"
        if any(x in t for x in ["dz", "domashka", "kontrolnaya", "shkol", "univer", "sessiya"]):
            return "student"
        if any(x in t for x in ["bro", "druzhische", "privet", "go ", "pognali"]):
            return "friend"

        # Meta hints: from name/user
        meta = meta or {}
        frm = meta.get("from")
        if isinstance(frm, dict):
            uname = (frm.get("username") or frm.get("first_name") or frm.get("last_name") or "").lower()
            if "adv" in uname or "law" in uname:
                return "lawyer"

        return "default"

# c=a+b