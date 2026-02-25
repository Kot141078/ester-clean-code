# -*- coding: utf-8 -*-
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

IDEAS_STORE = os.path.join("memory", "ideas.jsonl")

class IdeaEngine:
    """Module for capturing and developing ideas.
    Allows Esther not only to store Ovner’s thoughts, but also to prioritize them."""
    def __init__(self, graph=None):
        self.graph = graph
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(IDEAS_STORE), exist_ok=True)

    def add_idea(self, text: str, author: str, tags: List[str] = None, priority: int = 1) -> str:
        """Add a new idea to the incubator."""
        idea_id = f"idea_{int(time.time())}"
        payload = {
            "id": idea_id,
            "ts": datetime.now().isoformat(),
            "author": author,
            "text": text,
            "tags": tags or [],
            "priority": priority, # 1-nizkiy, 3-kritichnyy
            "status": "incubating", # incubating, active, archived
            "connections": []
        }
        
        with open(IDEAS_STORE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            
        # If the knowledge graph is connected, it creates an idea node
        if self.graph:
            self.graph.add_entity(idea_id, "idea", {"text": text[:50], "priority": priority})
            self.graph.add_relation(author, idea_id, "dreamed_up")
            
        return idea_id

    def list_ideas(self, tag: Optional[str] = None, min_priority: int = 0) -> List[Dict]:
        """Get a list of ideas for review (for example, during Esther's nightly reflections)."""
        if not os.path.exists(IDEAS_STORE): return []
        
        results = []
        with open(IDEAS_STORE, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                if tag and tag not in item.get("tags", []): continue
                if item.get("priority", 0) < min_priority: continue
                results.append(item)
        return results

    def update_idea_status(self, idea_id: str, new_status: str):
        """Transfer the idea to the status “in work” or “archive”."""
        if not os.path.exists(IDEAS_STORE): return
        
        temp_file = IDEAS_STORE + ".tmp"
        with open(IDEAS_STORE, "r", encoding="utf-8") as f, open(temp_file, "w", encoding="utf-8") as out:
            for line in f:
                data = json.loads(line)
                if data["id"] == idea_id:
                    data["status"] = new_status
                    data["updated_at"] = datetime.now().isoformat()
                out.write(json.dumps(data, ensure_ascii=False) + "\n")
        os.replace(temp_file, IDEAS_STORE)

# Example use for Esther
# ideas = IdeaEngine(graph=my_graph)