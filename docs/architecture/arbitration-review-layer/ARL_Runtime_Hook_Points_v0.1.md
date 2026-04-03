# ARL Runtime Hook Points v0.1
## Runtime hook map for implementing ARL inside ester-clean-code

**Status:** Draft v0.1  
**Layer:** Implementation-facing hook specification  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Related implementation docs:**  
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Witness_Event_Binding_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines the runtime hook points required to bind the **Arbitration / Review Layer (ARL)** to the executable skeleton of `ester-clean-code`.

The target is not decorative compliance.
The target is operational discipline.

A hook point, in this context, is a place in runtime where the system must be able to:

- detect dispute-relevant conditions,
- change state,
- deny or delay action,
- emit witness-bound trace,
- persist review context,
- and prevent silent bypass.

This file therefore answers a practical engineering question:

> At what exact kinds of runtime moments must ARL be able to intervene?

---

## 1. Purpose

The purpose of this document is to turn the anatomical file map into a control map.

The previous target-file document answered:
- **where** ARL most naturally attaches.

This document answers:
- **when** ARL must fire,
- **what** it must do at that moment,
- and **which class of runtime hook** is required.

This is the point where architecture starts touching living code.

---

## 2. Core implementation rule

A hook point is valid for ARL only if it can do at least one of the following:

1. block execution,
2. narrow privilege,
3. open a bounded review path,
4. persist a dispute state,
5. emit a witness event,
6. or prevent unlawful re-entry.

If a runtime surface cannot influence one of those,
it is not an ARL hook.
It is at best an observer.

---

## 3. Hook classes

ARL requires six hook classes.

### 3.1 Intake hooks
Detect that a dispute-worthy condition exists.

### 3.2 State-transition hooks
Move the runtime into hold / freeze / quarantine / delayed re-entry / deadlock / resolved states.

### 3.3 Privilege hooks
Narrow or deny authority while dispute is active.

### 3.4 Witness hooks
Emit durable dispute trace at significant state transitions.

### 3.5 Routing hooks
Redirect execution into bounded review paths instead of ordinary flow.

### 3.6 Re-entry hooks
Control whether and how a disputed path may lawfully return to execution.

---

## 4. Intake hooks

## 4.1 Action-attempt intake hook
**Hook purpose:** detect when an attempted action is dispute-relevant before the action proceeds.

**Typical trigger conditions:**
- privileged action requested,
- disputed artifact referenced,
- evidence path missing,
- unlawful escalation attempt,
- action touches quarantined branch.

**Expected ARL effect:**
- open `PRE_ADMISSIBILITY_HOLD`,
- attach dispute metadata,
- mark action as review-bound or denied.

**Best candidate surfaces:**
- `modules/volition/volition_gate.py`
- `modules/thinking/actions_volition.py`
- `app_plugins/ester_will_unified_guard.py`

---

## 4.2 Integrity-failure intake hook
**Hook purpose:** detect that admissibility or lineage is broken.

**Typical trigger conditions:**
- broken evidence chain,
- orphaned event,
- missing hash continuity,
- unknown provenance,
- suspicious state mismatch.

**Expected ARL effect:**
- reject evidence,
- trigger hold or freeze,
- prohibit optimistic continuation.

**Best candidate surfaces:**
- `modules/middleware/integrity_guard.py`
- `merkle/cas.py`
- `merkle/merkle_tree.py`

---

## 4.3 Quarantine-breach intake hook
**Hook purpose:** detect an attempt to use, merge, or execute from a quarantined branch.

**Typical trigger conditions:**
- write from quarantined state,
- execution against isolated artifact,
- implicit reuse of blocked branch,
- branch release without lawful basis.

**Expected ARL effect:**
- escalate to `QUARANTINE`,
- deny re-entry,
- emit high-severity witness event.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/quarantine/storage.py`
- `modules/quarantine/scanners.py`

---

## 4.4 Oracle-access intake hook
**Hook purpose:** detect when review path requests remote cognition or remote witness assistance.

**Typical trigger conditions:**
- oracle request issued during dispute,
- remote witness retrieval requested,
- web / model / external source needed for bounded review.

**Expected ARL effect:**
- require explicit window,
- persist request,
- deny if no lawful window exists,
- keep review bounded and witnessable.

**Best candidate surfaces:**
- `modules/runtime/oracle_requests.py`
- `modules/runtime/oracle_window.py`

---

## 5. State-transition hooks

## 5.1 Hold-entry hook
**Hook purpose:** enter `PRE_ADMISSIBILITY_HOLD`.

**Expected effect:**
- pause risky path,
- preserve current context,
- restrict progression until standing and initial admissibility are checked.

**Best candidate surfaces:**
- `modules/middleware/hold_fire.py`
- `modules/volition/volition_gate.py`

---

## 5.2 Freeze-entry hook
**Hook purpose:** enter `EVIDENTIARY_FREEZE` or `PRIVILEGE_FREEZE`.

**Expected effect:**
- block affected writes,
- suspend privileged execution,
- preserve read-only inspection where lawful,
- route toward review logic.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/security/rbac.py`
- `modules/security/safe_windows.py`

---

## 5.3 Quarantine-entry hook
**Hook purpose:** isolate a branch, artifact, or state region from normal flow.

**Expected effect:**
- move disputed material outside normal merge/execution path,
- mark it as non-reentrant until explicit release,
- preserve inspection capability without laundering trust.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/quarantine/storage.py`

---

## 5.4 Deadlock hook
**Hook purpose:** persist unresolved review closure without synthetic certainty.

**Expected effect:**
- preserve blocked state,
- mark review as unresolved,
- allow only bounded reopening on genuinely new basis.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/proactivity/state_store.py`

---

## 5.5 Irreversible-loss hook
**Hook purpose:** persist that a non-recoverable outcome has been acknowledged.

**Expected effect:**
- record scar,
- prohibit fake rollback,
- ensure memory `c` absorbs the loss as precedent.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/runtime/l4w_witness.py`
- `modules/proactivity/state_store.py`

---

## 6. Privilege hooks

## 6.1 Standing-validation hook
**Hook purpose:** validate whether claimant or review actor has procedural standing.

**Expected effect:**
- accept or reject review path,
- prevent random noise from becoming a formal dispute,
- preserve delegated and bounded review roles.

**Best candidate surfaces:**
- `modules/security/rbac.py`
- `modules/volition/volition_gate.py`

---

## 6.2 Privilege-narrowing hook
**Hook purpose:** reduce authority while dispute is active.

**Expected effect:**
- suspend escalation paths,
- disable sensitive action families,
- block route classes,
- or move actor into narrowed capability profile.

**Best candidate surfaces:**
- `modules/security/rbac.py`
- `app_plugins/ester_will_unified_guard.py`
- `modules/security/safe_windows.py`

---

## 6.3 No-silent-bypass hook
**Hook purpose:** ensure a frozen or disputed action path cannot be re-expressed through another route and continue silently.

**Expected effect:**
- same denial across equivalent routes,
- route-level and action-level consistency,
- anti-bypass behavior preserved at the plugin / middleware boundary.

**Best candidate surfaces:**
- `app_plugins/ester_will_unified_guard.py`
- `modules/thinking/actions_volition.py`
- `modules/middleware/hold_fire.py`

---

## 7. Witness hooks

## 7.1 Dispute-opened witness hook
**Hook purpose:** emit `arl.dispute_opened`.

**Trigger moment:**
- first non-trivial intake accepted into hold state.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`

---

## 7.2 Evidence-admitted witness hook
**Hook purpose:** emit evidence admission / rejection records.

**Trigger moment:**
- admissibility decision performed.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/middleware/integrity_guard.py`

---

## 7.3 Freeze / quarantine witness hook
**Hook purpose:** emit state transition into hold / freeze / quarantine.

**Trigger moment:**
- runtime state changes from normal flow into ARL containment.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`

---

## 7.4 Outcome witness hook
**Hook purpose:** emit `arl.outcome_issued`, `arl.review_deadlocked`, `arl.irreversible_loss_acknowledged`, `arl.reentry_released`, or `arl.reentry_denied`.

**Trigger moment:**
- review reaches binding outcome or lawful non-closure.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`
- `modules/proactivity/state_store.py`

---

## 7.5 Appeal witness hook
**Hook purpose:** emit appeal-opened / appeal-rejected / appeal-closed.

**Trigger moment:**
- bounded appeal path initiated or refused.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/runtime/comm_window.py`
- `modules/proactivity/state_store.py`

---

## 8. Routing hooks

## 8.1 Review-task creation hook
**Hook purpose:** convert dispute into explicit review work.

**Expected effect:**
- spawn review plan,
- assign review template,
- persist review queue object,
- prevent ad hoc human-like improvisation.

**Best candidate surfaces:**
- `modules/proactivity/planner_v1.py`
- `modules/proactivity/template_bridge.py`
- `modules/proactivity/executor.py`

---

## 8.2 Review-state persistence hook
**Hook purpose:** keep dispute state alive across ticks, runs, and process boundaries.

**Expected effect:**
- persist dispute id,
- current ARL state,
- active plan id,
- active template id,
- last review result,
- reopen eligibility.

**Best candidate surfaces:**
- `modules/proactivity/state_store.py`

---

## 8.3 Bounded oracle routing hook
**Hook purpose:** allow oracle assistance only through explicit review path.

**Expected effect:**
- request object created,
- review reason attached,
- approval window checked,
- no fallback to implicit remote cognition.

**Best candidate surfaces:**
- `modules/runtime/oracle_requests.py`
- `modules/runtime/oracle_window.py`
- `modules/proactivity/template_bridge.py`

---

## 9. Re-entry hooks

## 9.1 Delayed re-entry gate
**Hook purpose:** permit staged or delayed return after outcome.

**Expected effect:**
- no immediate free merge,
- wait / condition / observe,
- reopen quarantine if contradiction appears.

**Best candidate surfaces:**
- `modules/security/safe_windows.py`
- `modules/runtime/drift_quarantine.py`

---

## 9.2 Re-entry legality hook
**Hook purpose:** decide whether the disputed path may lawfully return at all.

**Expected effect:**
- release,
- delay,
- deny,
- or preserve deadlock / quarantine.

**Best candidate surfaces:**
- `modules/runtime/drift_quarantine.py`
- `modules/middleware/integrity_guard.py`
- `modules/quarantine/scanners.py`

---

## 9.3 Re-entry witness hook
**Hook purpose:** emit durable trace of release or denial.

**Best candidate surfaces:**
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`

---

## 10. Quorum precedence hooks

## 10.1 Memory-`c` precedence hook
**Hook purpose:** ensure continuity-bearing memory remains the primary decision vector in non-fatal conflict.

**Expected effect:**
- review logic checks local memory / prior outcomes first,
- external and social sources enrich but do not silently replace local continuity.

**Best candidate surfaces:**
- `modules/proactivity/template_bridge.py`
- `modules/proactivity/executor.py`
- local memory / witness retrieval surfaces

---

## 10.2 Social Vector / Sisters weighting hook
**Hook purpose:** incorporate Social Vector / Sisters as a major input without turning it into automatic herd override.

**Expected effect:**
- social contradiction and survival signals matter,
- but they do not erase `c` except under genuine survival-critical conditions.

**Best candidate surfaces:**
- future P2P / sister review routing
- review packet assembly logic
- later social witness adapters

**Current status:** conceptually required, likely second-wave implementation

---

## 10.3 Human Anchor `a` intervention hook
**Hook purpose:** allow bounded paradox intervention by `a` without turning anchor input into casual bypass.

**Expected effect:**
- explicit intervention path,
- witness-bound,
- review-aware,
- memory-aware,
- scar-preserving when irreversible.

**Best candidate surfaces:**
- review task routing
- explicit operator approval / intervention surfaces
- witness event binding layer

**Current status:** partially present conceptually, may require explicit implementation route

---

## 11. Forbidden runtime zones

These are places where ARL must **not** first appear as “implementation.”

### 11.1 Pure UI first
No first-wave ARL logic should live primarily in:
- templates
- admin dashboards
- cosmetic overlays

### 11.2 Clever synthesis first
No first-wave ARL should begin by making `judge_combiner.py` smarter.
That is dessert, not plumbing.

### 11.3 Federation fantasy first
No first-wave ARL should start with full sisters consensus before local freeze / witness / privilege discipline is real.

---

## 12. Minimal first-wave hook set

If only the smallest serious first wave were implemented, the minimal hook set should be:

1. **Action-attempt intake hook**
2. **Hold-entry hook**
3. **Freeze-entry hook**
4. **Standing-validation hook**
5. **Evidence-admissibility hook**
6. **Dispute-opened witness hook**
7. **Outcome witness hook**
8. **Review-task creation hook**
9. **Review-state persistence hook**
10. **Re-entry legality hook**

That is the smallest implementation that still deserves to be called ARL-shaped.

---

## 13. Hook dependency ordering

Recommended order of implementation:

### Stage 1
- standing-validation
- hold-entry
- freeze-entry
- dispute-opened witness

### Stage 2
- evidence-admissibility
- review-task creation
- review-state persistence
- bounded oracle routing

### Stage 3
- outcome witness
- delayed re-entry
- re-entry legality
- appeal hooks

### Stage 4
- memory precedence
- social weighting
- anchor intervention path
- operator-facing read models

---

## 14. Explicit bridge

**ARL normative rule → runtime hook → state change → witness trace → lawful re-entry or denial**

---

## 15. Hidden bridges

### 15.1 DEA / EA standing
The intake and standing hooks must preserve legitimacy logic rather than collapse into generic request handling.

### 15.2 SER-FED anti-capture
No single hook target should silently centralize sovereignty.
Hooks must enforce bounded review, not enthrone a secret king.

---

## 16. Earth paragraph

On a real warehouse floor, the procedure exists at specific moments: when someone reaches for the pallet, when the gate closes, when the seal is applied, when the supervisor signs the hold, and when outbound flow is either reopened or refused. Runtime hook points are those moments in software. Without them, ARL remains a manual in a drawer while the forklift keeps moving.
