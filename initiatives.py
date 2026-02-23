# -*- coding: utf-8 -*-
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

INITIATIVES_STORE = os.path.join("memory", "initiatives.jsonl")

_EMOTION_CATALOG = [
    {"tag": "stability", "title": "Razgruzit trevozhnye zadachi", "min_anxiety": 0.6, "min_interest": 0.0},
    {"tag": "focus", "title": "Zakryt odin vazhnyy khvost", "min_anxiety": 0.3, "min_interest": 0.3},
    {"tag": "growth", "title": "Zaplanirovat initsiativu na nedelyu", "min_anxiety": 0.0, "min_interest": 0.6},
    {"tag": "maintenance", "title": "Podderzhka i chistka bekloga", "min_anxiety": 0.0, "min_interest": 0.0},
]

class InitiativeEngine:
    """
    Modul upravleniya dolgosrochnymi initsiativami.
    Pozvolyaet Ester otslezhivat progress po krupnym proektam Owner.
    """
    def __init__(self, core=None):
        self.core = core
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(INITIATIVES_STORE), exist_ok=True)

    def add_initiative(self, title: str, description: str, priority: int = 2) -> str:
        """Registratsiya novoy krupnoy zadachi."""
        init_id = f"init_{int(time.time())}"
        payload = {
            "id": init_id,
            "ts": datetime.now().isoformat(),
            "title": title,
            "description": description,
            "priority": priority, # 1-3
            "status": "active",   # active, paused, completed
            "progress": 0,        # 0-100%
            "resource_cost": "high" if priority > 2 else "medium" 
        }
        
        with open(INITIATIVES_STORE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            
        return init_id

    def update_progress(self, init_id: str, progress: int, comment: str = ""):
        """Obnovlenie progressa po initsiative."""
        if not os.path.exists(INITIATIVES_STORE): return
        
        temp_file = INITIATIVES_STORE + ".tmp"
        with open(INITIATIVES_STORE, "r", encoding="utf-8") as f, \
             open(temp_file, "w", encoding="utf-8") as out:
            for line in f:
                data = json.loads(line)
                if data["id"] == init_id:
                    data["progress"] = min(100, progress)
                    data["last_update"] = datetime.now().isoformat()
                    if comment: data["last_comment"] = comment
                out.write(json.dumps(data, ensure_ascii=False) + "\n")
        os.replace(temp_file, INITIATIVES_STORE)

    def get_active_summary(self) -> str:
        """Svodka dlya Ester: chem my seychas zanyaty?"""
        if not os.path.exists(INITIATIVES_STORE): return "Aktivnykh initsiativ net."
        
        active = []
        with open(INITIATIVES_STORE, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["status"] == "active":
                    active.append(f"«{d['title']}» ({d['progress']}%)")
        
        return "Rabotaem nad: " + ", ".join(active) if active else "Vse zadachi zaversheny."


def choose_by_emotions(emotions: Dict[str, float] | None) -> List[Dict[str, str]]:
    """
    Pick lightweight initiatives by emotion vector.
    Returns items with at least `tag` and `title`.
    """
    emo = dict(emotions or {})
    anxiety = float(emo.get("anxiety", 0.0) or 0.0)
    interest = float(emo.get("interest", 0.0) or 0.0)
    scored: List[tuple[float, Dict[str, str]]] = []
    for item in _EMOTION_CATALOG:
        base = 1.0
        if anxiety >= float(item["min_anxiety"]):
            base += 1.0
        if interest >= float(item["min_interest"]):
            base += 1.0
        # anxiety-leaning items get a bonus when stress is high
        if item["tag"] == "stability":
            base += anxiety
        # growth items get bonus when curiosity is high
        if item["tag"] == "growth":
            base += interest
        scored.append((base, {"tag": str(item["tag"]), "title": str(item["title"])}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:3]]

def smoketest():
    """Smok-test dlya health_check.py"""
    try:
        engine = InitiativeEngine()
        return "OK (Engine Ready)"
    except Exception as e:
        return f"Error: {e}"
