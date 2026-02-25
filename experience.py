# -*- coding: utf-8 -*-
"""Experience for Ester: khranit sobytiya, uroki, evolyutsiyu kharaktera.
Rasshiren: dobavil metody dlya dobavleniya opyta, poiska po tegam, integratsiyu s emotsiyami."""
import json
import os
from datetime import datetime
from typing import Any, Dict, List

# Import the config and create an instance to access the paths
from config import EsterConfig
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
cfg = EsterConfig()

# Opredelyaem put k faylu opyta na osnove struktury iz config.py
# Esli v PATHS net 'memory', ispolzuem koren proekta
PERSIST_DIR = cfg.PATHS.get("memory", cfg.BASE_DIR)

class Experience:
    def __init__(self, path: str = os.path.join(PERSIST_DIR, "ester_experience.json")):
        self.path = path
        # Garantiruem nalichie direktorii
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.events: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading experience: ZZF0Z")
                return []
        return []

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving experience: ZZF0Z")

    def add_event(self, event: str, tags: List[str], emotions: Dict[str, float], lesson: str = ""):
        """Adds an event with tags, emotions, lesson."""
        self.events.append(
            {
                "event": event,
                "tags": tags,
                "emotions": emotions,
                "lesson": lesson,
                "date": datetime.now().isoformat(),  # strogiy ISO8601
            }
        )
        self._save()

    def search_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Search for events by tag."""
        return [e for e in self.events if tag in e["tags"]]

    def get_lessons(self) -> List[str]:
        """Returns all lessons for evolution."""
        return [e["lesson"] for e in self.events if e.get("lesson")]