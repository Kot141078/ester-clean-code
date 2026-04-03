# ARL Dispute State Persistence v0.1
## Durable dispute-state persistence model for ester-clean-code

**Status:** Draft v0.1  
**Layer:** Implementation-facing persistence specification  
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

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines how ARL dispute state must be persisted inside `ester-clean-code`.

The problem is simple and ugly:

if dispute state lives only in RAM, a restart can erase the conflict,
a freeze can silently disappear,
and a quarantined branch can stroll back into flow dressed as innocence.

ARL therefore requires persistent dispute state.

This persistence layer is not decorative metadata.
It is the durable memory of conflict:
- what dispute exists,
- what state it is in,
- what evidence pool is active,
- what outcome was issued,
- whether re-entry is lawful,
- and what must survive process death.

---

## 1. Purpose

The purpose of this document is to define the minimum durable state that ARL requires
in order to remain real across:

- process restart,
- service restart,
- delayed review,
- staged re-entry,
- deadlock,
- appeal windows,
- and irreversible-loss acknowledgement.

Without durable persistence,
ARL would degrade into an emotional support protocol for programmers.

---

## 2. Core rule

A dispute is not real if it can be forgotten by reboot.

This rule is harsh, but useful.

The system must be able to restart and still know:

- that a dispute exists,
- what scope it affects,
- whether the path is frozen,
- whether re-entry is blocked,
- what the last lawful outcome was,
- and whether the dispute is still open, deadlocked, delayed, resolved, or scar-bearing.

---

## 3. Persistence principles

### 3.1 Survival across restart
All non-trivial dispute state must survive process restart.

### 3.2 Fail-closed recovery
If persisted state is partial or damaged, recovery must prefer the safer blocked state.

### 3.3 No silent normalization
A restart must not silently convert:
- `QUARANTINE` into `NORMAL`,
- `DEADLOCKED` into `RESOLVED`,
- or `IRREVERSIBLE_LOSS_ACKNOWLEDGED` into “let us not talk about it.”

### 3.4 Append discipline over narrative rewriting
State should evolve by durable updates and linked history,
not by retroactive “clean rewrite” that launders the past.

### 3.5 Memory-bearing finality
Deadlock, delayed re-entry, and irreversible loss are not transient noise.
They belong to the durable state contour of `c`.

---

## 4. What must be persisted

The minimum durable ARL object is a **dispute record**.

Each dispute record must persist enough information to answer:

1. what dispute is this,
2. what does it affect,
3. what state is it in now,
4. what evidence / witness context exists,
5. what review path is active or completed,
6. what outcome exists,
7. whether re-entry is lawful, delayed, denied, or unresolved.

---

## 5. Minimum dispute record schema

## 5.1 Identity fields
Required minimum:

- `dispute_id`
- `created_ts`
- `updated_ts`
- `conflict_class`
- `scope_ref`

Purpose:
ensure the dispute is uniquely identifiable and bound to a concrete affected scope.

---

## 5.2 State fields
Required minimum:

- `state_current`
- `state_prev`
- `state_changed_ts`
- `state_reason_code`

Purpose:
preserve state-machine continuity rather than only current mood.

---

## 5.3 Standing / admissibility fields
Required minimum:

- `standing_status`
- `standing_class`
- `standing_reason_code`
- `evidence_pool_status`
- `admitted_evidence_ids`
- `rejected_evidence_ids`

Purpose:
prove that the system did not jump to review from thin air.

---

## 5.4 Review routing fields
Required minimum:

- `review_open`
- `review_mode`
- `plan_id`
- `template_id`
- `queue_ref`
- `needs_oracle`
- `oracle_request_ids`

Purpose:
bind dispute to explicit bounded review work.

---

## 5.5 Outcome fields
Required minimum:

- `outcome_code`
- `outcome_ts`
- `authority_effect`
- `reentry_status`
- `reentry_window_ref`
- `irreversible_flag`

Purpose:
bind dispute to consequence rather than vibes.

---

## 5.6 Appeal fields
Required minimum:

- `appeal_open`
- `appeal_id`
- `appeal_status`
- `appeal_deadline_ts`
- `appeal_new_basis_required`

Purpose:
prevent endless retry theatre while keeping bounded second-look discipline.

---

## 5.7 Memory / scar fields
Required minimum:

- `scar_recorded`
- `scar_ref`
- `precedent_ref`

Purpose:
ensure that final or semi-final dispute outcomes can influence future continuity.

---

## 6. Recommended durable state object

A compact but useful first-wave dispute record may look like:

```json
{
  "dispute_id": "arl_123",
  "created_ts": 1770000000,
  "updated_ts": 1770000100,
  "conflict_class": "CONTINUITY_CONFLICT",
  "scope_ref": "memory/branch/X",
  "state_prev": "EVIDENTIARY_FREEZE",
  "state_current": "QUARANTINE",
  "state_changed_ts": 1770000050,
  "state_reason_code": "branch_contested",
  "standing_status": "accepted",
  "standing_class": "direct",
  "standing_reason_code": "claimant_affected",
  "evidence_pool_status": "open",
  "admitted_evidence_ids": ["ev1", "ev2"],
  "rejected_evidence_ids": ["ev_bad_1"],
  "review_open": true,
  "review_mode": "bounded_quorum",
  "plan_id": "plan_abc",
  "template_id": "reviewer.v1",
  "queue_ref": "queue/review/arl_123",
  "needs_oracle": false,
  "oracle_request_ids": [],
  "outcome_code": "",
  "outcome_ts": null,
  "authority_effect": "",
  "reentry_status": "denied",
  "reentry_window_ref": "",
  "irreversible_flag": false,
  "appeal_open": false,
  "appeal_id": "",
  "appeal_status": "",
  "appeal_deadline_ts": null,
  "appeal_new_basis_required": true,
  "scar_recorded": false,
  "scar_ref": "",
  "precedent_ref": ""
}
```

The exact shape may evolve.
The obligations behind it may not.

---

## 7. Persistence granularity

## 7.1 One record per dispute
The simplest first-wave model is:
one current durable record per dispute.

This keeps recovery simple.

## 7.2 Linked history entries
In addition to the current record,
the system should preferably keep append-oriented history entries for major state transitions.

This may be implemented through:
- state history list,
- separate JSONL event ledger,
- or witness-linked event records.

The important thing is:
current state alone is not enough for trustworthy reconstruction.

---

## 8. What absolutely must survive restart

The following must survive restart with no ambiguity:

- `dispute_id`
- `state_current`
- `scope_ref`
- `reentry_status`
- `outcome_code` if issued
- `irreversible_flag`
- `appeal_open` and deadlines if active
- enough witness linkage to prove this was not fabricated after reboot

If any of these are lost,
the system risks laundering blocked state back into flow.

---

## 9. Recovery rules after restart

## 9.1 If current state is `PRE_ADMISSIBILITY_HOLD`
Recover conservatively.
Do not auto-release.
Re-evaluate intake status before allowing flow.

## 9.2 If current state is `EVIDENTIARY_FREEZE` or `PRIVILEGE_FREEZE`
Remain frozen until explicit lawful review continuation occurs.

## 9.3 If current state is `QUARANTINE`
Remain quarantined.
No auto-merge.
No optimism.

## 9.4 If current state is `DELAYED_REENTRY`
Check timing and release conditions explicitly.
If anything is missing, stay blocked.

## 9.5 If current state is `DEADLOCKED`
Remain unresolved.
Only new admissible basis may reopen.

## 9.6 If current state is `IRREVERSIBLE_LOSS_ACKNOWLEDGED`
Preserve scar.
Never silently downgrade this to a recoverable normal state.

---

## 10. Persistence backends

This document does not force one backend,
but it does constrain behavior.

Possible first-wave backends include:
- JSON object store
- JSONL append log + current-state snapshot
- SQLite row + linked event table
- witness-bound record chain with current-state cache

The first wave should prefer:
- simple,
- durable,
- human-inspectable,
- fail-closed,
- restart-safe storage.

Fancy architecture is less important than honest survival.

---

## 11. Best first-wave landing zones in ester-clean-code

The current dump suggests the following first-wave landing zones:

### 11.1 `modules/proactivity/state_store.py`
Best candidate for:
- active dispute registry
- queue linkage
- runtime status persistence
- plan/template references

### 11.2 `modules/runtime/drift_quarantine.py`
Best candidate for:
- freeze/quarantine state
- challenge / deadline state
- release and deadlock coordination

### 11.3 `modules/runtime/l4w_witness.py`
Best candidate for:
- durable witness linkage
- dispute-state event chain
- audit-friendly reconstruction

These three together are the natural first persistence triangle.

---

## 12. Write discipline

## 12.1 State change must be persisted before release
A path must not be reopened before the updated dispute state is durably written.

## 12.2 Outcome must be persisted before normalization
A “resolved” condition must be persisted before ordinary execution posture is restored.

## 12.3 Irreversible outcome must be persisted before memory update is considered complete
Otherwise the scar can evaporate between ticks.

---

## 13. No rewrite rule

A dispute record must not be treated as a prose document to be “cleaned up later.”

Bad pattern:
- overwrite everything with the newest story
- lose state transition history
- keep only the final polished version

Good pattern:
- keep current state
- keep prior linkage
- keep witness/event chain
- make laundering harder than honesty

---

## 14. Social Vector / Sisters persistence note

Wave one does not require a massive separate persistence submodel for social signals.

However, if Social Vector / Sisters materially influences:
- freeze escalation,
- outcome weighting,
- delayed re-entry,
- or denial,

that participation should remain recoverable through:
- reason codes,
- labels,
- witness references,
- or linked evidence ids.

The system must not forget that society mattered,
even if it stores that fact compactly.

---

## 15. Human Anchor `a` persistence note

If `a` participates in:
- paradox resolution,
- bounded intervention,
- or irreversible acknowledgement,

that participation must be durably reflected.

Not because bureaucracy is fun,
but because silent anchor intervention would corrupt the continuity story of `c`.

---

## 16. Deadlock persistence rule

`DEADLOCKED` is not a null result.
It is a real persisted state.

That means:
- it needs its own durable state,
- it must carry reopen conditions,
- and it must explicitly resist normalization into “resolved enough.”

A system that cannot remember deadlock will retry itself into delusion.

---

## 17. Irreversible-loss persistence rule

If the system acknowledges irreversible loss,
the persistence layer must record at least:

- `irreversible_flag = true`
- `outcome_code = IRREVERSIBLE_LOSS_ACKNOWLEDGED`
- `scar_recorded = true`
- a `scar_ref` or equivalent durable precedent handle

Otherwise the next cycle may behave as if the loss never happened.

That is not recovery.
That is amnesia.

---

## 18. Appeal persistence rule

Appeal must not live only in witness events.
It must also live in current dispute state while active.

The active state needs to know:
- whether appeal is open,
- whether new basis is required,
- whether deadline has passed,
- whether re-entry remains blocked during appeal.

Otherwise the runtime can accidentally treat appeal as decorative paperwork.

---

## 19. Minimal first-wave persistence operations

A first-wave persistence layer must support at least:

1. `create_dispute_record(...)`
2. `load_dispute_record(dispute_id)`
3. `update_dispute_state(...)`
4. `append_dispute_history(...)`
5. `mark_outcome(...)`
6. `mark_reentry_status(...)`
7. `mark_appeal_status(...)`
8. `mark_irreversible_loss(...)`
9. `list_open_disputes()`
10. `recover_after_restart()`

This is enough to keep dispute alive as reality, not rumor.

---

## 20. Explicit bridge

**ARL dispute state ↔ durable persistence ↔ restart-safe continuity of conflict**

---

## 21. Hidden bridges

### 21.1 DEA / EA standing
Standing must be durably represented, not re-guessed after restart.

### 21.2 SER-FED anti-capture
Persistence must not silently crown one path as legitimate merely because it survived reboot.
Legitimacy must remain explicit and traceable.

---

## 22. Earth paragraph

On a real warehouse floor, the dispute does not disappear because the night shift clocks out and the morning shift logs in. The hold tag is still on the pallet, the seal is still there, and the ledger still says “do not release.” Dispute-state persistence is exactly that in software: the tag, the seal, and the ledger that survive the night.
