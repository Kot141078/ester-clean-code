# Schema Pack v0.1

**Status:** Draft schema pack  
**Scope:** Canonical structural schemas for the first implementation layer of the new stack  
**Purpose:** Convert the object model into a schema-oriented contract suitable for future Pydantic models, JSON Schema generation, validator rules, and storage discipline

**Stack covered**
- `L4 Glitch Map`
- `ResearchNode / BackwardNode`
- `Witness Overlay / Evidence Notation`
- `Challenge / Review Protocol`
- `State Transition Matrix / Status Algebra`
- `Graph read projections`

---

## 1. Why this pack exists

`Object Model Draft Pack v0.1` defined:
- objects,
- enums,
- relations,
- invariants.

That was the typed spine.

This document adds the next necessary layer:

- field-level schema discipline,
- required vs optional fields,
- canonical data shapes,
- cross-object references,
- validation hooks,
- and storage-facing constraints.

This is still not implementation code.

But after this point, future implementation should no longer be allowed to say:
“we knew the concept, but we were vague about the structure.”

---

## 2. Schema principles

### 2.1 Runtime truth precedes projection
Schemas for graph/read objects must remain downstream of runtime/evidence/review truth.

### 2.2 Evidence never implies authority
No schema may encode a shortcut where:
`signed == executable`
or
`witnessed == legitimate`.

### 2.3 Research stays quarantined by schema
The schema itself must make unsafe collapse harder:
a `ResearchNode` cannot accidentally look like an executable runtime node.

### 2.4 Review preserves lineage
Review schemas must support reinterpretation without destructive overwrite.

### 2.5 Explicit beats clever
If a field matters for:
- safety,
- evidence,
- privilege,
- challengeability,
- expiry,
it should exist explicitly.

---

## 3. Canonical shared primitives

## 3.1 Scalar conventions

### `ID`
- type: `string`
- non-empty
- recommended pattern: lowercase prefix + `_` + stable unique token
- examples:
  - `glitch_01H...`
  - `research_01H...`
  - `chg_01H...`

### `UnixTs`
- type: `integer`
- minimum: `0`

### `Sha256Hex`
- type: `string`
- lowercase hex
- length: `64`

### `ShortCode`
- type: `string`
- non-empty
- machine-readable symbolic label
- examples:
  - `scope_missing`
  - `evidence_hash_mismatch`
  - `challenge_window_expired`

---

## 3.2 Common reusable schemas

### `NodeRef`

```json
{
  "type": "object",
  "required": ["node_id", "node_kind"],
  "properties": {
    "node_id": {"type": "string", "minLength": 1},
    "node_kind": {
      "type": "string",
      "enum": [
        "ExecutionNode",
        "GlitchNode",
        "ResearchNode",
        "BackwardNode",
        "WitnessNode",
        "ReviewNode",
        "GraphViewNode"
      ]
    }
  },
  "additionalProperties": false
}
```

---

### `EdgeRef`

```json
{
  "type": "object",
  "required": ["edge_id", "edge_kind"],
  "properties": {
    "edge_id": {"type": "string", "minLength": 1},
    "edge_kind": {
      "type": "string",
      "enum": [
        "execution_flow",
        "collision",
        "derives_research",
        "needs_evidence",
        "witness_binds",
        "challenge_opens",
        "review_resolves",
        "review_split",
        "cinematic_projects"
      ]
    }
  },
  "additionalProperties": false
}
```

---

### `WitnessRef`

```json
{
  "type": "object",
  "required": ["witness_id", "signing_class", "signed"],
  "properties": {
    "witness_id": {"type": "string", "minLength": 1},
    "signing_class": {"type": "string", "minLength": 1},
    "signed": {"type": "boolean"},
    "envelope_ref": {"type": ["string", "null"]}
  },
  "additionalProperties": false
}
```

---

### `TimeWindow`

```json
{
  "type": "object",
  "required": ["opened_ts", "deadline_ts", "kind", "is_open"],
  "properties": {
    "opened_ts": {"type": "integer", "minimum": 0},
    "deadline_ts": {"type": "integer", "minimum": 0},
    "kind": {"type": "string", "minLength": 1},
    "is_open": {"type": "boolean"}
  },
  "additionalProperties": false
}
```

Validation rule:
- `deadline_ts >= opened_ts`

---

## 4. Enum catalog

## 4.1 `Lane`

```json
{
  "type": "string",
  "enum": ["runtime", "research", "witness", "historical", "cinematic"]
}
```

## 4.2 `RuntimeLockType`

```json
{
  "type": "string",
  "enum": [
    "EnergyLock",
    "TimeLock",
    "ThermalLock",
    "PrivilegeLock",
    "VolitionLock",
    "IntegrityLock",
    "ConsentLock",
    "CautionLock",
    "EvidenceLock",
    "ContinuityLock",
    "MaintenanceLock",
    "EmbodimentLock",
    "TrustLock"
  ]
}
```

## 4.3 `EvidenceState`

```json
{
  "type": "string",
  "enum": [
    "asserted",
    "observed",
    "witnessed",
    "signed",
    "challenge_open",
    "settled",
    "expired",
    "cinematic_only"
  ]
}
```

## 4.4 `ChallengeStatus`

```json
{
  "type": "string",
  "enum": [
    "open",
    "queued",
    "under_review",
    "resolved_uphold",
    "resolved_modify",
    "resolved_split",
    "dismissed",
    "expired",
    "archived"
  ]
}
```

## 4.5 `ReviewOutcome`

```json
{
  "type": "string",
  "enum": [
    "annotate",
    "reclassify",
    "evidence_downgrade",
    "evidence_upgrade",
    "branch_split",
    "reopenability_change",
    "scope_restriction",
    "uphold"
  ]
}
```

## 4.6 `ReopenabilityState`

```json
{
  "type": "string",
  "enum": [
    "not_reopenable",
    "evidence_required",
    "review_required",
    "reopenable"
  ]
}
```

## 4.7 `RenderMode`

```json
{
  "type": "string",
  "enum": ["normal", "audit", "pedagogical"]
}
```

---

## 5. Core status schema

### `StatusTuple`

```json
{
  "type": "object",
  "required": [
    "lane",
    "active",
    "evidence_state",
    "expired",
    "executable",
    "render_mode_min"
  ],
  "properties": {
    "lane": {"$ref": "#/$defs/Lane"},
    "active": {"type": "boolean"},
    "evidence_state": {"$ref": "#/$defs/EvidenceState"},
    "challenge_status": {
      "oneOf": [
        {"$ref": "#/$defs/ChallengeStatus"},
        {"type": "null"}
      ]
    },
    "reopenability": {
      "oneOf": [
        {"$ref": "#/$defs/ReopenabilityState"},
        {"type": "null"}
      ]
    },
    "expired": {"type": "boolean"},
    "executable": {"type": "boolean"},
    "render_mode_min": {"$ref": "#/$defs/RenderMode"}
  },
  "additionalProperties": false
}
```

### Structural rules
1. `lane == "cinematic"` -> `executable == false`
2. `evidence_state == "cinematic_only"` -> `lane == "cinematic"`
3. `executable == true` -> `lane == "runtime"`
4. `reopenability != null` -> `lane in {"research", "historical"}`
5. `challenge_status != null` -> `evidence_state in {"challenge_open", "settled", "witnessed", "signed", "expired"}`

---

## 6. Runtime schemas

## 6.1 `ExecutionNode`

```json
{
  "type": "object",
  "required": [
    "node_id",
    "action_kind",
    "scope",
    "started_ts",
    "status",
    "metadata"
  ],
  "properties": {
    "node_id": {"type": "string", "minLength": 1},
    "action_kind": {"type": "string", "minLength": 1},
    "scope": {"type": "string", "minLength": 1},
    "started_ts": {"type": "integer", "minimum": 0},
    "ended_ts": {"type": ["integer", "null"], "minimum": 0},
    "actor_ref": {"type": ["string", "null"]},
    "status": {"$ref": "#/$defs/StatusTuple"},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `status.lane == "runtime"`
- `status.evidence_state != "cinematic_only"`

---

## 6.2 `GlitchNode`

```json
{
  "type": "object",
  "required": [
    "node_id",
    "source_execution_ref",
    "lock_type",
    "reason_code",
    "severity",
    "created_ts",
    "status",
    "added_caps",
    "removed_caps",
    "metadata"
  ],
  "properties": {
    "node_id": {"type": "string", "minLength": 1},
    "source_execution_ref": {"$ref": "#/$defs/NodeRef"},
    "lock_type": {"$ref": "#/$defs/RuntimeLockType"},
    "reason_code": {"type": "string", "minLength": 1},
    "severity": {"type": "string", "minLength": 1},
    "created_ts": {"type": "integer", "minimum": 0},
    "status": {"$ref": "#/$defs/StatusTuple"},
    "challenge_window": {
      "oneOf": [
        {"$ref": "#/$defs/TimeWindow"},
        {"type": "null"}
      ]
    },
    "witness_ref": {
      "oneOf": [
        {"$ref": "#/$defs/WitnessRef"},
        {"type": "null"}
      ]
    },
    "computed_hash": {"type": ["string", "null"]},
    "stored_hash": {"type": ["string", "null"]},
    "added_caps": {
      "type": "array",
      "items": {"type": "string"}
    },
    "removed_caps": {
      "type": "array",
      "items": {"type": "string"}
    },
    "rollback_reason": {"type": ["string", "null"]},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `source_execution_ref.node_kind == "ExecutionNode"`
- `status.lane == "runtime"`
- `status.executable == false`
- if `status.evidence_state in {"witnessed", "signed", "challenge_open", "settled"}` -> `witness_ref != null`
- if `status.challenge_status != null` -> `challenge_window != null`

---

## 7. Research schemas

## 7.1 `ResearchNode`

```json
{
  "type": "object",
  "required": [
    "node_id",
    "source_glitch_ref",
    "created_ts",
    "title",
    "summary",
    "missing_evidence",
    "required_resources",
    "reopenability",
    "status",
    "metadata"
  ],
  "properties": {
    "node_id": {"type": "string", "minLength": 1},
    "source_glitch_ref": {"$ref": "#/$defs/NodeRef"},
    "created_ts": {"type": "integer", "minimum": 0},
    "title": {"type": "string", "minLength": 1},
    "summary": {"type": "string", "minLength": 1},
    "missing_evidence": {
      "type": "array",
      "items": {"type": "string"}
    },
    "required_resources": {
      "type": "array",
      "items": {"type": "string"}
    },
    "reopenability": {"$ref": "#/$defs/ReopenabilityState"},
    "status": {"$ref": "#/$defs/StatusTuple"},
    "witness_ref": {
      "oneOf": [
        {"$ref": "#/$defs/WitnessRef"},
        {"type": "null"}
      ]
    },
    "challenge_ref": {"type": ["string", "null"]},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `source_glitch_ref.node_kind == "GlitchNode"`
- `status.lane == "research"`
- `status.executable == false`
- `status.reopenability != null`

---

## 7.2 `BackwardNode`

```json
{
  "type": "object",
  "required": [
    "node_id",
    "target_future_description",
    "source_research_ref",
    "gap_statement",
    "required_evidence",
    "bridge_assumptions",
    "status",
    "metadata"
  ],
  "properties": {
    "node_id": {"type": "string", "minLength": 1},
    "target_future_description": {"type": "string", "minLength": 1},
    "source_research_ref": {"$ref": "#/$defs/NodeRef"},
    "gap_statement": {"type": "string", "minLength": 1},
    "required_evidence": {
      "type": "array",
      "items": {"type": "string"}
    },
    "bridge_assumptions": {
      "type": "array",
      "items": {"type": "string"}
    },
    "status": {"$ref": "#/$defs/StatusTuple"},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `source_research_ref.node_kind == "ResearchNode"`
- `status.lane == "research"`
- `status.executable == false`

---

## 8. Evidence schemas

## 8.1 `EvidenceBadge`

```json
{
  "type": "object",
  "required": [
    "evidence_state",
    "signed",
    "challengeable",
    "expired",
    "display_hint"
  ],
  "properties": {
    "evidence_state": {"$ref": "#/$defs/EvidenceState"},
    "signed": {"type": "boolean"},
    "challengeable": {"type": "boolean"},
    "expired": {"type": "boolean"},
    "display_hint": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false
}
```

---

## 8.2 `EvidenceRecord`

```json
{
  "type": "object",
  "required": [
    "evidence_id",
    "target_ref",
    "evidence_state",
    "roles",
    "created_ts",
    "metadata"
  ],
  "properties": {
    "evidence_id": {"type": "string", "minLength": 1},
    "target_ref": {
      "oneOf": [
        {"$ref": "#/$defs/NodeRef"},
        {"$ref": "#/$defs/EdgeRef"}
      ]
    },
    "evidence_state": {"$ref": "#/$defs/EvidenceState"},
    "roles": {
      "type": "array",
      "items": {"type": "string"}
    },
    "created_ts": {"type": "integer", "minimum": 0},
    "signer": {"type": ["string", "null"]},
    "payload_hash": {"type": ["string", "null"]},
    "witness_ref": {
      "oneOf": [
        {"$ref": "#/$defs/WitnessRef"},
        {"type": "null"}
      ]
    },
    "expires_ts": {"type": ["integer", "null"], "minimum": 0},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `evidence_state == "signed"` -> `signer != null`
- `evidence_state in {"witnessed", "signed", "challenge_open", "settled"}` -> `witness_ref != null`
- `evidence_state == "cinematic_only"` -> target must belong to cinematic graph projection only

---

## 9. Review schemas

## 9.1 `ChallengeRecord`

```json
{
  "type": "object",
  "required": [
    "challenge_id",
    "target_ref",
    "opened_by_role",
    "opened_by_subject",
    "challenge_type",
    "reason",
    "opened_ts",
    "deadline_ts",
    "status",
    "new_evidence_refs",
    "metadata"
  ],
  "properties": {
    "challenge_id": {"type": "string", "minLength": 1},
    "target_ref": {
      "oneOf": [
        {"$ref": "#/$defs/NodeRef"},
        {"$ref": "#/$defs/EdgeRef"}
      ]
    },
    "opened_by_role": {"type": "string", "minLength": 1},
    "opened_by_subject": {"type": "string", "minLength": 1},
    "challenge_type": {"type": "string", "minLength": 1},
    "reason": {"type": "string", "minLength": 1},
    "opened_ts": {"type": "integer", "minimum": 0},
    "deadline_ts": {"type": "integer", "minimum": 0},
    "status": {"$ref": "#/$defs/ChallengeStatus"},
    "new_evidence_refs": {
      "type": "array",
      "items": {"type": "string"}
    },
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- `deadline_ts >= opened_ts`
- `status != "archived"` unless closed outcome exists in lineage

---

## 9.2 `ReviewRecord`

```json
{
  "type": "object",
  "required": [
    "review_id",
    "challenge_ref",
    "reviewer_role",
    "reviewer_subject",
    "outcome",
    "created_ts",
    "signed",
    "notes",
    "metadata"
  ],
  "properties": {
    "review_id": {"type": "string", "minLength": 1},
    "challenge_ref": {"type": "string", "minLength": 1},
    "reviewer_role": {"type": "string", "minLength": 1},
    "reviewer_subject": {"type": "string", "minLength": 1},
    "outcome": {"$ref": "#/$defs/ReviewOutcome"},
    "created_ts": {"type": "integer", "minimum": 0},
    "signed": {"type": "boolean"},
    "witness_ref": {
      "oneOf": [
        {"$ref": "#/$defs/WitnessRef"},
        {"type": "null"}
      ]
    },
    "previous_target_class": {"type": ["string", "null"]},
    "new_target_class": {"type": ["string", "null"]},
    "notes": {"type": "string"},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- if `outcome == "reclassify"` -> both class fields required
- if `signed == true` -> `witness_ref != null`
- if `outcome == "branch_split"` -> downstream split relation must exist in lineage layer

---

## 10. Guard schemas

## 10.1 `TransitionGuard`

```json
{
  "type": "object",
  "required": [
    "guard_id",
    "from_status",
    "to_status",
    "allowed",
    "rule_code",
    "reason"
  ],
  "properties": {
    "guard_id": {"type": "string", "minLength": 1},
    "from_status": {"$ref": "#/$defs/StatusTuple"},
    "to_status": {"$ref": "#/$defs/StatusTuple"},
    "allowed": {"type": "boolean"},
    "rule_code": {"type": "string", "minLength": 1},
    "reason": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false
}
```

### Forbidden transitions to encode later
- research -> executable
- cinematic_only -> signed
- challenge_open -> settled without review
- expired -> current without explicit revalidation
- signed -> legitimate via schema shortcut

---

## 10.2 `ReopenabilityGate`

```json
{
  "type": "object",
  "required": [
    "gate_id",
    "research_ref",
    "current_state",
    "required_evidence",
    "required_review",
    "allowed",
    "reason"
  ],
  "properties": {
    "gate_id": {"type": "string", "minLength": 1},
    "research_ref": {"$ref": "#/$defs/NodeRef"},
    "current_state": {"$ref": "#/$defs/ReopenabilityState"},
    "required_evidence": {
      "type": "array",
      "items": {"type": "string"}
    },
    "required_review": {"type": "boolean"},
    "allowed": {"type": "boolean"},
    "reason": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false
}
```

Validation rule:
- `research_ref.node_kind == "ResearchNode"`

---

## 11. Graph/read schemas

## 11.1 `GraphNodeView`

```json
{
  "type": "object",
  "required": [
    "node_ref",
    "lane",
    "title",
    "label",
    "badge",
    "render_mode_min",
    "visible",
    "metadata"
  ],
  "properties": {
    "node_ref": {"$ref": "#/$defs/NodeRef"},
    "lane": {"$ref": "#/$defs/Lane"},
    "title": {"type": "string", "minLength": 1},
    "label": {"type": "string", "minLength": 1},
    "badge": {"$ref": "#/$defs/EvidenceBadge"},
    "challenge_status": {
      "oneOf": [
        {"$ref": "#/$defs/ChallengeStatus"},
        {"type": "null"}
      ]
    },
    "render_mode_min": {"$ref": "#/$defs/RenderMode"},
    "visible": {"type": "boolean"},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

Validation rules:
- graph nodes are read projections only
- no `executable` field belongs here
- `lane == "cinematic"` allowed, but never implies runtime availability

---

## 11.2 `GraphEdgeView`

```json
{
  "type": "object",
  "required": [
    "edge_id",
    "edge_kind",
    "source_ref",
    "target_ref",
    "visible",
    "metadata"
  ],
  "properties": {
    "edge_id": {"type": "string", "minLength": 1},
    "edge_kind": {
      "type": "string",
      "enum": [
        "execution_flow",
        "collision",
        "derives_research",
        "needs_evidence",
        "witness_binds",
        "challenge_opens",
        "review_resolves",
        "review_split",
        "cinematic_projects"
      ]
    },
    "source_ref": {"$ref": "#/$defs/NodeRef"},
    "target_ref": {"$ref": "#/$defs/NodeRef"},
    "badge": {
      "oneOf": [
        {"$ref": "#/$defs/EvidenceBadge"},
        {"type": "null"}
      ]
    },
    "visible": {"type": "boolean"},
    "metadata": {"type": "object"}
  },
  "additionalProperties": false
}
```

---

## 11.3 `GraphSlice`

```json
{
  "type": "object",
  "required": [
    "slice_id",
    "mode",
    "nodes",
    "edges",
    "generated_ts"
  ],
  "properties": {
    "slice_id": {"type": "string", "minLength": 1},
    "mode": {"$ref": "#/$defs/RenderMode"},
    "nodes": {
      "type": "array",
      "items": {"$ref": "#/$defs/GraphNodeView"}
    },
    "edges": {
      "type": "array",
      "items": {"$ref": "#/$defs/GraphEdgeView"}
    },
    "generated_ts": {"type": "integer", "minimum": 0},
    "integrity_root": {"type": ["string", "null"]}
  },
  "additionalProperties": false
}
```

Validation rule:
- `integrity_root` summarizes lineage only; it cannot replace underlying evidence objects

---

## 12. Cross-object reference rules

### 12.1 Runtime chain
- `ExecutionNode` may lead to `GlitchNode`
- `GlitchNode` may lead to `ResearchNode`
- `ResearchNode` may lead to `BackwardNode`

### 12.2 Evidence chain
- any non-cinematic node may have `EvidenceRecord`
- `EvidenceRecord` may carry `WitnessRef`

### 12.3 Review chain
- `ChallengeRecord` targets `NodeRef` or `EdgeRef`
- `ReviewRecord` targets `ChallengeRecord`
- `ReviewRecord` may induce reclassification or split

### 12.4 Graph chain
- `GraphNodeView` and `GraphEdgeView` never become authoritative runtime objects
- they are projections over already existing typed objects

---

## 13. Minimal storage guidance

This pack does not force one storage backend.
But it suggests a future separation like:

- runtime truth -> runtime state / quarantine state / logs
- research truth -> dedicated research memory lane
- evidence truth -> witness/envelope/integrity storage
- graph projections -> derived read cache only

Never store all of these as one flat blob if they need different trust semantics.

---

## 14. Validation layers

### 14.1 Schema validation
- field existence
- enum membership
- nullability discipline

### 14.2 Semantic validation
- cross-object kind checks
- status/lane consistency
- review outcome consistency
- challenge deadline consistency

### 14.3 Transition validation
- legal status transitions only
- forbidden collapse detection

### 14.4 Integrity validation
- payload hash checks
- witness envelope references
- Merkle / content-address lineage where used

---

## 15. JSON Schema bundle shape

A future machine bundle may look like:

```json
{
  "$id": "ester.schema_pack.v0.1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Lane": {},
    "RuntimeLockType": {},
    "EvidenceState": {},
    "ChallengeStatus": {},
    "ReviewOutcome": {},
    "ReopenabilityState": {},
    "RenderMode": {},
    "NodeRef": {},
    "EdgeRef": {},
    "WitnessRef": {},
    "TimeWindow": {},
    "StatusTuple": {},
    "ExecutionNode": {},
    "GlitchNode": {},
    "ResearchNode": {},
    "BackwardNode": {},
    "EvidenceBadge": {},
    "EvidenceRecord": {},
    "ChallengeRecord": {},
    "ReviewRecord": {},
    "TransitionGuard": {},
    "ReopenabilityGate": {},
    "GraphNodeView": {},
    "GraphEdgeView": {},
    "GraphSlice": {}
  }
}
```

---

## 16. Recommended implementation order

1. publish enum schemas
2. publish shared primitive schemas
3. publish `StatusTuple`
4. publish runtime schemas
5. publish research schemas
6. publish evidence schemas
7. publish review schemas
8. publish guard schemas
9. publish graph schemas
10. add semantic validator pack
11. add transition legality pack
12. only then attach render/export tools

---

## 17. Explicit bridge

This schema pack makes the bridge sharper:

**the object model now has structural contracts, so the next implementation phase can no longer hide crucial distinctions between runtime truth, research quarantine, evidence standing, review lineage, and graph projection inside informal code.**

That is the explicit bridge between:
- concept,
- object typing,
- and future validator-backed implementation.

---

## 18. Hidden bridges

### Hidden Bridge 1 — Cybernetics
Schema discipline preserves regulator variety by preventing unsafe collapse of distinct feedback objects into one blurred state blob.

### Hidden Bridge 2 — Information Theory
Field-level structure reduces ambiguity and protects signal lineage better than narrative metadata sprawl.

---

## 19. Earth paragraph

In a real engineering system, the fault code, the maintenance ticket, the signed inspection, the override window, and the dashboard icon may all refer to the same incident — but they are not stored in the same shape for a reason. If you blur them into one universal object, the first post-mortem turns into a religious argument. Good schemas stop that before the metal gets warm.

---

## 20. Final position

`Schema Pack v0.1` is the first structural contract layer for the new stack.

It still does not execute.

But it does something almost as important:

it removes the excuse for future ambiguity.
