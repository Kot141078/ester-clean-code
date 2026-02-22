# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.volition import journal

try:
    from modules.autonomy import state as autonomy_state  # type: ignore
except Exception:  # pragma: no cover
    autonomy_state = None  # type: ignore

try:
    from modules.ops import control_state as ops_control_state  # type: ignore
except Exception:  # pragma: no cover
    ops_control_state = None  # type: ignore

try:
    from modules.memory.memory_bus import MemoryBus  # type: ignore
except Exception:  # pragma: no cover
    MemoryBus = None  # type: ignore

_PROACTIVE_STEPS = {"initiative", "plan", "agent", "action"}
_NETWORK_HINTS = (
    "network",
    "http",
    "https",
    "telegram",
    "webhook",
    "peer",
    "serp",
    "outbound",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        return int(default)


def _float_env(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        return float(default)


def _norm_step(step: Any) -> str:
    s = str(step or "action").strip().lower()
    if s not in {"initiative", "plan", "agent", "action", "http_route"}:
        return "action"
    return s


def _now_ts() -> int:
    return int(time.time())


@dataclass
class VolitionContext:
    chain_id: str = ""
    step: str = "action"
    actor: str = "ester"
    intent: str = ""
    action_kind: Optional[str] = None
    route: Optional[str] = None
    needs: List[str] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, value: Any) -> "VolitionContext":
        if isinstance(value, VolitionContext):
            return value
        if isinstance(value, dict):
            return cls(
                chain_id=str(value.get("chain_id") or ""),
                step=str(value.get("step") or "action"),
                actor=str(value.get("actor") or "ester"),
                intent=str(value.get("intent") or ""),
                action_kind=value.get("action_kind"),
                route=value.get("route"),
                needs=list(value.get("needs") or []),
                budgets=dict(value.get("budgets") or {}),
                metadata=dict(value.get("metadata") or {}),
            )
        return cls()

    def normalized(self) -> "VolitionContext":
        chain = str(self.chain_id or "").strip() or ("chain_" + uuid.uuid4().hex[:12])
        return VolitionContext(
            chain_id=chain,
            step=_norm_step(self.step),
            actor=str(self.actor or "ester").strip() or "ester",
            intent=str(self.intent or "").strip(),
            action_kind=(str(self.action_kind) if self.action_kind is not None else None),
            route=(str(self.route) if self.route is not None else None),
            needs=[str(x) for x in (self.needs or []) if str(x).strip()],
            budgets=dict(self.budgets or {}),
            metadata=dict(self.metadata or {}),
        )


@dataclass
class VolitionDecision:
    id: str
    allowed: bool
    reason_code: str
    reason: str
    slot: str
    policy_snapshot: Dict[str, Any]
    ts: int
    duration_ms: int
    counters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VolitionGate:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bucket_ts = 0
        self._window_sec = 60
        self._work_ms_used = 0
        self._actions_used = 0
        self._network_calls_used = 0
        self._error_streak = 0
        self._force_slot_a = False
        self._memory_cache_ts = 0.0
        self._memory_cache_value: Optional[bool] = None

    def _slot(self) -> str:
        with self._lock:
            if self._force_slot_a:
                return "A"
        slot = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
        return "B" if slot == "B" else "A"

    def _network_env_allowed(self) -> bool:
        return _truthy(os.getenv("ESTER_ALLOW_NETWORK", "")) or _truthy(
            os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
        )

    def _allowed_hours(self) -> str:
        return str(os.getenv("ESTER_VOLITION_ALLOWED_HOURS", "07:00-23:00") or "07:00-23:00").strip()

    def _time_in_window(self, window: str) -> bool:
        parts = [p.strip() for p in str(window or "").split("-")]
        if len(parts) != 2:
            return True
        try:
            sh, sm = [int(x) for x in parts[0].split(":", 1)]
            eh, em = [int(x) for x in parts[1].split(":", 1)]
        except Exception:
            return True
        now = datetime.now()
        cur = now.hour * 60 + now.minute
        start = max(0, min(23, sh)) * 60 + max(0, min(59, sm))
        end = max(0, min(23, eh)) * 60 + max(0, min(59, em))
        if start <= end:
            return start <= cur <= end
        return cur >= start or cur <= end

    def _autonomy_snapshot(self) -> Dict[str, Any]:
        snap: Dict[str, Any] = {}
        if autonomy_state is not None:
            try:
                raw = autonomy_state.get()
                if isinstance(raw, dict):
                    snap.update(raw)
            except Exception as exc:
                snap["autonomy_error"] = str(exc)
        if ops_control_state is not None:
            try:
                snap["control_paused"] = bool(ops_control_state.get_paused())
            except Exception as exc:
                snap["control_state_error"] = str(exc)
        return snap

    def _memory_ready(self) -> Optional[bool]:
        if MemoryBus is None:
            return None
        now = time.monotonic()
        if (now - self._memory_cache_ts) < 5.0:
            return self._memory_cache_value
        try:
            bus = MemoryBus(use_vector=False, use_chroma=False)
            raw = bus.readiness_status()
            val = bool((raw or {}).get("memory_ready"))
        except Exception:
            val = None
        with self._lock:
            self._memory_cache_ts = now
            self._memory_cache_value = val
        return val

    def _needs_network(self, ctx: VolitionContext) -> bool:
        for item in ctx.needs:
            low = str(item or "").lower()
            if any(tok in low for tok in _NETWORK_HINTS):
                return True
        marker = " ".join([str(ctx.action_kind or ""), str(ctx.route or ""), str(ctx.intent or "")]).lower()
        return any(tok in marker for tok in _NETWORK_HINTS)

    def _budget_defaults(self, ctx: VolitionContext) -> Dict[str, Any]:
        window = int(ctx.budgets.get("window") or _int_env("ESTER_VOLITION_WINDOW_SEC", 60))
        max_work_ms = int(ctx.budgets.get("max_work_ms") or _int_env("ESTER_VOLITION_MAX_WORK_MS", 2000))
        max_actions = int(ctx.budgets.get("max_actions") or _int_env("ESTER_VOLITION_MAX_ACTIONS", 3))
        est_work_ms = int(
            ctx.budgets.get("est_work_ms")
            or _int_env("ESTER_VOLITION_EST_WORK_MS", min(250, max(1, int(max_work_ms))))
        )
        watts = float(_float_env("ESTER_EST_WATTS_DEFAULT", 35.0))
        est_energy_j = float(ctx.budgets.get("est_energy_j") or (watts * est_work_ms / 1000.0))
        return {
            "window": max(1, int(window)),
            "max_work_ms": max(1, int(max_work_ms)),
            "max_actions": max(1, int(max_actions)),
            "est_work_ms": max(1, min(int(max_work_ms), int(est_work_ms))),
            "est_energy_j": round(float(est_energy_j), 6),
        }

    def _roll_bucket(self, window_sec: int) -> None:
        now = _now_ts()
        bucket = int(now // max(1, window_sec) * max(1, window_sec))
        with self._lock:
            if bucket != self._bucket_ts or window_sec != self._window_sec:
                self._bucket_ts = bucket
                self._window_sec = window_sec
                self._work_ms_used = 0
                self._actions_used = 0
                self._network_calls_used = 0

    def _counters(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "bucket_ts": int(self._bucket_ts),
                "window_sec": int(self._window_sec),
                "work_ms_used": int(self._work_ms_used),
                "actions_used": int(self._actions_used),
                "network_calls_used": int(self._network_calls_used),
            }

    def _consume(self, proactive: bool, est_work_ms: int, needs_network: bool) -> Dict[str, Any]:
        with self._lock:
            if proactive:
                self._work_ms_used += max(0, int(est_work_ms))
                self._actions_used += 1
            if needs_network:
                self._network_calls_used += 1
            return self._counters()

    def _budget_allows(
        self,
        proactive: bool,
        est_work_ms: int,
        needs_network: bool,
        max_work_ms: int,
        max_actions: int,
    ) -> Tuple[bool, str, str]:
        if not proactive:
            return True, "ALLOW", "non_proactive_step"
        cur = self._counters()
        if int(cur["actions_used"]) + 1 > max_actions:
            return False, "DENY_BUDGET", f"actions budget exceeded: {cur['actions_used']}/{max_actions}"
        if int(cur["work_ms_used"]) + int(est_work_ms) > max_work_ms:
            return False, "DENY_BUDGET", f"work budget exceeded: {cur['work_ms_used']}/{max_work_ms} ms"
        if needs_network and int(cur["network_calls_used"]) + 1 > max_actions:
            return False, "DENY_BUDGET", "network calls budget exceeded"
        return True, "ALLOW", "budget_ok"

    def _build_policy(self, ctx: VolitionContext) -> Dict[str, Any]:
        budgets = self._budget_defaults(ctx)
        proactive = ctx.step in _PROACTIVE_STEPS and (
            ctx.actor == "ester" or str(ctx.actor).startswith("agent:")
        )
        needs_network = self._needs_network(ctx)
        network_env_allowed = self._network_env_allowed()
        hours = self._allowed_hours()
        in_hours = self._time_in_window(hours)
        snap = self._autonomy_snapshot()
        paused = bool(snap.get("paused") or snap.get("control_paused"))
        return {
            "proactive_step": proactive,
            "needs_network": needs_network,
            "network_env_allowed": network_env_allowed,
            "allowed_hours": hours,
            "in_allowed_hours": in_hours,
            "autonomy_paused": paused,
            **budgets,
        }

    def _decide_core(self, ctx: VolitionContext, slot: str, policy: Dict[str, Any]) -> Tuple[bool, str, str]:
        if policy.get("autonomy_paused"):
            return False, "DENY_PAUSED", "autonomy paused"
        if policy.get("proactive_step") and not policy.get("in_allowed_hours"):
            return False, "DENY_WINDOW", "outside allowed proactive hours"
        if policy.get("needs_network") and not policy.get("network_env_allowed"):
            return False, "DENY_NETWORK", "network disabled by env"
        b_ok, b_code, b_reason = self._budget_allows(
            proactive=bool(policy.get("proactive_step")),
            est_work_ms=int(policy.get("est_work_ms", 0)),
            needs_network=bool(policy.get("needs_network")),
            max_work_ms=int(policy.get("max_work_ms", 0)),
            max_actions=int(policy.get("max_actions", 0)),
        )
        if not b_ok:
            return False, b_code, b_reason
        return True, "ALLOW", "policy_allow"

    def _note_error(self) -> bool:
        limit = max(1, _int_env("ESTER_VOLITION_AUTO_ROLLBACK_N", 3))
        with self._lock:
            self._error_streak += 1
            if self._error_streak >= limit:
                self._force_slot_a = True
                return True
            return False

    def _clear_error_streak(self) -> None:
        with self._lock:
            self._error_streak = 0

    def _journal(self, ctx: VolitionContext, decision: VolitionDecision) -> None:
        autonomy = self._autonomy_snapshot()
        metadata = dict(ctx.metadata or {})
        agent_id = str(metadata.get("agent_id") or "")
        plan_id = str(metadata.get("plan_id") or "")
        action_id = str(metadata.get("action_id") or ctx.action_kind or "")
        args_digest = str(metadata.get("args_digest") or "")
        raw_step_index = metadata.get("step_index")
        try:
            step_index = int(raw_step_index) if raw_step_index is not None else None
        except Exception:
            step_index = None
        raw_budgets_snapshot = metadata.get("budgets_snapshot")
        budgets_snapshot = dict(raw_budgets_snapshot) if isinstance(raw_budgets_snapshot, dict) else {}
        if not budgets_snapshot:
            budgets_snapshot = {
                "time_window": int((decision.policy_snapshot or {}).get("window") or 0),
                "max_ms": int((decision.policy_snapshot or {}).get("max_work_ms") or 0),
                "max_steps": int((decision.policy_snapshot or {}).get("max_actions") or 0),
                "oracle_window": str(
                    metadata.get("oracle_window")
                    or metadata.get("window_id")
                    or (ctx.budgets or {}).get("oracle_window")
                    or ""
                ),
            }
        policy_hit = str(metadata.get("policy_hit") or decision.reason_code or "")
        rec: Dict[str, Any] = {
            "id": decision.id,
            "ts": decision.ts,
            "chain_id": ctx.chain_id,
            "step": ctx.step,
            "actor": ctx.actor,
            "intent": ctx.intent,
            "action_kind": ctx.action_kind,
            "route": ctx.route,
            "allowed": decision.allowed,
            "reason_code": decision.reason_code,
            "reason": decision.reason,
            "budgets": dict(ctx.budgets or {}),
            "counters": dict(decision.counters or {}),
            "slot": decision.slot,
            "needs": list(ctx.needs or []),
            "metadata": metadata,
            "agent_id": agent_id,
            "plan_id": plan_id,
            "step_index": step_index,
            "action_id": action_id,
            "args_digest": args_digest,
            "budgets_snapshot": budgets_snapshot,
            "decision": "allow" if bool(decision.allowed) else "deny",
            "policy_hit": policy_hit,
            "autonomy_state": autonomy,
            "memory_ready": self._memory_ready(),
            "policy_snapshot": dict(decision.policy_snapshot or {}),
            "duration_ms": decision.duration_ms,
        }
        journal.append(rec)

    def decide(self, ctx: Any) -> VolitionDecision:
        start = time.monotonic()
        raw_ctx = VolitionContext.from_any(ctx).normalized()
        slot = self._slot()
        policy = self._build_policy(raw_ctx)
        self._roll_bucket(int(policy.get("window", 60)))
        try:
            would_allow, code, reason = self._decide_core(raw_ctx, slot, policy)
            if slot == "B":
                allowed = bool(would_allow)
                reason_code = str(code if not allowed else "ALLOW")
                reason_text = str(reason if not allowed else "allowed by policy")
            else:
                allowed = True
                reason_code = "ALLOW_SLOT_A"
                if would_allow:
                    reason_text = "observe-only slot A"
                else:
                    reason_text = f"observe-only slot A (would deny: {code})"
                policy["would_allow"] = bool(would_allow)
                policy["would_reason_code"] = str(code)
                policy["would_reason"] = str(reason)

            if allowed:
                counters = self._consume(
                    proactive=bool(policy.get("proactive_step")),
                    est_work_ms=int(policy.get("est_work_ms", 0)),
                    needs_network=bool(policy.get("needs_network")),
                )
            else:
                counters = self._counters()
            self._clear_error_streak()
        except Exception as exc:
            rolled = self._note_error()
            err = f"{exc.__class__.__name__}: {exc}"
            if slot == "B":
                allowed = False
                reason_code = "DENY_EXCEPTION"
                reason_text = "gate exception in enforce mode"
            else:
                allowed = True
                reason_code = "ALLOW_SLOT_A"
                reason_text = "gate exception in observe mode"
            policy["exception"] = err
            policy["auto_rollback_to_A"] = bool(rolled)
            counters = self._counters()

        decision = VolitionDecision(
            id="vol_" + uuid.uuid4().hex,
            allowed=bool(allowed),
            reason_code=str(reason_code),
            reason=str(reason_text),
            slot=slot,
            policy_snapshot=policy,
            ts=_now_ts(),
            duration_ms=max(0, int((time.monotonic() - start) * 1000)),
            counters=counters,
        )
        self._journal(raw_ctx, decision)
        return decision

    def ensure(self, ctx: Any) -> VolitionDecision:
        decision = self.decide(ctx)
        if (
            decision.slot == "A"
            and _truthy(os.getenv("ESTER_VOLITION_SLOTA_RAISE", "0"))
            and not bool((decision.policy_snapshot or {}).get("would_allow", True))
        ):
            raise RuntimeError(f"volition observe warning: {decision.reason_code}")
        return decision


_DEFAULT_GATE: Optional[VolitionGate] = None
_DEFAULT_LOCK = threading.RLock()


def get_default_gate() -> VolitionGate:
    global _DEFAULT_GATE
    with _DEFAULT_LOCK:
        if _DEFAULT_GATE is None:
            _DEFAULT_GATE = VolitionGate()
        return _DEFAULT_GATE


def decide(ctx: Any) -> VolitionDecision:
    return get_default_gate().decide(ctx)


def ensure(ctx: Any) -> VolitionDecision:
    return get_default_gate().ensure(ctx)


__all__ = [
    "VolitionContext",
    "VolitionDecision",
    "VolitionGate",
    "get_default_gate",
    "decide",
    "ensure",
]
