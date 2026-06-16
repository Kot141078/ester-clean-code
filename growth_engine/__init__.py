# -*- coding: utf-8 -*-
"""growth_engine - a bounded, auditable instrumental self-improvement engine.

NOT consciousness, NOT "becoming", NOT subjecthood, NOT open-ended self-rewriting.
It makes tools / policies / routing / memory-weights *provably better* against an
external fitness signal, with every change witnessed, gated, and reversible.

Designed to mirror ester-clean-code idioms (fail-closed gates, hash-chained witness,
L4 budgets) and to be wired into it via documented seams (see README).
"""
from .common import ok, err, hash_obj, q
from .witness import GrowthWitnessLedger
from .fitness import Episode, Outcome, FitnessLedger, VALID_SOURCES
from .behavior import BehaviorVersion, new_version, decide
from .candidates import (
    Candidate,
    propose_param_candidates,
    make_tool_code_candidate,
    RISK_LOW,
    RISK_MED,
    RISK_HIGH,
)
from .sandbox import ReplaySet, shadow_eval
from .promotion import PromotionGate
from .engine import GrowthEngine

__all__ = [
    "ok",
    "err",
    "hash_obj",
    "q",
    "GrowthWitnessLedger",
    "Episode",
    "Outcome",
    "FitnessLedger",
    "VALID_SOURCES",
    "BehaviorVersion",
    "new_version",
    "decide",
    "Candidate",
    "propose_param_candidates",
    "make_tool_code_candidate",
    "RISK_LOW",
    "RISK_MED",
    "RISK_HIGH",
    "ReplaySet",
    "shadow_eval",
    "PromotionGate",
    "GrowthEngine",
]

__version__ = "0.1.0"
