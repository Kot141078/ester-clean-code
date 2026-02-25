# modules/mvp_agents.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@dataclass
class AgentProfile:
    id: str
    mission: str
    capabilities: List[str]
    risk: str  # low/medium/high

PROFILES: Dict[str, AgentProfile] = {
    "director": AgentProfile(
        id="director",
        mission="Route requests and collect response.",
        capabilities=["route", "plan", "merge_results", "rate_limit"],
        risk="medium",
    ),
    "ops_guard": AgentProfile(
        id="ops_guard",
        mission="Diagnostika i zdorove uzla.",
        capabilities=["healthcheck", "inspect_routes", "inspect_env"],
        risk="high",
    ),
    "rag_researcher": AgentProfile(
        id="rag_researcher",
        mission="Dostavat relevantnyy kontekst iz pamyati/dokov.",
        capabilities=["retrieve", "quote", "summarize"],
        risk="medium",
    ),
    "messenger": AgentProfile(
        id="messenger",
        mission="Sending messages via approved channels/templates.",
        capabilities=["compose", "queue_outbox"],
        risk="high",
    ),
    "maker_dev": AgentProfile(
        id="maker_dev",
        mission="Draft modules + checks (without auto-application).",
        capabilities=["draft", "test", "diff"],
        risk="high",
    ),
}

def list_profiles() -> List[Dict[str, Any]]:
    return [asdict(p) for p in PROFILES.values()]

def run_agent(agent_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if agent_id not in PROFILES:
        return {"ok": False, "error": "unknown_agent", "agent_id": agent_id}

    # MVP: for now the “stub” is just an echo + profile.
    prof = PROFILES[agent_id]
    return {
        "ok": True,
        "agent": asdict(prof),
        "input": payload,
        "output": f"[{agent_id}] received: {payload}",
    }