# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _run_root() -> Path:
    env = (os.getenv("DAG_RUN_ROOT") or "").strip()
    if env:
        p = Path(env).resolve()
    else:
        base = Path(os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")).resolve()
        p = base / "graph" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


BR_ROOT = _run_root()
_LOCK = threading.Lock()
_TPL = re.compile(r"{{\s*([^{}]+)\s*}}")


def _slug(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", str(s or "").strip())
    return out.strip("-") or "run"


def _run_dir(run_id: str) -> Path:
    path = _run_root() / _slug(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_run_dir(run_id: str) -> Path:
    return _run_dir(run_id)


def _state_path(run_id: str) -> Path:
    return _run_dir(run_id) / "state.json"


def _ctx_path(run_id: str, branch_id: str) -> Path:
    return _run_dir(run_id) / f"{branch_id}.json"


def _gen_run_id(plan: Dict[str, Any]) -> str:
    raw = json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"run-{hashlib.sha1(raw).hexdigest()[:10]}-{int(time.time())}"


def _resolve_expr(expr: str, ctx: Dict[str, Any], item: Any) -> Any:
    root: Any
    path: List[str]
    e = str(expr or "").strip()
    if e == "ctx":
        return ctx
    if e == "item":
        return item
    if e.startswith("ctx."):
        root = ctx
        path = e[4:].split(".")
    elif e.startswith("item."):
        root = item
        path = e[5:].split(".")
    else:
        root = ctx
        path = e.split(".")

    cur: Any = root
    for part in path:
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _render_value(value: Any, ctx: Dict[str, Any], item: Any) -> Any:
    if isinstance(value, str):
        full = re.fullmatch(r"\s*{{\s*([^{}]+)\s*}}\s*", value)
        if full:
            return _resolve_expr(full.group(1), ctx, item)

        def _sub(match: re.Match[str]) -> str:
            v = _resolve_expr(match.group(1), ctx, item)
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return str(v)

        return _TPL.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _render_value(v, ctx, item) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(v, ctx, item) for v in value]
    return value


def load_plan_from_text(text: str) -> Dict[str, Any]:
    src = text or ""
    try:
        obj = json.loads(src)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    try:
        import yaml  # type: ignore

        obj = yaml.safe_load(src)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {"nodes": []}


def load_state(run_id: str) -> Dict[str, Any]:
    p = _state_path(run_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(run_id_or_obj, state: Dict[str, Any] | None = None) -> str:
    if state is None and isinstance(run_id_or_obj, dict):
        payload = dict(run_id_or_obj)
        run_id = str(payload.get("run_id") or "run")
    else:
        run_id = str(run_id_or_obj)
        payload = dict(state or {})
    p = _state_path(run_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort persistence for tests that aggressively clean temp dirs.
        pass
    return str(p)


def load_context(run_id: str, branch_id: str) -> Dict[str, Any]:
    p = _ctx_path(run_id, branch_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_context(run_id: str, branch_id: str, ctx: Dict[str, Any]) -> None:
    p = _ctx_path(run_id, branch_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class DAGEngine:
    def __init__(self, plan: Dict[str, Any]):
        self.plan = dict(plan or {})
        self.run_id = str(self.plan.get("run_id") or _gen_run_id(self.plan))
        self.root_branch = str(self.plan.get("branch_id") or "main")
        persisted = load_state(self.run_id) if self.run_id else {}
        persisted_defs = persisted.get("node_defs") or []
        persisted_by_id: Dict[str, Dict[str, Any]] = {}
        if isinstance(persisted_defs, list):
            for raw in persisted_defs:
                if not isinstance(raw, dict):
                    continue
                nid = str(raw.get("id") or "").strip()
                if nid:
                    persisted_by_id[nid] = dict(raw)

        raw_nodes = list(self.plan.get("nodes") or [])
        if not raw_nodes and persisted_by_id:
            raw_nodes = [dict(v) for v in persisted_by_id.values()]

        self.nodes: List[Dict[str, Any]] = []
        for i, raw in enumerate(raw_nodes):
            incoming = dict(raw or {})
            incoming_id = str(incoming.get("id") or f"n{i+1}")
            base = dict(persisted_by_id.get(incoming_id) or {})
            node = {**base, **incoming}
            node_id = str(node.get("id") or f"n{i+1}")
            node_type = str(node.get("type") or node.get("kind") or base.get("type") or "noop")
            node["id"] = node_id
            node["type"] = node_type
            self.nodes.append(node)
        self.node_ids = [n["id"] for n in self.nodes]
        self.node_map = {n["id"]: n for n in self.nodes}
        self.state = self._bootstrap_state()

    def _bootstrap_state(self) -> Dict[str, Any]:
        existing = load_state(self.run_id)
        if existing:
            state = existing
            state.setdefault("run_id", self.run_id)
            state.setdefault("branch_id", self.root_branch)
            state.setdefault("branches", {})
            state.setdefault("inflight", {})
            state.setdefault("fanouts", {})
            state.setdefault("finished", False)
            state.setdefault("node_defs", [dict(n) for n in self.nodes])
            for branch, bdata in list((state.get("branches") or {}).items()):
                bnodes = dict((bdata or {}).get("nodes") or {})
                for nid in self.node_ids:
                    bnodes.setdefault(nid, "pending")
                state["branches"][branch] = {"nodes": bnodes}
                if not _ctx_path(self.run_id, branch).exists():
                    _save_context(self.run_id, branch, {})
            save_state(self.run_id, state)
            return state

        base_ctx = dict(self.plan.get("context_init") or {})
        state = {
            "run_id": self.run_id,
            "branch_id": self.root_branch,
            "branches": {
                self.root_branch: {"nodes": {nid: "pending" for nid in self.node_ids}}
            },
            "inflight": {},
            "fanouts": {},
            "finished": False,
            "created_ts": time.time(),
            "node_defs": [dict(n) for n in self.nodes],
        }
        _save_context(self.run_id, self.root_branch, base_ctx)
        save_state(self.run_id, state)
        return state

    def _deps_satisfied(self, branch: str, node: Dict[str, Any]) -> bool:
        deps = [str(x) for x in (node.get("depends") or [])]
        bnodes = (self.state.get("branches", {}).get(branch, {}) or {}).get("nodes", {})
        for dep in deps:
            st = str(bnodes.get(dep) or "")
            if st == "done":
                continue
            return False
        return True

    def _make_child_branch(self, parent: str, idx: int) -> str:
        return f"{parent}#{idx:02d}"

    def _ensure_branch(self, branch: str, seed_nodes: Dict[str, str], ctx: Dict[str, Any]) -> None:
        branches = self.state.setdefault("branches", {})
        bnodes = {nid: seed_nodes.get(nid, "pending") for nid in self.node_ids}
        branches[branch] = {"nodes": bnodes}
        _save_context(self.run_id, branch, ctx)

    def _exec_fanout(self, branch: str, node: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        item = ctx.get("item")
        items = _render_value(node.get("items"), ctx, item)
        if not isinstance(items, list):
            items = []
        child_names: List[str] = []
        parent_nodes = (
            self.state.get("branches", {}).get(branch, {}) or {}
        ).get("nodes", {})
        seed = {k: ("done" if v == "done" else "pending") for k, v in parent_nodes.items()}
        seed[node["id"]] = "done"
        # Join nodes are aggregate-only in the root branch; child branches must
        # start with them terminal to avoid infinite pending states.
        for n in self.nodes:
            if str(n.get("type") or "") == "join":
                seed[str(n.get("id"))] = "done"
        for i, it in enumerate(items, start=1):
            child = self._make_child_branch(branch, i)
            child_ctx = copy.deepcopy(ctx)
            child_ctx["item"] = copy.deepcopy(it)
            self._ensure_branch(child, seed, child_ctx)
            child_names.append(child)
        self.state.setdefault("fanouts", {})[node["id"]] = child_names

    def _exec_script(self, branch: str, node: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        item = ctx.get("item")
        updates = node.get("update") or {}
        if isinstance(updates, dict):
            for k, v in updates.items():
                ctx[str(k)] = _render_value(v, ctx, item)
        if node.get("template") is not None and node.get("out"):
            ctx[str(node.get("out"))] = _render_value(node.get("template"), ctx, item)
        _save_context(self.run_id, branch, ctx)

    def _exec_llm_generate(self, branch: str, node: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        item = ctx.get("item")
        rendered = _render_value(node.get("prompt", ""), ctx, item)
        out_key = str(node.get("out") or "generated")
        ctx[out_key] = str(rendered or "")
        _save_context(self.run_id, branch, ctx)

    def _join_rows(self, branch: str, node: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[bool, Any]:
        source = str(node.get("from") or "").strip()
        if source:
            children = list((self.state.get("fanouts") or {}).get(source) or [])
        else:
            children = sorted(
                b for b in (self.state.get("branches") or {}).keys() if b.startswith(f"{branch}#")
            )

        await_nodes = [str(x) for x in (node.get("await_nodes") or [])]
        for child in children:
            child_nodes = (
                self.state.get("branches", {}).get(child, {}) or {}
            ).get("nodes", {})
            if any(str(child_nodes.get(nid) or "") != "done" for nid in await_nodes):
                return False, None

        select = node.get("select")
        rows: List[Tuple[str, Any]] = []
        for child in children:
            child_ctx = load_context(self.run_id, child)
            child_item = child_ctx.get("item")
            if isinstance(select, dict):
                row = {str(k): _render_value(v, child_ctx, child_item) for k, v in select.items()}
            else:
                row = {
                    "branch": child,
                    "item": child_item,
                    "context_keys": sorted(child_ctx.keys()),
                }
            rows.append((child, row))

        mode = str(node.get("mode") or "list").lower()
        if mode == "dict":
            key_field = node.get("key_field")
            out: Dict[str, Any] = {}
            for child, row in rows:
                if key_field:
                    key = str(
                        _render_value(
                            key_field,
                            load_context(self.run_id, child),
                            load_context(self.run_id, child).get("item"),
                        )
                        or child
                    )
                else:
                    key = child
                out[key] = row
            return True, out

        if mode == "text":
            sep = str(node.get("separator") or "\n")
            parts: List[str] = []
            for _, row in rows:
                if isinstance(row, dict) and "text" in row:
                    parts.append(str(row.get("text") or ""))
                else:
                    parts.append(json.dumps(row, ensure_ascii=False))
            return True, sep.join(parts)

        return True, [row for _, row in rows]

    def _execute_node(self, branch: str, node: Dict[str, Any]) -> bool:
        bnodes = (self.state.get("branches", {}).get(branch, {}) or {}).get("nodes", {})
        node_id = str(node.get("id"))
        ntype = str(node.get("type") or "noop")
        ctx = load_context(self.run_id, branch)
        item = ctx.get("item")

        if ntype == "fanout":
            self._exec_fanout(branch, node, ctx)
            bnodes[node_id] = "done"
            return True

        if ntype == "script":
            self._exec_script(branch, node, ctx)
            bnodes[node_id] = "done"
            return True

        if ntype in ("noop", "echo"):
            bnodes[node_id] = "done"
            return True

        if ntype == "llm.generate":
            self._exec_llm_generate(branch, node, ctx)
            bnodes[node_id] = "done"
            return True

        if ntype.startswith("human."):
            # Root orchestration branch usually has no concrete item after fanout.
            # In that case, do not create synthetic human tasks for main branch.
            if branch == self.root_branch and ctx.get("item") is None:
                out_key = str(node.get("out") or "human_result")
                ctx.setdefault(out_key, "")
                _save_context(self.run_id, branch, ctx)
                bnodes[node_id] = "done"
                return True
            task_id = f"{branch}:{node_id}"
            if task_id not in (self.state.get("inflight") or {}):
                self.state.setdefault("inflight", {})[task_id] = {
                    "branch": branch,
                    "node_id": node_id,
                    "out": str(node.get("out") or "human_result"),
                    "message": _render_value(node.get("message", ""), ctx, item),
                }
            bnodes[node_id] = "waiting_human"
            return True

        if ntype == "join":
            ready, value = self._join_rows(branch, node, ctx)
            if not ready:
                return False
            out_key = str(node.get("out") or "joined")
            ctx[out_key] = value
            _save_context(self.run_id, branch, ctx)
            bnodes[node_id] = "done"
            return True

        bnodes[node_id] = "failed"
        return True

    def _all_terminal(self) -> bool:
        branches = self.state.get("branches") or {}
        for bdata in branches.values():
            for st in ((bdata or {}).get("nodes") or {}).values():
                if str(st) in ("pending", "running"):
                    return False
                if str(st) == "waiting_human":
                    return False
        return True

    def tick(self) -> bool:
        with _LOCK:
            if self.state.get("finished"):
                return False

            changed = False
            while True:
                progressed = False
                branches = list((self.state.get("branches") or {}).keys())
                branches.sort(key=lambda b: (0 if b == self.root_branch else 1, b))

                for branch in branches:
                    bnodes = (self.state.get("branches", {}).get(branch, {}) or {}).get("nodes", {})
                    for node in self.nodes:
                        nid = node["id"]
                        st = str(bnodes.get(nid) or "pending")
                        if st in ("done", "failed", "waiting_human"):
                            continue
                        if not self._deps_satisfied(branch, node):
                            continue
                        if branch != self.root_branch and node.get("type") == "join":
                            bnodes[nid] = "done"
                            progressed = True
                            changed = True
                            break
                        if self._execute_node(branch, node):
                            progressed = True
                            changed = True
                            break
                    if progressed:
                        break

                if not progressed:
                    break

            if not (self.state.get("inflight") or {}) and self._all_terminal():
                self.state["finished"] = True

            save_state(self.run_id, self.state)
            return changed

    def on_human_completed(self, task_id: str, result: Dict[str, Any]) -> bool:
        with _LOCK:
            inflight = self.state.setdefault("inflight", {})
            task = inflight.pop(task_id, None)
            if not task:
                return False
            branch = str(task.get("branch") or self.root_branch)
            node_id = str(task.get("node_id") or "")
            out_key = str(task.get("out") or "human_result")
            ctx = load_context(self.run_id, branch)
            value = result.get("result") if isinstance(result, dict) and "result" in result else result
            ctx[out_key] = value
            _save_context(self.run_id, branch, ctx)
            branch_nodes = (
                self.state.get("branches", {}).get(branch, {}) or {}
            ).setdefault("nodes", {})
            if node_id:
                branch_nodes[node_id] = "done"
            save_state(self.run_id, self.state)
            return True


def run_loop(engine: DAGEngine, poll_interval: float = 0.1, poll_sec: Optional[float] = None) -> None:
    interval = float(poll_sec if poll_sec is not None else poll_interval)
    interval = max(0.001, interval)
    while True:
        engine.tick()
        if engine.state.get("finished"):
            return
        time.sleep(interval)
