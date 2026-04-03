# ARL Minimal Event Types for ester-clean-code v0.1
## Minimal machine-facing event set for first-wave ARL implementation

**Status:** Draft v0.1  
**Layer:** Implementation-facing event pack  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Related implementation docs:**  
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Witness_Event_Binding_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines the **minimal event set** required to make the first implementation wave of the Arbitration / Review Layer (ARL) operational inside `ester-clean-code`.

The emphasis is deliberate:

- minimal,
- machine-facing,
- first-wave,
- and anti-theatrical.

A bad event pack tries to narrate everything.
A good event pack records only what the system must prove.

This document therefore defines the smallest event vocabulary that still allows ARL to be:
- stateful,
- reviewable,
- witness-bindable,
- fail-closed,
- and resistant to silent bypass.

---

## 1. Purpose

The purpose of this document is to keep first-wave ARL implementation from collapsing into two common mistakes:

1. **event starvation**  
   where the system changes state but nothing durable proves it;

2. **event carnival**  
   where every twitch becomes an event and the signal dies in its own exhaust fumes.

This pack aims for the narrow middle:
enough to prove discipline,
not enough to drown it.

---

## 2. Event design rule

A first-wave ARL event is justified only if it records one of the following:

- dispute intake,
- standing / admissibility decision,
- state transition,
- review routing,
- outcome issuance,
- appeal transition,
- or lawful / unlawful re-entry.

If an event does not serve one of those jobs,
it does not belong in the minimal pack.

---

## 3. Event naming rule

Recommended naming prefix:

`arl.`

Examples:
- `arl.dispute_opened`
- `arl.freeze_entered`
- `arl.outcome_issued`

This keeps the first-wave pack:
- isolated,
- grep-friendly,
- and visibly distinct from generic runtime chatter.

---

## 4. Minimal required event types

## 4.1 `arl.dispute_opened`
### Purpose
Record that a non-trivial dispute was admitted into ARL intake.

### Trigger
- dispute-worthy condition detected,
- claim or conflict passed enough threshold to open a hold,
- system now recognizes a formally tracked dispute.

### Required machine meaning
- a dispute id now exists,
- ordinary flow for the affected scope may no longer proceed unexamined.

### Minimal payload concerns
- `dispute_id`
- `conflict_class`
- `actor_role`
- `scope_ref`
- `state_to = PRE_ADMISSIBILITY_HOLD`
- `basis_ref`

---

## 4.2 `arl.standing_decided`
### Purpose
Record that standing was accepted or rejected.

### Trigger
- claimant / actor legitimacy evaluated,
- delegated reviewer scope checked,
- procedural right to continue determined.

### Required machine meaning
- review path may continue or must halt,
- random noise must not silently become formal dispute.

### Minimal payload concerns
- `dispute_id`
- `standing_class`
- `standing_result` (`accepted` / `rejected`)
- `reason_code`

---

## 4.3 `arl.evidence_decided`
### Purpose
Record evidence admission or rejection.

### Trigger
- evidence packet evaluated for admissibility,
- provenance / timing / continuity / integrity checked.

### Required machine meaning
- evidence pool changed,
- rejected evidence cannot silently influence outcome.

### Minimal payload concerns
- `dispute_id`
- `evidence_id`
- `evidence_class`
- `decision` (`admitted` / `rejected`)
- `reason_code`
- `provenance_status`
- `time_window_status`

---

## 4.4 `arl.state_changed`
### Purpose
Record a significant ARL state transition.

### Trigger
Any transition into or out of:
- `PRE_ADMISSIBILITY_HOLD`
- `EVIDENTIARY_FREEZE`
- `PRIVILEGE_FREEZE`
- `QUARANTINE`
- `REVIEW_ACTIVE`
- `DELAYED_REENTRY`
- `DEADLOCKED`
- `RESOLVED`
- `IRREVERSIBLE_LOSS_ACKNOWLEDGED`

### Required machine meaning
- ARL is not implicit,
- the state machine actually moved.

### Minimal payload concerns
- `dispute_id`
- `state_from`
- `state_to`
- `reason_code`
- `scope_ref`

---

## 4.5 `arl.review_routed`
### Purpose
Record that the dispute has been turned into an explicit review path.

### Trigger
- review task / plan / template selected,
- execution routed away from ordinary path into bounded review.

### Required machine meaning
- review is no longer oral folklore,
- it now exists as explicit bounded work.

### Minimal payload concerns
- `dispute_id`
- `plan_id`
- `template_id`
- `review_mode`
- `needs_oracle`
- `queue_ref`

---

## 4.6 `arl.oracle_review_decided`
### Purpose
Record that oracle-assisted review was requested, allowed, denied, or closed.

### Trigger
- external witness / oracle assistance requested during active review.

### Required machine meaning
- remote cognition did not occur by accident,
- and denial is as important as approval.

### Minimal payload concerns
- `dispute_id`
- `request_id`
- `decision` (`requested` / `approved` / `denied` / `closed`)
- `window_id`
- `reason_code`

---

## 4.7 `arl.outcome_issued`
### Purpose
Record the binding review outcome.

### Trigger
Review reaches a lawful result.

### Required machine meaning
A binding result now exists.
This is the moment that stops the system from floating in indefinite ambiguity.

### Minimal payload concerns
- `dispute_id`
- `outcome_code`
- `state_to`
- `reentry_status`
- `authority_effect`
- `irreversible_flag`

### Expected first-wave outcome codes
- `UPHELD`
- `REJECTED`
- `INSUFFICIENT_EVIDENCE`
- `REMAND_FOR_MORE_EVIDENCE`
- `QUARANTINE_CONTINUES`
- `ROLLBACK_AUTHORITY`
- `DELAYED_REENTRY`
- `NO_LAWFUL_EXECUTION_PATH`
- `IRREVERSIBLE_LOSS_ACKNOWLEDGED`

---

## 4.8 `arl.appeal_decided`
### Purpose
Record that an appeal was opened, rejected, or closed.

### Trigger
- appeal requested,
- threshold checked,
- appeal admitted or refused,
- appeal concluded.

### Required machine meaning
- no-infinite-retry discipline is enforceable,
- and re-argument without new basis is visible as refusal.

### Minimal payload concerns
- `dispute_id`
- `appeal_id`
- `decision` (`opened` / `rejected` / `closed`)
- `reason_code`
- `new_basis_present`

---

## 4.9 `arl.reentry_decided`
### Purpose
Record lawful release, delayed release, or denial of re-entry.

### Trigger
- disputed branch evaluated for return to ordinary flow.

### Required machine meaning
- the branch is either back in flow,
- waiting under explicit condition,
- or still blocked.

### Minimal payload concerns
- `dispute_id`
- `reentry_status` (`released` / `delayed` / `denied`)
- `release_window`
- `condition_ref`
- `reason_code`

---

## 5. Why this set is enough for wave one

This event set is sufficient to prove, at minimum:

1. a dispute was recognized,
2. standing was checked,
3. evidence was not silently laundered,
4. the state machine moved,
5. review became explicit work,
6. oracle assistance did not bypass policy,
7. an outcome exists,
8. appeal is bounded,
9. and re-entry did not happen by narrative wish.

That is already a real protocol footprint.

Anything more can come later.

---

## 6. What is intentionally excluded from the minimal pack

The following are intentionally left out of first-wave event vocabulary:

- high-resolution social vector analytics
- full DEA / EA packet mirroring
- detailed quorum sub-votes
- every internal scoring step
- every UI action
- every speculative intermediate thought
- every operator page view
- every benign read operation

These may be useful later.
They are not required to prove first-wave ARL discipline.

---

## 7. Recommended payload invariants

Every minimal ARL event should be able to carry, directly or indirectly:

- `record_id`
- `ts`
- `dispute_id`
- `event_type`
- `actor_role`
- `scope_ref`
- `policy_ref`
- `reason_code`
- `prev_hash` or chain linkage through enclosing witness layer
- optional privacy-aware references rather than raw payloads

The key is not luxurious metadata.
The key is stable linkage.

---

## 8. Event sequencing rule

The first-wave event pack should preserve a sane partial order.

A normal successful sequence may look like:

1. `arl.dispute_opened`
2. `arl.standing_decided`
3. `arl.evidence_decided`
4. `arl.state_changed`
5. `arl.review_routed`
6. optional `arl.oracle_review_decided`
7. `arl.outcome_issued`
8. optional `arl.appeal_decided`
9. `arl.reentry_decided`

This sequence does not have to be perfect every time.
But it must be impossible for the system to jump from “nothing happened”
to “released” without the middle discipline being visible somewhere.

---

## 9. Anti-laundering rule

A first-wave ARL event pack must not permit the following lie:

- no real standing check,
- no real freeze,
- no real review routing,
- but later a beautifully worded “outcome” appears.

The implementation should prefer fewer true events over many theatrical ones.

If a state did not change,
the event should not pretend that it did.

---

## 10. Social Vector / Sisters note

The minimal event pack does not need a dedicated social event in wave one.

However, if Social Vector / Sisters materially affects:
- outcome weighting,
- freeze escalation,
- or re-entry denial,

this influence should be representable through:
- `reason_code`
- `labels`
- or `policy_ref`

A future wave may split this into richer event classes.
The first wave only needs to avoid erasing it.

---

## 11. Human Anchor `a` note

The minimal event pack also does not need a separate anchor-only event family in wave one.

However, if `a` materially participates in:
- paradox resolution,
- irreversible acknowledgment,
- or explicit bounded intervention,

that participation should be visible inside:
- `actor_role`
- `reason_code`
- or structured labels

The key is:
no silent anchor override.

---

## 12. Machine-facing enum suggestions

### 12.1 Standing results
- `accepted`
- `rejected`

### 12.2 Evidence decisions
- `admitted`
- `rejected`

### 12.3 Oracle review decisions
- `requested`
- `approved`
- `denied`
- `closed`

### 12.4 Appeal decisions
- `opened`
- `rejected`
- `closed`

### 12.5 Re-entry statuses
- `released`
- `delayed`
- `denied`

These are intentionally compact.
Wave one is not a parliament.

---

## 13. Explicit bridge

**ARL machine discipline ↔ minimal event pack ↔ witness-bound first implementation**

---

## 14. Hidden bridges

### 14.1 DEA / EA standing
Standing stays structurally meaningful even if wave one keeps the event surface compact.

### 14.2 SER-FED anti-capture
Event minimalism also protects against silent power centers hiding behind unreadable event fog.

---

## 15. Earth paragraph

On a real warehouse floor, you do not need 93 different forms to prove that the pallet was disputed, the gate was closed, the seal was checked, the supervisor reviewed it, and outbound release was either signed or denied. You need just enough paperwork that the next shift can see exactly what happened and cannot quietly pretend otherwise. That is what this event pack is trying to be.
