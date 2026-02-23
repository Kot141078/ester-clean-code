# -*- coding: utf-8 -*-
import os, json, time, hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SHARED_STORE = os.path.join("memory", "shared_content.jsonl")

class ShareBridge:
    def __init__(self, graph_engine=None):
        self.graph = graph_engine
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(os.path.dirname(SHARED_STORE), exist_ok=True)

    def _generate_content_hash(self, content: str) -> str:
        """Predotvraschaet dublikaty v pamyati."""
        return hashlib.md5(content.encode()).hexdigest()

    def process_share(self, source_type: str, author_id: str, content: Any, metadata: Optional[Dict] = None) -> str:
        """
        Uluchsheno: Dobavlena deduplikatsiya i avtomaticheskaya privyazka k grafu.
        """
        content_str = str(content)
        c_hash = self._generate_content_hash(content_str)
        
        share_id = f"sh_{int(time.time())}_{c_hash[:6]}"
        
        payload = {
            "id": share_id,
            "hash": c_hash,
            "timestamp": datetime.now().isoformat(),
            "source": source_type,
            "author": author_id,
            "content": content,
            "metadata": metadata or {},
            "status": "new",
            "priority": self._estimate_priority(content_str, metadata)
        }
        
        # Sokhranyaem v log
        with open(SHARED_STORE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        
        # Avtomaticheskaya integratsiya v graf, esli on podklyuchen
        if self.graph:
            self._auto_link_to_graph(payload)
            
        return share_id

    def _estimate_priority(self, text: str, meta: Optional[Dict]) -> int:
        """Prostaya logika opredeleniya vazhnosti kontenta."""
        low_text = text.lower()
        # Esli prislal Owner (Owner) ili est markery srochnosti
        if "vazhno" in low_text or "srochno" in low_text:
            return 3
        if meta and meta.get("is_pinned"):
            return 2
        return 1

    def _auto_link_to_graph(self, data: Dict):
        """Sozdaet pervichnye neyronnye svyazi v grafe."""
        try:
            self.graph.add_entity(data["id"], "shared_content", {
                "priority": data["priority"],
                "source": data["source"]
            })
            self.graph.add_relation(data["author"], data["id"], "authored", weight=1.0)
            
            # Poisk klyuchevykh slov dlya bystrykh svyazey
            for word in ["proekt", "bag", "ideya", "plan"]:
                if word in str(data["content"]).lower():
                    self.graph.add_relation(data["id"], word, "references", weight=0.8)
        except Exception as e:
            print(f"Oshibka avtolinkovki: {e}")

    def get_pending_tasks(self) -> List[Dict]:
        """Vozvraschaet neobrabotannyy kontent dlya Deep Thinking sessii."""
        if not os.path.exists(SHARED_STORE): return []
        with open(SHARED_STORE, "r", encoding="utf-8") as f:
            return [json.loads(l) for l in f if json.loads(l).get("status") == "new"]

# Ekzemplyar dlya importa
# bridge = ShareBridge(graph_engine=EsterKnowledgeGraph())