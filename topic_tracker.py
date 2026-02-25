# -*- coding: utf-8 -*-
import json
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Put k sostoyaniyu tem
TOPICS_STATE = os.path.join("state", "topics_context.json")

class TopicTracker:
    """Improved context tracker. 
    Keep track of what is being discussed and how long the topic remains relevant."""
    def __init__(self):
        self.current_context: Dict[str, Any] = {
            "active_topics": {},  # topic_name: {weight, last_seen, energy}
            "history": [],
            "last_update": time.time()
        }
        self._load_state()

    def _load_state(self):
        if os.path.exists(TOPICS_STATE):
            try:
                with open(TOPICS_STATE, 'r', encoding='utf-8') as f:
                    self.current_context = json.load(f)
            except Exception:
                pass

    def _save_state(self):
        os.makedirs(os.path.dirname(TOPICS_STATE), exist_ok=True)
        with open(TOPICS_STATE, 'w', encoding='utf-8') as f:
            json.dump(self.current_context, f, ensure_ascii=False, indent=2)

    def update_topics(self, found_topics: List[str], sentiment: float = 0.0):
        """Updates topic weights.
        fund_topics: list of topics found in the message.
        sentiment: emotional coloring (affects the energy of the topic)."""
        now = time.time()
        decay = 0.95 # Theme cooldown factor
        
        # 1. Apply Fade to Old Themes
        for t in list(self.current_context["active_topics"].keys()):
            # The topic loses relevance over time
            time_passed = (now - self.current_context["active_topics"][t]["last_seen"]) / 60
            self.current_context["active_topics"][t]["energy"] *= (decay ** time_passed)
            
            # Deleting completely cold topics
            if self.current_context["active_topics"][t]["energy"] < 0.1:
                del self.current_context["active_topics"][t]

        # 2. Dobavlyaem ili usilivaem novye temy
        for t in found_topics:
            if t in self.current_context["active_topics"]:
                self.current_context["active_topics"][t]["weight"] += 1
                self.current_context["active_topics"][t]["energy"] = min(2.0, self.current_context["active_topics"][t]["energy"] + 0.5)
                self.current_context["active_topics"][t]["last_seen"] = now
            else:
                self.current_context["active_topics"][t] = {
                    "weight": 1,
                    "energy": 1.0 + abs(sentiment),
                    "first_seen": now,
                    "last_seen": now
                }

        self.current_context["last_update"] = now
        self._save_state()

    def get_main_topic(self) -> Optional[str]:
        """Returns the hottest topic at the moment."""
        if not self.current_context["active_topics"]:
            return None
        return max(self.current_context["active_topics"], 
                   key=lambda k: self.current_context["active_topics"][k]["energy"])

    def get_context_summary(self) -> str:
        """Generates a text description of Esther's current state of mind."""
        active = [t for t, data in self.current_context["active_topics"].items() if data["energy"] > 0.5]
        if not active:
            return "Fokus rasseyan."
        return f"Fokus na: {', '.join(active)}."

# Instance for system
tracker = TopicTracker()