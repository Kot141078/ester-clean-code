# -*- coding: utf-8 -*-
import os
import random
import time
import asyncio
import logging
from datetime import datetime
import pytz
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Trying to import helper modules
try:
    from group_intelligence import list_active_groups
except ImportError:
    # Stub if group_intelligence is not yet initialized
    def list_active_groups(seconds=86400): return []

# Movie bank for Friday rituals (expandable)
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

RITUAL_HOUR = int(os.getenv("RITUAL_HOUR", "20"))  # Evening ritual time (20:00)
TZ_STR = os.getenv("TZ", "Europe/Moscow")

class RitualsModule:
    """Esther's social rhythms module.
    Responsible for evening interactives: surveys (Fri/Sat) and retrospectives (Mon-Thu)."""
    def __init__(self, core=None):
        self.core = core
        self.running = False
        self._last_run_date = None
        self.tz = pytz.timezone(TZ_STR)

    def start(self):
        """Start a background time checking loop."""
        if self.running: return
        self.running = True
        # Ideally this should be async.create_task in the main loop
        # But for compatibility, we will leave the tick method, which will hold the kernel
        logging.info("[Rituals] Modul ritmov aktivirovan.")

    async def check_schedule(self):
        """This method should be called periodically (for example, once a minute) from the kernel."""
        now = datetime.now(self.tz)
        
        # We check whether the hour of the ritual has come and whether we have already started it today
        if now.hour == RITUAL_HOUR and self._last_run_date != now.date():
            await self._perform_evening_ritual(now)
            self._last_run_date = now.date()

    async def _perform_evening_ritual(self, now: datetime):
        """Ispolnenie rituala v zavisimosti ot dnya nedeli."""
        dow = now.weekday()  # 0=Pn ... 6=Vs
        groups = list_active_groups(86400) # Active in the last 24 hours
        
        if not groups:
            logging.info("juRitual There are no active groups for ritual.")
            return

        logging.info(f"yuRitual Launch of a ritual for ZZF0Z groups. Day: ZZF1ZZ")

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
        question = "🎬 Kiber-evening. What do you think about it?"

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
                logging.error(f"yRituals Error sending survey to ZZF0Z: ZZF1ZZ")

    async def _ritual_daily_sync(self, chat_ids):
        """Simple text check-in."""
        phrases = [
            "Colleagues, synchronization time. What are your victories today? 🏆",
            "We complete the cycle of the day. What are we moving to the backlog for tomorrow? 📝",
            "System Check: Uroven energii command? 🔋",
        ]
        text = random.choice(phrases)
        
        for chat_id in chat_ids:
            try:
                if self.core and self.core.bot:
                    await self.core.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logging.error(f"yRituals Error sync in ZZF0Z: ZZF1ZZ")

    def smoketest(self):
        """Diagnostika modulya."""
        try:
            # Checking the list of films
            assert len(FILM_BANK) > 0
            # Checking the timezone
            datetime.now(self.tz)
            return f"OK (Timezone: {TZ_STR}, Movies: {len(FILM_BANK)})"
        except Exception as e:
            return f"FAILED: {e}"

# Global instance for old imports (if needed)
# rituals = RitualsModule()