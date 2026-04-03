# ARL Freeze State Machine v0.1
## Operational state model for dispute containment and lawful re-entry

**Status:** Draft v0.1  
**Layer:** Implementation-facing state machine  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. Purpose

This document defines an implementation-facing state model for ARL-related freeze, hold, quarantine, review, and re-entry behavior.

It is not a legal theory.
It is a control diagram in prose.

Its purpose is simple:
when dispute happens, the runtime must know where it is allowed to move,
where it is forbidden to move,
and what evidence is required for state transition.

---

## 2. Core principle

A dispute is not a comment.
A dispute is a **state transition request**.

If the runtime continues behaving as if nothing happened,
there is no ARL implementation.
There is only decorative language.

---

## 3. State set

### 3.1 NORMAL
Default operating state.
No active ARL dispute currently blocks the affected path.

### 3.2 PRE_ADMISSIBILITY_HOLD
Temporary hold entered before full admissibility is decided.
Used when a claim appears non-trivial but has not yet cleared standing and evidence checks.

### 3.3 EVIDENTIARY_FREEZE
Entered when standing is present and evidence review is active.
The affected branch, memory path, or action path is frozen pending review.

### 3.4 PRIVILEGE_FREEZE
A narrower or stronger freeze focused on privilege-bearing operations.
Used when the dispute concerns access, escalation, action authority, or role misuse.

### 3.5 QUARANTINE
The disputed branch is isolated from normal execution flow.
Read visibility may remain available under policy.
Write / commit / re-entry remains blocked.

### 3.6 REVIEW_ACTIVE
Review quorum / bounded review path is active.
This state may coexist with evidentiary freeze or quarantine as the active review phase.

### 3.7 DELAYED_REENTRY
Review has ended but re-entry is time-delayed, conditional, or staged.

### 3.8 RESOLVED
Dispute is resolved and relevant restrictions are lifted or replaced with stable consequence.

### 3.9 DEADLOCKED
Review reached insufficient closure.
The system preserves unresolved discipline rather than inventing truth.

### 3.10 IRREVERSIBLE_LOSS_ACKNOWLEDGED
A loss or excision has been accepted as real and non-reversible.
The system moves forward with scar, not denial.

---

## 4. Transition logic

### 4.1 NORMAL → PRE_ADMISSIBILITY_HOLD
Trigger:
- non-trivial dispute signal,
- anomaly requiring review,
- challenge packet,
- identity / privilege / continuity suspicion.

Condition:
- enough basis to justify a stop,
- not yet enough basis to fully admit review.

### 4.2 PRE_ADMISSIBILITY_HOLD → EVIDENTIARY_FREEZE
Trigger:
- standing validated,
- initial evidence admitted,
- review basis sufficient to prevent normal execution.

### 4.3 PRE_ADMISSIBILITY_HOLD → NORMAL
Trigger:
- standing rejected,
- evidence malformed,
- claim clearly insufficient at intake.

### 4.4 EVIDENTIARY_FREEZE → PRIVILEGE_FREEZE
Trigger:
- conflict directly affects authority, role, execution permission, or escalation path.

### 4.5 EVIDENTIARY_FREEZE → QUARANTINE
Trigger:
- branch contamination risk,
- continuity fracture,
- unlawful re-entry suspicion,
- disputed output cannot safely rejoin normal flow.

### 4.6 QUARANTINE → REVIEW_ACTIVE
Trigger:
- review path formally opened,
- quorum / review node engaged,
- witness-bound evidence window active.

### 4.7 REVIEW_ACTIVE → RESOLVED
Trigger:
- sufficient admissible basis,
- lawful outcome issued,
- no further freeze needed for the disputed scope.

### 4.8 REVIEW_ACTIVE → DELAYED_REENTRY
Trigger:
- outcome permits eventual re-entry,
- but only after waiting period, staged conditions, or additional proof.

### 4.9 REVIEW_ACTIVE → DEADLOCKED
Trigger:
- insufficient basis,
- unresolved contradiction,
- review cannot lawfully manufacture certainty.

### 4.10 REVIEW_ACTIVE → IRREVERSIBLE_LOSS_ACKNOWLEDGED
Trigger:
- excision / non-recoverable damage / permanent rejection becomes the only lawful stable outcome.

### 4.11 DEADLOCKED → REVIEW_ACTIVE
Trigger:
- genuinely new admissible evidence,
- reopened challenge window under bounded conditions.

### 4.12 DEADLOCKED → IRREVERSIBLE_LOSS_ACKNOWLEDGED
Trigger:
- later basis proves that unresolved preservation is no longer lawful or survivable.

### 4.13 DELAYED_REENTRY → NORMAL
Trigger:
- waiting period completed,
- release conditions satisfied,
- no contradiction introduced during the delay window.

### 4.14 DELAYED_REENTRY → QUARANTINE
Trigger:
- release conditions fail,
- new contradiction appears,
- re-entry becomes unsafe or non-lawful.

---

## 5. State permissions

### 5.1 NORMAL
Allowed:
- ordinary execution
- ordinary planning
- bounded escalation under normal policy

Blocked:
- none beyond ordinary policy

### 5.2 PRE_ADMISSIBILITY_HOLD
Allowed:
- intake review
- standing checks
- minimal witness capture
- bounded read access

Blocked:
- irreversible affected-path execution
- silent privileged changes

### 5.3 EVIDENTIARY_FREEZE
Allowed:
- evidence ingestion
- witness binding
- read-only inspection
- bounded review operations

Blocked:
- affected-path writes
- authority expansion
- disputed branch re-entry

### 5.4 PRIVILEGE_FREEZE
Allowed:
- observation
- privilege audit
- challenge evaluation

Blocked:
- role expansion
- privileged execution
- override laundering

### 5.5 QUARANTINE
Allowed:
- inspection
- bounded comparison
- witness updates
- scar-aware analysis

Blocked:
- ordinary merge
- silent resurrection
- operational reuse of disputed branch as if clean

### 5.6 REVIEW_ACTIVE
Allowed:
- bounded quorum processing
- explicit review actions
- evidence weighting
- outcome preparation

Blocked:
- speculative synthesis outside admissible pool
- silent policy rewrite

### 5.7 DELAYED_REENTRY
Allowed:
- staged observation
- release countdown
- conditional proof collection

Blocked:
- immediate unrestricted return

### 5.8 DEADLOCKED
Allowed:
- preservation
- bounded reopen on new evidence
- continued quarantine if needed

Blocked:
- confidence laundering
- repeated re-argument with unchanged basis

### 5.9 IRREVERSIBLE_LOSS_ACKNOWLEDGED
Allowed:
- scar registration
- precedent writing
- future reasoning with acknowledged loss

Blocked:
- fake rollback
- narrative restoration of what no longer exists

---

## 6. Memory rule

All final or semi-final ARL states must be memory-bearing.

In particular:
- `DEADLOCKED`
- `DELAYED_REENTRY`
- `IRREVERSIBLE_LOSS_ACKNOWLEDGED`

must not be treated as disposable technical noise.

If the runtime survives a dispute,
the dispute belongs to the history of `c`.

---

## 7. Social Vector / Sisters rule

Social input may influence:
- review pressure,
- contradiction detection,
- contextual survival assessment,
- and decision caution.

But the state machine must preserve the user-canonical principle:

> Social Vector / Sisters is major input,
> but does not automatically override continuity-bearing local memory `c`
> unless non-compliance is genuinely survival-fatal for `c`.

This means the state machine may intensify hold or quarantine under social pressure,
but it must not silently erase the individuality of `c`.

---

## 8. Human Anchor `a` rule

`a` remains:
- part of the emergence condition of `c`,
- relevant to paradox resolution,
- and a legitimate source of bounded final intervention.

But this state model must not treat `a` as a casual bypass switch.

If `a` intervenes,
that intervention must still:
- be explicit,
- be witness-bound,
- and produce a durable state consequence.

---

## 9. Fail-closed rule

If a transition lacks lawful basis,
the state machine must remain in the safer blocking state.

That means:
- no silent re-entry,
- no “probably safe” merge,
- no probabilistic self-comfort posing as evidence.

Safer unresolved state is preferable to elegant corruption.

---

## 10. No-infinite-retry rule

The state machine must not permit endless cycling between:
- review,
- appeal,
- freeze,
- and reopen

without genuinely new basis.

State loops without new evidence are not resilience.
They are pathology.

---

## 11. Implementation hints

This state model suggests natural runtime hooks for:
- dispute flags
- branch lock flags
- write-disable flags
- privilege narrowing
- witness-event emission
- timeout enforcement
- release-condition evaluators
- deadlock persistence markers

The exact code path is downstream.
The state discipline must come first.

---

## 12. Explicit bridge

**ARL dispute discipline ↔ freeze/quarantine runtime state ↔ lawful re-entry control**

---

## 13. Hidden bridges

### 13.1 DEA / EA standing
State transitions should only begin once a claim has procedurally valid standing.

### 13.2 SER-FED anti-capture
Review-active state must not harden into permanent invisible sovereignty.

---

## 14. Earth paragraph

In a real warehouse, a disputed pallet is not “a topic under discussion.” It is physically moved aside, marked, locked from outbound flow, and only released under explicit authority. This state machine is that fork-lift choreography in software form: stop, isolate, inspect, decide, and only then reopen the gate.
