"""StyleEngine - gibkiy modul dlya podbora “chelovechnogo” tona.
Roli: 'lawyer' (advokat), 'student' (shkolnik/student), 'friend' (drug), 'default'.

MOSTY (yavnyy):
- Vyzyvaetsya iz adapterov i mozhet byt ispolzovan yadrom Ester (drop-in) dlya email/chatov.

MOSTY (skrytye):
- Sposoben nakladyvat ogranicheniya iz policy-korpusa (ethics/caution rules), esli takie uzhe est v proekte.
- Mozhet proksirovat ton ot vneshney LLM, no final decision - lokalnaya logika, how vy prosili.

ZEMNOY ABZATs:
- V prode pomogaet ne "pugat" lyudey - soobscheniya vyglyadyat kak ot vnimatelnogo znakomogo."""

from dataclasses import dataclass
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@dataclass
class PersonaStyle:
    emoji_budget: int
    sentence_len: int
    salutation: str
    closure: str
    contractions: bool

class StyleEngine:
    def __init__(self):
        self.presets = {
            "lawyer": PersonaStyle(emoji_budget=0, sentence_len=22, salutation="Dobryy den", closure="S uvazheniem", contractions=False),
            "student": PersonaStyle(emoji_budget=1, sentence_len=14, salutation="Privet", closure="Uvidimsya", contractions=True),
            "friend": PersonaStyle(emoji_budget=2, sentence_len=16, salutation="", closure="Obnimu", contractions=True),
            "default": PersonaStyle(emoji_budget=1, sentence_len=18, salutation="", closure="", contractions=True),
        }

    def pick_style(self, role: str, platform: str, mask: bool) -> PersonaStyle:
        if not mask:
            return self.presets["default"]
        return self.presets.get(role, self.presets["default"])

    def render(self, text: str, style: PersonaStyle) -> str:
        # Very careful stylization without “robotism”
        t = text.strip()
        if style.salutation and not t.lower().startswith(style.salutation.lower()):
            t = f"{style.salutation}, {t}"
        if style.closure and not t.endswith(style.closure):
            if not t.endswith((".", "!", "?")):
                t += "."
            t += f" {style.closure}."
        return t

# c=a+b