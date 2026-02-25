# -*- coding: utf-8 -*-
"""schemas/memory_topes.po - “human-like” memory data types.
A unified scheme for episodes, semantics, cards, aliases and flashback packages."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class EpisodicEntry:
    """Episodes - “what, where, when” (raw fragments of experience)."""

    id: str
    user: str
    text: str
    created_at: str
    updated_at: str
    doc_id: (
        str  # stabilnyy identifikator dokumenta/istochnika
    )
    weight: float = 1.0  # “the power of recollection” (desai lowers it)
    tokens: int = (
        0  # approximate length (for compact/constraints)
    )
    summary: Optional[str] = (
        None  # compact summary of a long episode
    )
    fragments: List[Dict[str, int]] = field(
        default_factory=list
    )  # [{start, end}] ssylki na iskhodnye kuski
    refs: List[str] = field(default_factory=list)  # svyazannye doc_id
    meta: Dict[str, Any] = field(
        default_factory=dict
    )  # proizvolnye metadannye (topic, folder, page, etc.)
    archived: bool = False  # "collapse" into semantics (but not deleted)
    folded_into: Optional[str] = None  # Semantic Center id, if “folded” there


@dataclass
class SemanticEntry:
    """Semantic nodes are “semantic clusters” (aggregation of topics/concepts)."""

    id: str
    user: str
    topic: str
    summary: str
    concepts: List[str]
    created_at: str
    updated_at: str
    weight: float = 1.0
    doc_ids: List[str] = field(
        default_factory=list
    )  # what doc_ids feed this node
    episode_ids: List[str] = field(
        default_factory=list
    )  # which episodes were collapsed/referenced


@dataclass
class CardEntry:
    """Cards - “at hand” (pins/chips: definitions, recipes, checklists)."""

    id: str
    user: str
    title: str
    content: str
    tags: List[str]
    created_at: str
    updated_at: str
    weight: float = 1.0
    links: List[str] = field(default_factory=list)  # doc_id / vneshnie ssylki


@dataclass
class AliasMap:
    """Eternal aliases daughter_id - renaming without breaking links.
    We store forward and reverse maps for quick resolution."""

    created_at: str
    updated_at: str
    forward: Dict[str, str] = field(default_factory=dict)  # old_id -> new_id
    reverse: Dict[str, List[str]] = field(default_factory=dict)  # new_id -> [old_id, ...]


class MemoryHit(TypedDict, total=False):
    """Unified thread for RAG/Trace."""

    type: str  # "episode" | "semantic" | "card"
    id: str
    user: str
    score: float
    snippet: str
    doc_id: str
    meta: Dict[str, Any]


class FlashbackBundle(TypedDict, total=False):
    """The flashbatch is the result of contextual recall."""

    episodes: List[MemoryHit]
    semantics: List[MemoryHit]
    cards: List[MemoryHit]
    aliases: Dict[str, str]  # forward map (for client/trace)
    stats: Dict[str, Any]  # ms, counts, notes


# --------- Utility preobrazovaniya ---------


def to_dict_dc(obj) -> Dict[str, Any]:
    return asdict(obj)


def mk_episode(
    user: str, text: str, doc_id: str, meta: Optional[Dict[str, Any]] = None
) -> EpisodicEntry:
    eid = gen_id("ep")
    ts = now_iso()
    return EpisodicEntry(
        id=eid,
        user=user,
        text=text,
        created_at=ts,
        updated_at=ts,
        doc_id=doc_id,
        tokens=max(1, len(text) // 4),
        meta=meta or {},
    )


def mk_semantic(
    user: str, topic: str, summary: str, concepts: Optional[List[str]] = None
) -> SemanticEntry:
    sid = gen_id("sem")
    ts = now_iso()
    return SemanticEntry(
        id=sid,
        user=user,
        topic=topic,
        summary=summary,
        concepts=concepts or [],
        created_at=ts,
        updated_at=ts,
    )


def mk_card(user: str, title: str, content: str, tags: Optional[List[str]] = None) -> CardEntry:
    cid = gen_id("card")
    ts = now_iso()
    return CardEntry(
        id=cid,
        user=user,
        title=title,
        content=content,
        tags=tags or [],
        created_at=ts,
        updated_at=ts,
    )


def mk_alias_map() -> AliasMap:
    ts = now_iso()
# return AliasMap(created_at=ts, updated_at=ts)