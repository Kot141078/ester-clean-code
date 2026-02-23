# -*- coding: utf-8 -*-
"""
schemas/memory_types.py — tipy dannykh pamyati «kak u cheloveka».
Edinaya skhema dlya epizodov, semantiki, kartochek, aliasov i flashback-paketov.
"""

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
    """
    Epizody — «chto, gde, kogda» (syrye fragmenty opyta).
    """

    id: str
    user: str
    text: str
    created_at: str
    updated_at: str
    doc_id: (
        str  # stabilnyy identifikator dokumenta/istochnika
    )
    weight: float = 1.0  # «sila vspominaniya» (decay ee ponizhaet)
    tokens: int = (
        0  # priblizitelnaya dlina (dlya kompakta/ogranicheniy)
    )
    summary: Optional[str] = (
        None  # kompaktnaya svodka dlinnogo epizoda
    )
    fragments: List[Dict[str, int]] = field(
        default_factory=list
    )  # [{start, end}] ssylki na iskhodnye kuski
    refs: List[str] = field(default_factory=list)  # svyazannye doc_id
    meta: Dict[str, Any] = field(
        default_factory=dict
    )  # proizvolnye metadannye (topic, folder, page, etc.)
    archived: bool = False  # «svernut» v semantiku (no ne udalen)
    folded_into: Optional[str] = None  # id SemanticEntry, esli «slozhen» tuda


@dataclass
class SemanticEntry:
    """
    Semanticheskie uzly — «smyslovye sgustki» (agregatsiya tem/ponyatiy).
    """

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
    )  # kakie doc_id podpityvayut etot uzel
    episode_ids: List[str] = field(
        default_factory=list
    )  # kakie epizody byli svernuty/ssylayutsya


@dataclass
class CardEntry:
    """
    Kartochki — «pod rukoy» (piny/fishki: opredeleniya, retsepty, chek-listy).
    """

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
    """
    Vechnye aliasy doc_id — pereimenovanie bez lomki ssylok.
    Khranim pryamuyu i obratnuyu karty dlya bystrogo razresheniya.
    """

    created_at: str
    updated_at: str
    forward: Dict[str, str] = field(default_factory=dict)  # old_id -> new_id
    reverse: Dict[str, List[str]] = field(default_factory=dict)  # new_id -> [old_id, ...]


class MemoryHit(TypedDict, total=False):
    """
    Unifitsirovannyy hit dlya RAG/Trace.
    """

    type: str  # "episode" | "semantic" | "card"
    id: str
    user: str
    score: float
    snippet: str
    doc_id: str
    meta: Dict[str, Any]


class FlashbackBundle(TypedDict, total=False):
    """
    Flashback-paket — rezultat kontekstnogo vspominaniya.
    """

    episodes: List[MemoryHit]
    semantics: List[MemoryHit]
    cards: List[MemoryHit]
    aliases: Dict[str, str]  # forward map (dlya klienta/trace)
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