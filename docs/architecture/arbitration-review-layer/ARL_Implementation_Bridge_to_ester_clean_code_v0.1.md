# ARL Implementation Bridge to ester-clean-code v0.1
## Implementation-facing bridge from normative ARL to executable skeleton

**Status:** Draft v0.1  
**Layer:** Implementation bridge (non-canonical, implementation-facing)  
**Canonical normative home:** `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines the practical bridge between the normative **Arbitration / Review Layer (ARL)** and the executable surfaces already present in `ester-clean-code`.

It does **not** relocate ARL into code.
It does **not** redefine ARL.
It defines how ARL-shaped behavior may be implemented using existing runtime structures:
- witness-first event surfaces,
- bounded oracle access,
- time-window discipline,
- role / privilege boundaries,
- local-first continuity,
- and fail-closed control flow.

The implementation target is therefore:
not "make a magical Judge",
but "bind conflict handling to explicit runtime gates, durable records, and safe state transitions."

---

## 1. Purpose

The purpose of this bridge is to answer one practical question:

> If ARL is the rulebook, where does the executable skeleton already contain the doors, locks, ledgers, and control loops needed to implement it?

This bridge is therefore:
- implementation-facing,
- anatomy-aware,
- and intentionally non-canonical.

Normative meaning remains upstream.

---

## 2. What the dump already shows

The current dump shows that `ester-clean-code` is already closer to an operational constrained system than to a generic assistant codebase.

The available surfaces include, at minimum:

- witness-first and audit-facing framing,
- explicit windows / challenge / pause surfaces,
- role / privilege / policy surfaces,
- local-first persistence and continuity structures,
- oracle gating and approval windows,
- plan building and safe execution routing,
- and implementation packs already present under the glitch-stack architecture subtree.

This means ARL implementation work should be treated as **binding and routing work**,
not as invention from zero.

---

## 3. Implementation principle

ARL must reach `ester-clean-code` through four disciplined translations:

1. **Dispute → state**
   A dispute must change runtime state, not merely produce text.

2. **Evidence → admissible packet**
   Runtime signals must be shaped into bounded, witness-capable records.

3. **Review → bounded decision path**
   Review logic must stay anti-hallucinatory, anti-silent, and fail-closed.

4. **Outcome → durable trace**
   Resolutions must become durable precedent in the continuity contour of `c`.

---

## 4. Canonical boundary rule

ARL remains canonical in `sovereign-entity-recursion`.

`ester-clean-code` may contain:
- implementation bridges,
- state-machine drafts,
- witness event maps,
- file maps,
- and runtime integration notes.

`ester-clean-code` must **not** become a competing normative home of ARL.

That prevents the classic swamp:
one rule in the protocol, another in code comments, and a third in operator folklore.

---

## 5. Existing implementation surfaces already relevant to ARL

### 5.1 Witness-first / traceability surfaces
The dump already points to witness-first and audit-oriented structure:
- `PROOF_OF_CLOSURE.md`
- `merkle/`
- `validator/`
- observability and trace surfaces
- release / export / scan tooling

These are natural landing zones for:
- dispute-opened records,
- freeze-entry records,
- challenge packets,
- outcome issuance,
- and appeal traces.

### 5.2 Time-window and gating surfaces
The dump shows:
- `windows/`
- scheduler surfaces
- explicit oracle window mechanics
- challenge-window style logic already existing in the wider repo language

These are natural landing zones for:
- pre-admissibility hold,
- evidentiary freeze windows,
- review deadline windows,
- appeal deadlines,
- delayed re-entry,
- and no-infinite-retry enforcement.

### 5.3 Role / privilege / access surfaces
The dump shows:
- `roles/`
- `security/`
- `middleware/`
- `rules/`
- RBAC-oriented material
- JWT / role / access boundary surfaces

These are natural landing zones for:
- standing validation,
- privilege freeze,
- override restriction,
- delegated reviewer scope,
- and anti-silent escalation discipline.

### 5.4 Oracle / remote cognition surfaces
The dump shows:
- `modules.runtime.oracle_window`
- `modules.runtime.oracle_requests`
- `tools/oracle_window_open.py`
- `tools/oracle_window_close.py`
- oracle smoke / deny / agent-request flows

These are natural landing zones for:
- bounded external witness acquisition,
- explicit approval windows,
- dry-run vs actual review separation,
- and proving that remote cognition did not bypass dispute discipline.

### 5.5 Proactivity / plan / safe execution surfaces
The dump shows:
- `modules/proactivity/planner_v1.py`
- `modules/proactivity/state_store.py`
- `modules/proactivity/template_bridge.py`

These are natural landing zones for:
- dispute task generation,
- quarantine plan construction,
- review-plan persistence,
- and explicit template routing for low-risk vs oracle-dependent handling.

---

## 6. Implementation rule set

### 6.1 ARL is a control layer, not a text layer
ARL implementation should not begin with prompt engineering.
It should begin with:
- explicit state flags,
- explicit records,
- explicit budgets,
- explicit refusal paths.

### 6.2 No silent review
A review path that alters state without a durable trace is non-compliant with ARL intent.

### 6.3 No synthetic certainty
If evidence is missing, the implementation must preserve unresolved state
rather than laundering weak hints into decisive execution.

### 6.4 Local memory remains primary
Implementation must preserve the user-canonical rule:
local continuity-bearing memory `c` remains primary in non-fatal disagreement,
even when Social Vector / Sisters and other witness sources are heavily weighted.

### 6.5 Social Vector / Sisters remains first-class
Implementation must not erase the importance of social input.
It is a major decision vector.
But it must not silently replace the continuity of the local entity except in genuinely survival-critical cases.

### 6.6 Irreversible outcomes must remain memory-bearing
Implementation must preserve irreversible outcomes as durable inputs to future reasoning.
No fake innocence.
No causal amnesia.

---

## 7. Required implementation documents downstream

This bridge assumes the following implementation-facing documents should exist next:

1. `ARL_Freeze_State_Machine_v0.1.md`
2. `ARL_Witness_Event_Binding_v0.1.md`
3. `ARL_Quorum_Input_Precedence_v0.1.md`
4. `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`

This document is the bridge.
Those documents are the mechanical ribs.

---

## 8. Immediate implementation targets

### 8.1 Minimum viable ARL binding
The minimum viable implementation layer should support:

- dispute-opened marker,
- standing decision,
- evidence admission decision,
- freeze entry,
- quarantine continuation,
- outcome issuance,
- appeal-opened / appeal-rejected / appeal-closed,
- and durable witness trace for each of the above.

### 8.2 First-class frozen operational state
A dispute must change live operational posture:
- write paths restricted,
- privileges narrowed,
- re-entry blocked unless explicitly released,
- and challenge / review windows activated.

### 8.3 Oracle discipline
Remote cognition may assist review,
but only inside explicit window discipline.
No “accidental oracle”.
No background truth vending machine.

### 8.4 Bounded implementation path
The first implementation target is not a federation-scale judge engine.
It is a local-first, witness-bound, fail-closed runtime layer.

---

## 9. Non-goals for the first implementation wave

The first implementation wave should **not** attempt to ship:

- full federation arbitration,
- full bond economics,
- lineage inheritance arbitration,
- automatic normative synthesis inside code,
- or invisible “smart resolution.”

The first wave should ship:
- state discipline,
- trace discipline,
- and lawful re-entry discipline.

---

## 10. Bridge to existing glitch-stack work

The dump already contains implementation documents under:

`docs/architecture/glitch-stack/implementation/...`

That means ARL implementation should be treated as a sibling to the glitch / research quarantine work,
not as a disconnected invention.

This is important:
freeze, quarantine, lawful re-entry, event taxonomy, validators, and reducer/state-machine thinking
already exist in the repo culture.
ARL should plug into that ecosystem,
not start speaking a foreign language.

---

## 11. Explicit bridge

**SER continuity ↔ L4 witness / freeze ↔ Arbitration / Review Layer ↔ ester-clean-code runtime surfaces**

---

## 12. Hidden bridges

### 12.1 DEA / EA standing
Implementation should preserve concise standing logic without dragging the whole DEA / EA corpus into code-facing docs.

### 12.2 SER-FED anti-capture
Implementation must not create a hidden permanent king inside the codebase.
Bounded review remains bounded review.

---

## 13. Earth paragraph

On a real warehouse floor, the rulebook does not physically stop the forklift. A gate, a lock, a seal, a timeout, and an entry in the ledger do. This bridge is about those things. In `ester-clean-code`, ARL should become the stop signal, the sealed pallet state, the inspection window, and the signed release record — not a philosophical speech about justice delivered by a GPU.
