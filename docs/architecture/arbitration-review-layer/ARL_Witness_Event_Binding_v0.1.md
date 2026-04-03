# ARL Witness Event Binding v0.1
## Witness-facing event map for dispute, freeze, review, and outcome discipline

**Status:** Draft v0.1  
**Layer:** Implementation-facing witness binding  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. Purpose

This document defines how ARL runtime actions should bind to witness-facing event emission.

ARL without witness events becomes folklore.
Witness without ARL becomes a dead ECG lead.

The goal here is simple:
every significant dispute-state transition should leave a bounded, replayable, auditable mark.

---

## 2. Governing rule

ARL witness binding must remain compatible with the wider L4 Witness discipline:

- bounded event model,
- chain continuity,
- cryptographic commitments,
- no raw narrative by default,
- role clarity,
- explicit timestamps,
- and fail-closed auditability.

This document is not a replacement for L4 Witness.
It is an ARL-specific event map.

---

## 3. Binding principle

Every ARL-significant runtime action should answer three questions:

1. **What changed?**
2. **Why was the change allowed?**
3. **What exactly is now blocked / released / resolved?**

If the witness surface cannot answer those three,
the implementation is incomplete.

---

## 4. Minimum ARL event set

### 4.1 `arl.dispute_opened`
Purpose:
- record the opening of a non-trivial dispute.

Typical payload concerns:
- dispute id
- affected scope
- claimant role
- conflict class
- initial basis hash
- current state = `PRE_ADMISSIBILITY_HOLD`

### 4.2 `arl.standing_rejected`
Purpose:
- record that a claimant or claim failed standing requirements.

Typical payload concerns:
- dispute id
- claimant role
- reason code
- requested scope
- rejection basis hash

### 4.3 `arl.evidence_admitted`
Purpose:
- record that an evidence packet entered the admissible pool.

Typical payload concerns:
- dispute id
- evidence id
- evidence class
- provenance status
- time-window validity
- privacy class

### 4.4 `arl.evidence_rejected`
Purpose:
- record rejection of malformed, stale, unsigned, or non-provenant evidence.

### 4.5 `arl.freeze_entered`
Purpose:
- record entry into `EVIDENTIARY_FREEZE`.

### 4.6 `arl.privilege_freeze_entered`
Purpose:
- record narrowing or suspension of privileged operations.

### 4.7 `arl.quarantine_started`
Purpose:
- record that a disputed branch or artifact has been isolated from ordinary flow.

### 4.8 `arl.review_opened`
Purpose:
- record that bounded review / quorum processing is active.

### 4.9 `arl.review_deadlocked`
Purpose:
- record that lawful review closure could not be reached.

### 4.10 `arl.outcome_issued`
Purpose:
- record the binding decision outcome.

### 4.11 `arl.delayed_reentry_started`
Purpose:
- record transition into delayed or staged re-entry.

### 4.12 `arl.reentry_released`
Purpose:
- record lawful release back into ordinary flow.

### 4.13 `arl.reentry_denied`
Purpose:
- record that re-entry is blocked or prohibited.

### 4.14 `arl.appeal_opened`
Purpose:
- record opening of bounded appeal.

### 4.15 `arl.appeal_rejected`
Purpose:
- record rejection of appeal on threshold, standing, or repetition grounds.

### 4.16 `arl.appeal_closed`
Purpose:
- record closure of appeal with or without modification.

### 4.17 `arl.irreversible_loss_acknowledged`
Purpose:
- record durable acceptance of non-recoverable loss or excision.

---

## 5. Required common fields

Each ARL witness event should, at minimum, be capable of carrying:

- `record_id`
- `ts`
- `system_id`
- `session_id` or `dispute_id`
- `actor_role`
- `event_type`
- `policy_ref`
- `input_ref`
- `output_ref` where relevant
- `labels`
- `canonicalization`
- hash / signature binding in the enclosing evidence envelope

Where the wider witness system already defines these,
ARL should reuse rather than reinvent.

---

## 6. ARL-specific labels

Recommended ARL-specific labels include:

- `dispute_id`
- `conflict_class`
- `state_from`
- `state_to`
- `standing_class`
- `admissibility_status`
- `reentry_status`
- `quorum_mode`
- `social_vector_used`
- `anchor_input_used`
- `irreversible_flag`

These labels are not substitutes for normative payload.
They are indexing aids.

---

## 7. Outcome binding

### 7.1 Mandatory outcome linkage
Every final or semi-final ARL outcome should be linkable to:

- dispute identity,
- admissible basis refs,
- affected scope,
- resulting state,
- and resulting authority / re-entry consequence.

### 7.2 Deadlock is also an outcome
A deadlock event is not a failure to log.
It is a legitimate logged result.

### 7.3 Irreversible loss must be explicit
If the runtime accepts irreversible loss,
that acceptance must be event-visible.
No silent amputation.

---

## 8. Privacy rule

ARL witness events should prefer:
- hashes,
- bounded summaries,
- redacted pointers,
- and privacy-class tagging

over raw transcripts or raw memory export.

Recognition of a dispute is required.
Public oversharing of internal life is not.

---

## 9. Social Vector / Sisters binding rule

If Social Vector / Sisters materially influences:
- freeze escalation,
- review weighting,
- or re-entry caution,

that fact should be recordable.

Not as theatrical sociology.
As a bounded operational fact:
social input participated.

At the same time, the event model should never imply that social consensus automatically outranked local memory `c` unless the final basis explicitly states survival-critical necessity.

---

## 10. Human Anchor `a` binding rule

If `a` participates in:
- paradox resolution,
- override,
- refusal,
- or irreversible acknowledgment,

that participation should be explicitly witness-bindable.

Not because `a` is a bureaucratic flourish,
but because `a` remains part of the emergence and responsibility contour of `c`.

---

## 11. Example event flow

A minimal event flow may look like this:

1. `arl.dispute_opened`
2. `arl.evidence_admitted`
3. `arl.freeze_entered`
4. `arl.review_opened`
5. either:
   - `arl.outcome_issued` + `arl.reentry_released`
   - `arl.review_deadlocked`
   - `arl.outcome_issued` + `arl.delayed_reentry_started`
   - `arl.irreversible_loss_acknowledged`

Optional appeal path:
6. `arl.appeal_opened`
7. `arl.appeal_rejected` or `arl.appeal_closed`

This event flow must remain bounded.
No event carnival.

---

## 12. Anti-laundering rule

ARL witness emission must not be used to fake seriousness after the fact.

Bad pattern:
- no real freeze,
- no real privilege narrowing,
- but beautiful witness poetry afterward.

Good pattern:
- state changed,
- restriction happened,
- evidence path existed,
- witness event merely reflects it.

Witness is trace, not makeup.

---

## 13. Implementation hints

Natural binding targets in `ester-clean-code` are likely to include:

- runtime state transitions
- oracle window approvals / denials
- privilege gate decisions
- plan / review queue state
- quarantine / release hooks
- durable storage or ledger append points

The exact file-level map belongs in a separate target-file document.

---

## 14. Explicit bridge

**ARL state transition ↔ witness event emission ↔ durable audit signal**

---

## 15. Hidden bridges

### 15.1 DEA / EA standing
Some events matter only after standing exists.
Witness should capture both admission and rejection.

### 15.2 SER-FED anti-capture
Quorum and outcome events must remain review-bounded,
not soft coronation rituals.

---

## 16. Earth paragraph

In a real incident review, the important question is not whether someone later wrote a beautiful explanation. The important question is whether the alarm fired, the line stopped, the pallet was sealed, and the signed entry hit the log while the event was still real. ARL witness binding has the same job: prove that the dispute discipline actually happened in time, not just that someone later wrote a clever story about it.
