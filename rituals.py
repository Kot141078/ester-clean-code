# -*- coding: utf-8 -*-
import os
import random
import time
import asyncio
import logging
from datetime import datetime
import pytz
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Popytka importa vspomogatelnykh moduley
try:
    from group_intelligence import list_active_groups
except ImportError:
    # Zaglushka, esli group_intelligence esche ne initsializirovan
    def list_active_groups(seconds=86400): return []

# Bank filmov dlya pyatnichnykh ritualov (rasshiryaemyy)
FILM_BANK = [
    ("The Social Network", "Drama/Bio"),
    ("Ex Machina", "Sci-Fi/AI"),
    ("Her", "Romance/AI"),
    ("Source Code", "Sci-Fi/Thriller"),
    ("Limitless", "Sci-Fi/Thriller"),
    ("Upgrade", "Cyberpunk"),
    ("Hackers", "Classic"),
    ("Mr. Robot (Ep. 1)", "Series"),
    ("Silicon Valley (Ep. 1)", "Comedy"),
    ("Pirates of Silicon Valley", "Bio"),
    ("Tron: Legacy", "Sci-Fi"),
    ("WarGames", "Classic"),
]

RITUAL_HOUR = int(os.getenv("RITUAL_HOUR", "20"))  # Vremya vechernego rituala (20:00)
TZ_STR = os.getenv("TZ", "Europe/Moscow")

class RitualsModule:
    """
    Modul sotsialnykh ritmov Ester.
    Otvechaet za vechernie interaktivy: oprosy (Pt/Sb) i retrospektivy (Pn-Cht).
    """
    def __init__(self, core=None):
        self.core = core
        self.running = False
        self._last_run_date = None
        self.tz = pytz.timezone(TZ_STR)

    def start(self):
        """Zapusk fonovogo tsikla proverki vremeni."""
        if self.running: return
        self.running = True
        # V ideale eto dolzhno byt asyncio.create_task v osnovnom tsikle
        # No dlya sovmestimosti ostavim metod tick, kotoryy budet dergat yadro
        logging.info("[Rituals] Modul ritmov aktivirovan.")

    async def check_schedule(self):
        """Etot metod dolzhen vyzyvatsya periodicheski (naprimer, raz v minutu) iz yadra."""
        now = datetime.now(self.tz)
        
        # Proveryaem, nastupil li chas rituala i ne zapuskali li my ego uzhe segodnya
        if now.hour == RITUAL_HOUR and self._last_run_date != now.date():
            await self._perform_evening_ritual(now)
            self._last_run_date = now.date()

    async def _perform_evening_ritual(self, now: datetime):
        """Ispolnenie rituala v zavisimosti ot dnya nedeli."""
        dow = now.weekday()  # 0=Pn ... 6=Vs
        groups = list_active_groups(86400) # Aktivnye za poslednie 24 chasa
        
        if not groups:
            logging.info("[Rituals] Net aktivnykh grupp dlya rituala.")
            return

        logging.info(f"[Rituals] Zapusk rituala dlya {len(groups)} grupp. Den: {dow}")

        # Pyatnitsa (4) ili Subbota (5) — Vybor filma
        if dow in (4, 5):
            await self._ritual_movie_night(groups)
        else:
            # Budni — Chek-in / Plany
            await self._ritual_daily_sync(groups)

    async def _ritual_movie_night(self, chat_ids):
        """Sozdaet opros s filmami."""
        options_data = random.sample(FILM_BANK, k=min(4, len(FILM_BANK)))
        options_text = [f"{name} ({genre})" for name, genre in options_data]
        question = "🎬 Kiber-vecher. Chto posmotrim dlya vdokhnoveniya?"

        for chat_id in chat_ids:
            try:
                if self.core and self.core.bot:
                    await self.core.bot.send_poll(
                        chat_id=chat_id,
                        question=question,
                        options=options_text,
                        is_anonymous=False,
                        allows_multiple_answers=False
                    )
                else:
                    logging.warning(f"[Rituals] Bot instance not found for chat {chat_id}")
            except Exception as e:
                logging.error(f"[Rituals] Oshibka otpravki oprosa v {chat_id}: {e}")

    async def _ritual_daily_sync(self, chat_ids):
        """Prostoy tekstovyy chek-in."""
        phrases = [
            "Kollegi, vremya sinkhronizatsii. Kakie pobedy za segodnya? 🏆",
            "Zavershaem tsikl dnya. Chto perenosim v beklog na zavtra? 📝",
            "System Check: Uroven energii komandy? 🔋",
        ]
        text = random.choice(phrases)
        
        for chat_id in chat_ids:
            try:
                if self.core and self.core.bot:
                    await self.core.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logging.error(f"[Rituals] Oshibka sync v {chat_id}: {e}")

    def smoketest(self):
        """Diagnostika modulya."""
        try:
            # Proveryaem spisok filmov
            assert len(FILM_BANK) > 0
            # Proveryaem taymzonu
            datetime.now(self.tz)
            return f"OK (Timezone: {TZ_STR}, Movies: {len(FILM_BANK)})"
        except Exception as e:
            return f"FAILED: {e}"

# Globalnyy instans dlya starykh importov (esli nuzhno)
# rituals = RitualsModule()