# -*- coding: utf-8 -*-
"""
modules/synergy/learning.py — onlayn-adaptatsiya prigodnostey (EMA/bandit) + runtime-patch fit_roles_ext.

MOSTY:
- (Yavnyy) Khranim vesa per (agent_id, role) v SQLite: uspekh ↑, neudacha ↓ v granitsakh [W_MIN..W_MAX].
- (Skrytyy #1) Izvlekaem signaly iz tsepochki sobytiy AssignmentStore (Planned/OutcomeReported), obnovlyaem vesa.
- (Skrytyy #2) Patchim modules.synergy.role_model.fit_roles_ext bez smeny kontraktov: umnozhaem bazovye skora na vyuchennye vesa.

ZEMNOY ABZATs:
Sistema «uchitsya» na realnoy otdache: kogo stavit v operatora, kakuyu platformu predpochest i t.d.
Esli zadacha zakrylas uspeshno — sootvetstvuyuschie pary agent-rol poluchayut legkiy bonus; esli proval — shtraf.

# c=a+b
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.synergy.store import AssignmentStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ---------- konfig ----------

def _fenv(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

W_MIN = _fenv("SYNERGY_LEARNING_W_MIN", 0.70)
W_MAX = _fenv("SYNERGY_LEARNING_W_MAX", 1.30)
ALPHA = _fenv("SYNERGY_LEARNING_ALPHA", 0.06)

# ---------- SQL ----------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_weights(
  agent_id TEXT NOT NULL,
  role TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  n INTEGER NOT NULL DEFAULT 0,
  updated_ts INTEGER NOT NULL,
  PRIMARY KEY(agent_id, role)
);
"""

def _db_path() -> str:
    # tot zhe fayl, chto u AssignmentStore
    p = os.getenv("SYNERGY_DB_PATH")
    if p:
        return p
    url = os.getenv("SYNERGY_DB_URL", "sqlite:///data/ester.db")
    return url.replace("sqlite:///", "")

def _connect() -> sqlite3.Connection:
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.executescript(_SCHEMA)
    return conn

# ---------- menedzher ----------

@dataclass
class Weight:
    agent_id: str
    role: str
    weight: float
    n: int
    updated_ts: int

class LearningManager:
    """
    Prostoy kontur «obucheniya s podkrepleniem» dlya prigodnostey (bandit/EMA).
    """

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or _connect()

    # --- CRUD vesov ---

    def get_weight(self, agent_id: str, role: str) -> float:
        r = self.conn.execute(
            "SELECT weight FROM learning_weights WHERE agent_id=? AND role=?",
            (agent_id, role)
        ).fetchone()
        return float(r["weight"]) if r else 1.0

    def set_weight(self, agent_id: str, role: str, weight: float, inc_n: int = 1) -> Weight:
        w = max(W_MIN, min(W_MAX, float(weight)))
        ts = int(time.time())
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO learning_weights(agent_id,role,weight,n,updated_ts) VALUES(?,?,?,?,?) "
                "ON CONFLICT(agent_id,role) DO UPDATE SET weight=excluded.weight, n=learning_weights.n+?, updated_ts=excluded.updated_ts",
                (agent_id, role, w, max(0, inc_n), ts, max(0, inc_n)),
            )
        return Weight(agent_id, role, w, (self._sel_n(agent_id, role)), ts)

    def _sel_n(self, agent_id: str, role: str) -> int:
        r = self.conn.execute(
            "SELECT n FROM learning_weights WHERE agent_id=? AND role=?",
            (agent_id, role)
        ).fetchone()
        return int(r["n"]) if r else 0

    def list_weights(self) -> List[Weight]:
        rows = self.conn.execute("SELECT * FROM learning_weights").fetchall()
        return [Weight(r["agent_id"], r["role"], float(r["weight"]), int(r["n"]), int(r["updated_ts"])) for r in rows]

    # --- obuchenie iz sobytiy ---

    @staticmethod
    def _reward(outcome: str) -> float:
        """
        Primitivnaya funktsiya nagrady: success -> +1, failure -> -1, partial -> +0.3, cancelled -> -0.2
        """
        o = (outcome or "").strip().lower()
        if o == "success":
            return +1.0
        if o == "failure":
            return -1.0
        if o == "partial":
            return +0.3
        if o == "cancelled":
            return -0.2
        return 0.0

    def train_from_events(self, team_id: Optional[str] = None, since_ts: Optional[int] = None) -> int:
        """
        Nakhodit pary sobytiy (Planned -> OutcomeReported) i obnovlyaet vesa (EMA).
        Vozvraschaet kolichestvo obnovlennykh (agent,role).
        """
        s = AssignmentStore.default()
        # Poluchaem sobytiya (gipoteza: ikh ne bolshe desyatkov tysyach)
        events = s.list_events(team_id or "") if team_id else s.list_events(team_id="*")  # '*' — vse; sm. nizhe
        # Esli '*' — podkhvatim vse komandy vruchnuyu
        if team_id is None:
            # kostyl: metod list_events trebuet team_id; oboydem — progulyaemsya po izvestnym
            team_ids = set()
            # dostanem iz sobytiy odnoy komandy (STORE ikh ne vydaet globalno) — ispolzuem obkhod id ot SQLite
            # Uprostim: budem chitat po izvestnym, naydennym v uzhe poluchennom spiske
            for e in events:
                team_ids.add(e.team_id)
            updated = 0
            for t in team_ids:
                updated += self.train_from_events(team_id=t, since_ts=since_ts)
            return updated

        # Filtruem nuzhnuyu komandu
        evs = [e for e in events if (since_ts is None or e.ts >= since_ts)]
        planned: Dict[str, Dict[str, Any]] = {}  # request_id -> assigned
        updated_pairs = 0

        for e in evs:
            if e.type == "Planned":
                assigned = (e.payload.get("result") or {}).get("assigned") or {}
                req_id = (e.request_id or "").strip()
                trace_id = str((e.payload.get("result") or {}).get("trace_id") or "").strip()
                if req_id:
                    planned[req_id] = dict(assigned)
                if trace_id:
                    planned[trace_id] = dict(assigned)
                if not req_id and not trace_id:
                    planned[f"ts:{e.ts}"] = dict(assigned)
            elif e.type == "OutcomeReported":
                rid = (e.request_id or "").strip()
                assigned = planned.get(rid) or {}
                if not assigned:
                    # net svyazannogo plana — propuskaem
                    continue
                rew = self._reward(str((e.payload or {}).get("outcome") or ""))
                if rew == 0.0:
                    continue
                # EMA: w := clamp( w + alpha*rew*(1 - (w-1)^2) )
                for role, agent_id in assigned.items():
                    w0 = self.get_weight(agent_id, role)
                    # pri plokhom iskhode silnee nakazyvaem platformu/operatora
                    alpha = ALPHA * (1.4 if role in ("platform", "operator") and rew < 0 else 1.0)
                    w1 = w0 + alpha * rew * (1.0 - (w0 - 1.0) * (w0 - 1.0))
                    self.set_weight(agent_id, role, w1, inc_n=1)
                    updated_pairs += 1

        return updated_pairs

    # --- primenenie vesov ---

    def adjust_scores_for_agent(self, agent: Dict[str, Any], base_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Umnozhaet bazovye skora na vyuchennye vesa (per agent-role).
        """
        aid = agent.get("id") or ""
        out: Dict[str, float] = {}
        for role, s in base_scores.items():
            w = self.get_weight(aid, role)
            out[role] = max(0.0, min(1.0, s * w))
        return out

    # --- staticheskiy konstruktor ---

    @staticmethod
    def default() -> "LearningManager":
        return LearningManager()

# ---------- runtime-patch fit_roles_ext ----------

_PATCHED = False
_ORIG = None

def enable_runtime_patch() -> bool:
    """
    Patchit modules.synergy.role_model.fit_roles_ext tak, chtoby on uchityval vyuchennye vesa.
    Idempotenten: povtornyy vyzov nichego ne lomaet.
    """
    global _PATCHED, _ORIG
    try:
        import modules.synergy.role_model as rm  # noqa: WPS433
    except Exception:
        return False
    if not hasattr(rm, "fit_roles_ext"):
        return False
    current = rm.fit_roles_ext
    if getattr(current, "_synergy_learning_wrapped", False):
        _PATCHED = True
        return True
    _ORIG = current
    orig = current

    def _wrapped(agent: Dict[str, Any]) -> Dict[str, float]:
        base = orig(agent)
        try:
            lm = LearningManager.default()
            return lm.adjust_scores_for_agent(agent, base)
        except Exception:
            return base

    setattr(_wrapped, "_synergy_learning_wrapped", True)
    rm.fit_roles_ext = _wrapped  # tip: ignore
    _PATCHED = True
    return True

# Avto-vklyuchenie po ENV (esli modul kto-to importiroval)
if os.getenv("SYNERGY_LEARNING_PATCH", "0") == "1":
    try:
        enable_runtime_patch()
    except Exception:
        pass
