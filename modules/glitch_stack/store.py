"""Explicit-root persistence for Glitch Stack M1 sidecars."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .m1 import CanonicalEvent, GlitchNode, ResearchNode, to_record

SCHEMA = "ester.glitch_m1.store.v1"


class GlitchM1Store:
    """Persist Glitch M1 nodes/events below an explicit caller-provided root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "glitch_m1"
        self.glitch_nodes_dir = self.base_dir / "glitch_nodes"
        self.research_nodes_dir = self.base_dir / "research_nodes"
        self.events_path = self.base_dir / "events.jsonl"
        self.manifest_path = self.base_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.glitch_nodes_dir.mkdir(parents=True, exist_ok=True)
        self.research_nodes_dir.mkdir(parents=True, exist_ok=True)
        self.write_manifest()

    def write_manifest(self) -> Path:
        manifest = self.manifest()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, manifest)
        return self.manifest_path

    def manifest(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "runtime_glitch_nodes": str(self.glitch_nodes_dir),
            "research_nodes": str(self.research_nodes_dir),
            "events": str(self.events_path),
            "research_lane_separate": True,
            "runtime_memory_store": None,
        }

    def save_glitch_node(self, glitch: GlitchNode) -> Path:
        self.ensure_dirs()
        target = self.glitch_nodes_dir / f"{_safe_file_id(glitch.node_ref.id)}.json"
        _write_json(target, to_record(glitch))
        return target

    def save_research_node(self, research: ResearchNode) -> Path:
        self.ensure_dirs()
        target = self.research_nodes_dir / f"{_safe_file_id(research.node_ref.id)}.json"
        _write_json(target, to_record(research))
        return target

    def append_event(self, event: CanonicalEvent) -> Path:
        self.ensure_dirs()
        line = json.dumps(to_record(event), ensure_ascii=False, sort_keys=True)
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return self.events_path

    def append_events(self, events: Iterable[CanonicalEvent]) -> Path:
        self.ensure_dirs()
        with self.events_path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(to_record(event), ensure_ascii=False, sort_keys=True) + "\n")
        return self.events_path

    def load_events(self) -> list[dict[str, object]]:
        if not self.events_path.exists():
            return []
        rows: list[dict[str, object]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows


def persist_m1_bundle(
    store: GlitchM1Store,
    *,
    glitch: GlitchNode | None = None,
    research: ResearchNode | None = None,
    events: Iterable[CanonicalEvent] = (),
) -> dict[str, str | None]:
    """Persist a small M1 bundle without assuming any live runtime path."""

    glitch_path = store.save_glitch_node(glitch) if glitch is not None else None
    research_path = store.save_research_node(research) if research is not None else None
    events_path = store.append_events(events)
    return {
        "glitch_path": str(glitch_path) if glitch_path is not None else None,
        "research_path": str(research_path) if research_path is not None else None,
        "events_path": str(events_path),
        "manifest_path": str(store.manifest_path),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _safe_file_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "node"
