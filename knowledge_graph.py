# -*- coding: utf-8 -*-
"""
Knowledge Graph for Ester: ispolzuet networkx dlya khraneniya svyazey mezhdu suschnostyami, vospominaniyami i emotsiyami.
Rasshiren: dobavil metody dlya dobavleniya uzlov/reber, poiska putey, i integratsiyu s pamyatyu.
- Dobavleno: integratsiya s cards (svyazi pri dobavlenii faktov)
- Dobavleno: primenenie decay ko vsemu grafu
"""

import networkx as nx
from datetime import datetime
import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Konstanty dlya grafa
DECAY_FACTOR = 0.99  # Koeffitsient zatukhaniya vesa svyazi so vremenem

class EsterKnowledgeGraph:
    def __init__(self, storage_path="state/knowledge_graph.gpickle"):
        self.storage_path = storage_path
        self.graph = nx.MultiDiGraph()
        self.load_graph()

    def load_graph(self):
        if os.path.exists(self.storage_path):
            try:
                # V sovremennykh versiyakh networkx luchshe ispolzovat node-link dannye dlya JSON
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except Exception as e:
                print(f"Oshibka zagruzki grafa: {e}")
                self.graph = nx.MultiDiGraph()

    def save_graph(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_entity(self, entity_id: str, entity_type: str, properties: dict = None):
        """Dobavit suschnost (uzel) v graf."""
        if properties is None:
            properties = {}
        properties['type'] = entity_type
        properties['timestamp'] = datetime.now().isoformat()
        properties['weight'] = properties.get('weight', 1.0)
        self.graph.add_node(entity_id, **properties)

    def add_relation(self, source: str, target: str, relation_type: str, weight: float = 1.0):
        """Dobavit svyaz (rebro) mezhdu suschnostyami."""
        self.graph.add_edge(
            source, 
            target, 
            key=relation_type,
            relation=relation_type,
            weight=weight,
            timestamp=datetime.now().isoformat()
        )

    # Uluchsheno: primenenie decay ko vsem uzlam i rebram
    def apply_decay(self):
        now = datetime.now()
        for node, data in self.graph.nodes(data=True):
            ts = data.get("timestamp")
            if ts:
                age_days = (now - datetime.fromisoformat(ts)).days
                data["weight"] = data.get("weight", 1.0) * (DECAY_FACTOR**age_days)
        
        for u, v, data in self.graph.edges(data=True):
            ts = data.get("timestamp")
            if ts:
                age_days = (now - datetime.fromisoformat(ts)).days
                data["weight"] = data.get("weight", 1.0) * (DECAY_FACTOR**age_days)

    # Uluchsheno: Metod dlya udaleniya uzla
    def remove_node(self, node_id: str):
        if node_id in self.graph.nodes:
            self.graph.remove_node(node_id)

    # Uluchsheno: Poisk assotsiatsiy (sosednikh uzlov)
    def get_associations(self, entity_id: str):
        if entity_id not in self.graph.nodes:
            return []
        return list(self.graph.neighbors(entity_id))

    def find_path(self, start_node: str, end_node: str):
        """Nayti kratchayshiy put mezhdu dvumya ponyatiyami (assotsiativnaya tsepochka)."""
        try:
            return nx.shortest_path(self.graph, source=start_node, target=end_node, weight='weight')
        except nx.NetworkXNoPath:
            return None