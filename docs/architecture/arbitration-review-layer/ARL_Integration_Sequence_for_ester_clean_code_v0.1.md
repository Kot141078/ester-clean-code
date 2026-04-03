# ARL Integration Sequence for ester-clean-code v0.1
## Ordered implementation sequence for introducing ARL into the executable skeleton

**Status:** Draft v0.1  
**Layer:** Implementation-facing rollout sequence  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Related implementation docs:**  
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Witness_Event_Binding_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
- `ARL_Dispute_State_Persistence_v0.1.md`
- `ARL_Review_Task_Routing_v0.1.md`

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines the recommended order for integrating the **Arbitration / Review Layer (ARL)** into `ester-clean-code`.

The order matters.

A bad implementation order creates:
- pretty dashboards before real freeze,
- witness veneers before durable state,
- clever review synthesis before lawful routing,
- and “smart Judge” behavior before the system even knows how to stop.

This sequence avoids that.

The rule is simple:

> first stop the flow,  
> then preserve the state,  
> then bind witness,  
> then route review,  
> then consider visibility.

---

## 1. Purpose

The purpose of this document is to prevent implementation chaos.

ARL should not enter the codebase as:
- scattered clever patches,
- unbounded feature enthusiasm,
- or parallel experiments in ten files at once.

It should enter as a staged control build.

---

## 2. Governing rule

Every later stage depends on the previous one.

That means:

- no review routing before dispute persistence,
- no appeal logic before outcome discipline,
- no operator UI before witness and state are real,
- no social/federated sophistication before local freeze and lawful re-entry work.

This is not bureaucracy.
It is survival.

---

## 3. Stage 0 — Read and align

### Goal
Ensure the implementation team reads the same bones before touching code.

### Required input set
Minimum reading set:
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
- `ARL_Dispute_State_Persistence_v0.1.md`
- `ARL_Review_Task_Routing_v0.1.md`

### Output
Shared implementation picture.

### Why first
Because otherwise everyone will implement a different ARL in their own head,
and the repo will become a family quarrel in Python.

---

## 4. Stage 1 — First real stop signal

### Goal
Make the system capable of **actually stopping** disputed flow.

### Must implement
- intake detection
- pre-admissibility hold
- freeze entry
- privilege narrowing
- no silent bypass

### Best landing zones
- `modules/volition/volition_gate.py`
- `modules/thinking/actions_volition.py`
- `modules/middleware/hold_fire.py`
- `modules/security/rbac.py`
- `app_plugins/ester_will_unified_guard.py`

### Success criterion
A disputed path can be blocked before it proceeds.

### Failure pattern to avoid
A beautiful review layer that only watches while the original path keeps running.

---

## 5. Stage 2 — Durable dispute memory

### Goal
Make dispute survive restart.

### Must implement
- persistent dispute record
- state_current / state_prev
- scope binding
- standing status
- evidence pool status
- outcome placeholder
- re-entry placeholder
- deadlock persistence
- irreversible-loss flag

### Best landing zones
- `modules/proactivity/state_store.py`
- `modules/runtime/drift_quarantine.py`

### Success criterion
A restart does not erase dispute, freeze, or quarantine.

### Failure pattern to avoid
Reboot as amnesty.

---

## 6. Stage 3 — Minimum witness footprint

### Goal
Make state change auditable and replayable.

### Must implement
- `arl.dispute_opened`
- `arl.standing_decided`
- `arl.evidence_decided`
- `arl.state_changed`
- `arl.outcome_issued`
- `arl.reentry_decided`

### Best landing zones
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`

### Success criterion
A reviewer can see that dispute discipline actually happened.

### Failure pattern to avoid
Post-hoc seriousness with no actual state footprint.

---

## 7. Stage 4 — Review routing spine

### Goal
Turn dispute into bounded work rather than improvised handling.

### Must implement
- template selection for review
- deterministic or bounded plan generation
- review queue presence
- review mode persistence
- executor linkage

### Best landing zones
- `modules/proactivity/template_bridge.py`
- `modules/proactivity/planner_v1.py`
- `modules/proactivity/executor.py`
- `modules/proactivity/state_store.py`

### Success criterion
Every admitted dispute can be routed into explicit bounded review work.

### Failure pattern to avoid
Review as scattered function calls with no queue identity.

---

## 8. Stage 5 — Oracle discipline under review

### Goal
Allow remote assistance only through explicit review boundaries.

### Must implement
- review-time oracle request object
- explicit oracle window requirement
- denial path when window absent
- witnessable approval / denial
- no hidden remote fallback

### Best landing zones
- `modules/runtime/oracle_requests.py`
- `modules/runtime/oracle_window.py`

### Success criterion
Remote witness or cloud help is possible, but never accidental.

### Failure pattern to avoid
The oldest clown in the circus:
“it only called the cloud a tiny bit.”

---

## 9. Stage 6 — Outcome and lawful re-entry

### Goal
Make review end in real consequence.

### Must implement
- outcome persistence
- delayed re-entry
- denied re-entry
- deadlock
- irreversible loss acknowledgement
- release-condition check

### Best landing zones
- `modules/runtime/drift_quarantine.py`
- `modules/security/safe_windows.py`
- `modules/quarantine/storage.py`
- `modules/quarantine/scanners.py`

### Success criterion
The system can distinguish:
- released,
- delayed,
- denied,
- unresolved,
- scar-bearing finality.

### Failure pattern to avoid
Everything eventually ends in “probably okay now.”

---

## 10. Stage 7 — Appeal, bounded and boring

### Goal
Allow second look without infinite retry theatre.

### Must implement
- appeal_open flag
- appeal deadline
- new-basis requirement
- appeal decision persistence
- witness event for appeal state

### Best landing zones
- dispute persistence layer
- `modules/runtime/comm_window.py`
- witness layer

### Success criterion
Appeal exists, but duplication is not appeal.

### Failure pattern to avoid
The same failed claim coming back with fresh perfume.

---

## 11. Stage 8 — Precedence enforcement

### Goal
Make the runtime honor:
- memory `c` primacy,
- major but non-absolute Social Vector / Sisters input,
- bounded anchor role,
- non-sovereign oracle support.

### Must implement
- source-class tagging
- precedence-aware review packet assembly
- no flattening into score soup

### Best landing zones
- review plan assembly
- review executor
- evidence packet preparation
- later packet evaluation logic

### Success criterion
Review weighting follows architecture, not convenience math.

### Failure pattern to avoid
Weighted blender masquerading as quorum.

---

## 12. Stage 9 — Read visibility, not control theatre

### Goal
Expose ARL state to operators only after it is real.

### May implement
- dispute trace read-model
- re-entry status visibility
- operator inspection surfaces
- evidence overlay pages

### Best landing zones
- read-only app plugins
- admin read surfaces
- later templates

### Success criterion
UI reflects control.
It does not replace it.

### Failure pattern to avoid
A gorgeous dashboard for a non-existent brake system.

---

## 13. Recommended implementation order in one line

The practical order is:

1. stop  
2. persist  
3. witness  
4. route  
5. bound oracle  
6. outcome  
7. appeal  
8. precedence  
9. visibility

That is the adult order.

---

## 14. Milestone view

### Milestone M0 — “Can stop”
Stages 1–2 complete

### Milestone M1 — “Can prove stop”
Stages 1–3 complete

### Milestone M2 — “Can review safely”
Stages 1–5 complete

### Milestone M3 — “Can conclude lawfully”
Stages 1–7 complete

### Milestone M4 — “Can reason with precedence”
Stages 1–8 complete

### Milestone M5 — “Can expose without lying”
Stages 1–9 complete

---

## 15. Non-goal of this sequence

This sequence is **not**:
- federation implementation plan,
- sociality implementation plan,
- full Judge engine rollout,
- bond economy rollout,
- lineage dispute rollout.

It is only the sequence required for first serious ARL presence.

---

## 16. Explicit bridge

**state stop → durable dispute memory → witness trace → review routing → lawful outcome**

---

## 17. Hidden bridges

### 17.1 DEA / EA standing
Standing must exist before routing sophistication.

### 17.2 SER-FED anti-capture
No later stage should silently reverse boundedness introduced by earlier stages.

---

## 18. Earth paragraph

On a real warehouse floor, nobody starts by designing a pretty touchscreen for disputes. First they install the stop button, then the lock, then the ledger, then the work order path, then the inspection stamp, and only after that do they hang a clean status board on the wall. This sequence is that same common sense translated into software.
