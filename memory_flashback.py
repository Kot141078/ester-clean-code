# -*- coding: utf-8 -*-
# memory_flashback.py (fixed)

from __future__ import annotations

"""memory_flashback.py - flashback poverkh VectorStore + KGStore, s optsionalnoy klasterizatsiey.

Error from loga:
  attempted relative import with no known parent package

Prichina:
  V iskhodnike stoyat otnositelnye importy:
      from .kg_store import KGStore
      from .vector_store import VectorStore
  Eto korrektno, tolko esli modul importiruetsya kak chast paketa.
  Esli zhe loader/entrypoint gruzit fayl kak “just skript” (python memory_flashback.py or SourceFileLoader),
  __package__ empty → otnositelnye importy padayut.

What was done:
  - “Ustoychivye importy”: snachala try otnositelnye, zatem lokalnye, zatem modules.memory.*.
  - Myagkaya degradatsiya: esli sklearn net - flashback rabotaet, just bez clustering.
  - Uluchshena klasterizatsiya: random_state, n_init, zaschita ot malogo chisla tochek/pustykh embeddings.
  - Puti khraneniya normalizovany cherez PERSIST_DIR (something ne zaviset ot cwd).
  - Added atomarnaya zapis clusters.json (cherez .tmp + replace).

Mosty (demand):
  - Yavnyy most: VectorStore(query) → FlashbackClusterer(flashback) → KGStore(edges) = “svyazat pamyat s kontekstom”.
  - Skrytye mosty:
      (1) Infoteoriya ↔ praktika: klaster = szhatie/kvantizatsiya mnozhestva vospominaniy (umenshaem entropiyu opisaniya).
      (2) Kibernetika ↔ kod: rezhim degradatsii (net sklearn → tolko poisk) predotvraschaet otkaz kontura “vspominaniya”.

ZEMNOY ABZATs: v kontse fayla."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger(__name__)

# For clustering (optional)
try:
    from sklearn.cluster import KMeans  # type: ignore
except Exception:
    KMeans = None  # type: ignore


def _persist_dir() -> str:
    return (os.getenv("PERSIST_DIR") or "data").strip() or "data"


def _safe_mkdir(p: str) -> None:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass


def _resolve_stores() -> Tuple[Any, Any]:
    """Ustoychivo importiruet KGStore i VectorStore.

    Poryadok:
      1) otnositelnye importy (kak chast paketa)
      2) lokalnye (v odnoy papke)
      3) modules.memory.* (kak v ostalnoy arkhitekture Ester)"""
    KG = VS = None

    # 1) relative
    try:
        from .kg_store import KGStore as KG  # type: ignore
        from .vector_store import VectorStore as VS  # type: ignore
        return KG, VS
    except Exception:
        pass

    # 2) local
    try:
        from kg_store import KGStore as KG  # type: ignore
        from vector_store import VectorStore as VS  # type: ignore
        return KG, VS
    except Exception:
        pass

    # 3) modules.memory.*
    try:
        from modules.memory.kg_store import KGStore as KG  # type: ignore
        from modules.memory.vector_store import VectorStore as VS  # type: ignore
        return KG, VS
    except Exception as e:
        raise ImportError("Cannot import KGStore/VectorStore (relative/local/modules.memory)")



KGStore, VectorStore = _resolve_stores()


def _as_float_list(x: Any) -> Optional[List[float]]:
    """Pytaemsya privesti embedding k list[float]."""
    if x is None:
        return None
    if isinstance(x, list):
        try:
            return [float(v) for v in x]
        except Exception:
            return None
    if isinstance(x, tuple):
        try:
            return [float(v) for v in x]
        except Exception:
            return None
    # numpy-like
    try:
        return [float(v) for v in list(x)]  # type: ignore
    except Exception:
        return None


@dataclass
class FlashbackConfig:
    vectors_subdir: str = "flashback_vectors"
    clusters_file: str = "clusters.json"
    default_top_k: int = 3
    default_num_clusters: int = 5
    random_state: int = 42
    n_init: int = 10  # safe for sklearn<1.4


class FlashbackClusterer:
    def __init__(
        self,
        vector_store: Optional[Any] = None,
        kg_store: Optional[Any] = None,
        *,
        config: Optional[FlashbackConfig] = None,
    ):
        self.config = config or FlashbackConfig()

        base = _persist_dir()
        vectors_path = os.path.join(base, self.config.vectors_subdir)
        _safe_mkdir(vectors_path)

        self.vector_store = vector_store or VectorStore(vectors_path)
        self.kg_store = kg_store or KGStore()

        self.clusters: Dict[str, List[str]] = {}

    def cluster_memories(self, num_clusters: Optional[int] = None) -> List[List[str]]:
        """Groups memories into clusters and links them into CG.

        Returns a list of clusters: yuuid,id,...sch, ...sch"""
        if KMeans is None:
            logger.warning("sklearn not installed; clustering skipped")
            return []

        n_clusters = int(num_clusters or self.config.default_num_clusters)
        if n_clusters <= 0:
            return []

        # Poluchaem vse vektora vospominaniy
        all_memories = self.vector_store.get_all()
        if not all_memories:
            return []

        embeddings: List[List[float]] = []
        ids: List[str] = []

        for mem in all_memories:
            emb = _as_float_list(mem.get("embedding"))
            mid = mem.get("id")
            if not emb or not mid:
                continue
            embeddings.append(emb)
            ids.append(str(mid))

        if not embeddings:
            return []

        actual_clusters = min(n_clusters, len(embeddings))
        if actual_clusters <= 1:
            # 0/1 cluster - nothing to learn; everything in one bag
            one = [ids]
            self.clusters = {"cluster_0": ids}
            self._link_clusters_to_kg()
            return one

        try:
            kmeans = KMeans(
                n_clusters=actual_clusters,
                random_state=self.config.random_state,
                n_init=self.config.n_init,
            )
            labels = kmeans.fit_predict(embeddings)
        except Exception as e:
            logger.error("KMeans failed: %s", e)
            return []

        clusters: List[List[str]] = [[] for _ in range(actual_clusters)]
        for idx, label in enumerate(labels):
            try:
                clusters[int(label)].append(ids[idx])
            except Exception:
                clusters[0].append(ids[idx])

        self.clusters = {f"cluster_{i}": cluster for i, cluster in enumerate(clusters)}

        self._link_clusters_to_kg()
        return list(self.clusters.values())

    def _link_clusters_to_kg(self) -> None:
        """Connects clusters in a CG as nodes/edges. Best-effort."""
        try:
            for cluster_id, mem_ids in self.clusters.items():
                try:
                    self.kg_store.add_node(cluster_id, "cluster", {"mem_count": len(mem_ids)})
                except Exception:
                    pass
                for mem_id in mem_ids:
                    try:
                        self.kg_store.add_edge(mem_id, "belongs_to", cluster_id, weight=1.0)
                    except Exception:
                        pass
        except Exception:
            logger.debug("KG link skipped", exc_info=True)

    def flashback(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for memories with cluster_id enrichment (if any)."""
        k = int(top_k or self.config.default_top_k)
        if k <= 0:
            k = 1

        results = self.vector_store.query(query, k) or []
        for res in results:
            try:
                cid = self._find_cluster(str(res.get("id")))
                if cid:
                    res["cluster"] = cid
            except Exception:
                continue
        return results

    def _find_cluster(self, mem_id: str) -> Optional[str]:
        """Finds the ID of the cluster to which the memory belongs."""
        try:
            neighbors = self.kg_store.get_neighbors(mem_id, "belongs_to")
            if neighbors:
                return neighbors[0][0]
        except Exception:
            pass
        return None

    def save_clusters(self, path: Optional[str] = None) -> None:
        """Sokhranyaet self.clusters v JSON (atomarno)."""
        base = _persist_dir()
        p = path or os.path.join(base, self.config.clusters_file)
        tmp = p + ".tmp"
        try:
            _safe_mkdir(str(Path(p).parent))
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.clusters, f, ensure_ascii=False, indent=2)
            Path(tmp).replace(p)
        except Exception as e:
            logger.error("Failed to save clusters: %s", e)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    def load_clusters(self, path: Optional[str] = None) -> None:
        base = _persist_dir()
        p = path or os.path.join(base, self.config.clusters_file)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clusters = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            self.clusters = {}
        except Exception as e:
            logger.error("Failed to load clusters: %s", e)
            self.clusters = {}


__all__ = ["FlashbackClusterer", "FlashbackConfig"]


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Flashback - eto kak “assotsiativnaya pamyat” v mozge: vy vspominaete ne po adresu, a po nameku.
Klastery - eto kak gruppirovka neyronnykh ensemble: ne tochnaya karta, a ekonomiya energii pri poiske.
Inzhenerno eto pokhozhe na sklad:
- vektornyy poisk - bystryy poisk po “pokhozhesti korobok”,
- klaster - eto “zona sklada”, kuda korobki svalivayut po tipu,
- KG‑svyazi — eto yarlyki “lezhit v zone X”.
Esli lomaetsya klasterizatsiya - sklad vse ravno dolzhen vydavat tovar: poetomu rezhim degradatsii."""