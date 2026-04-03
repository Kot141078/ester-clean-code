# ARL Review Task Routing v0.1
## Review-task routing model for dispute handling inside ester-clean-code

**Status:** Draft v0.1  
**Layer:** Implementation-facing routing specification  
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

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines how a recognized ARL dispute should be converted into bounded review work inside `ester-clean-code`.

The key implementation problem is not merely:
“how do we store the dispute?”

The real problem is:
**how do we route the dispute into explicit, finite, reviewable work
without falling into improvisation, retry-circus, or silent bypass?**

This document therefore defines:
- intake-to-review conversion,
- planner / template / executor routing,
- queue discipline,
- oracle-assisted review boundaries,
- and the refusal rules that prevent review from becoming disguised ordinary execution.

---

## 1. Purpose

The purpose of this document is to answer one practical engineering question:

> Once ARL recognizes a real dispute, how should the runtime route it into actual review work?

Without routing discipline, the runtime has only bad choices:
- do nothing,
- let the original path continue,
- or let some clever agent improvise a “solution.”

ARL requires none of those.
It requires explicit review routing.

---

## 2. Core rule

A dispute must not be handled as a side effect.

It must become:
- a bounded review task,
- in a known queue,
- with a known template,
- under known budgets,
- with known state consequences.

If review is not routable,
it is not operational.

---

## 3. Routing principle

Review-task routing must preserve five things at once:

1. **fail-closed intake**
2. **explicit template choice**
3. **explicit queue presence**
4. **bounded execution budgets**
5. **durable relation to dispute state**

This is the opposite of:
“let the smartest module take a swing.”

---

## 4. Trigger for routing

A review task should be routable only after the following threshold is crossed:

- a dispute id exists,
- standing is accepted or at least not yet rejected,
- the runtime has entered hold/freeze/quarantine posture,
- and the affected scope is no longer allowed to proceed normally.

Before that point, the system may still be in intake discipline.

After that point, explicit review work becomes mandatory.

---

## 5. Routing stages

## 5.1 Intake stage
At this stage the system decides:
- whether the signal is a real dispute,
- whether standing exists,
- whether the path must stop.

Outputs of this stage:
- dispute id
- initial state
- conflict class
- basic scope
- admissibility needed yes/no

This stage should **not** yet pretend to know the final answer.

---

## 5.2 Review-shaping stage
At this stage the system decides:
- what kind of review is needed,
- whether it is local-only,
- whether it needs bounded oracle assistance,
- whether the review is evidence-heavy, privilege-heavy, continuity-heavy, or quarantine-heavy.

Outputs of this stage:
- template id
- review mode
- initial plan skeleton
- queue destination
- oracle necessity flag

---

## 5.3 Review-execution stage
At this stage the system runs bounded review work:
- collect / validate evidence
- compare continuity and witness traces
- consult allowed sources
- update dispute state
- emit witness events
- issue outcome or deadlock

This stage is where review becomes real work rather than legal poetry.

---

## 5.4 Outcome / re-entry stage
At this stage the system decides:
- release
- delay
- continue quarantine
- deadlock
- irreversible loss
- appeal eligibility

This stage must remain linked to the same dispute id and the same persistence object.

---

## 6. Best first-wave routing surfaces in ester-clean-code

The dump strongly suggests the following first-wave routing surfaces.

### 6.1 `modules/proactivity/template_bridge.py`
Primary candidate for deterministic dispute → template selection.

### 6.2 `modules/proactivity/planner_v1.py`
Primary candidate for deterministic minimal review plan generation.

### 6.3 `modules/proactivity/executor.py`
Primary candidate for queue-bound execution of review work.

### 6.4 `modules/proactivity/state_store.py`
Primary candidate for queue-state and runtime-state persistence.

### 6.5 `modules/runtime/oracle_requests.py`
Primary candidate for explicit remote-review request objects.

### 6.6 `modules/runtime/oracle_window.py`
Primary candidate for bounded external review windowing.

These together already look like a real routing spine.

---

## 7. Routing decisions

## 7.1 Dispute class → review mode
Recommended first-wave review modes:

- `local_evidence_review`
- `local_privilege_review`
- `local_continuity_review`
- `quarantine_release_review`
- `oracle_assisted_review`

The first wave should prefer local modes whenever lawful and sufficient.

---

## 7.2 Dispute class → template selection
Recommended first-wave mapping:

### `IDENTITY_CONFLICT`
Default template:
- `reviewer.v1`

### `PRIVILEGE_CONFLICT`
Default template:
- `reviewer.v1`

### `EVIDENCE_CONFLICT`
Default template:
- `reviewer.v1`

### `CONTINUITY_CONFLICT`
Default template:
- `reviewer.v1` or a dedicated continuity-review template later

### `QUARANTINE_BREACH_CONFLICT`
Default template:
- `planner.v1` for deterministic containment steps,
- then `reviewer.v1` for bounded review

### `VISIBILITY_AUTHORITY_CONFLICT`
Default template:
- `reviewer.v1`

### `LINEAGE_CONFLICT`
Default template:
- local review first,
- oracle-assisted only if bounded justification exists

The exact template names may evolve.
The routing discipline should not.

---

## 8. Deterministic first-wave plan shape

A first-wave ARL review plan should remain compact and deterministic.

Typical step families:

1. persist dispute intake marker
2. verify state / freeze context
3. gather admissible evidence refs
4. validate evidence integrity
5. compare continuity / memory / witness references
6. optionally request bounded oracle window
7. compute bounded review result
8. persist outcome
9. emit witness events
10. update re-entry status

That is enough.
Anything much fancier at wave one is vanity.

---

## 9. Queue discipline

## 9.1 Review tasks must enter queue
A review task must have a queue presence,
not only an in-memory function call.

This matters because disputes may outlive the current tick.

## 9.2 Review tasks must remain identifiable
Queue entry must stay linked to:
- `dispute_id`
- `plan_id`
- `template_id`
- `review_mode`
- `scope_ref`

## 9.3 Review queue must not collapse into ordinary initiative traffic
Even if the same executor infrastructure is reused,
review tasks should remain distinguishable from:
- ordinary proactivity
- ordinary suggestions
- ordinary content work

A dispute is not just another todo item.

---

## 10. Budget discipline

## 10.1 Time budget
Each review task must carry a bounded time window.

## 10.2 Action budget
Each review task must carry bounded action count or bounded review step count.

## 10.3 Oracle budget
If oracle is allowed:
- explicit request id
- explicit window
- explicit token / call budget
- no implicit fallback

## 10.4 Retry budget
Review tasks must not requeue forever.

The queue must not become a laundromat for uncertainty.

---

## 11. Oracle-assisted review routing

## 11.1 When oracle review is allowed
Oracle-assisted review should be allowed only when:

- local evidence is insufficient,
- the need is explicit,
- the dispute state remains frozen,
- and a lawful review window exists.

## 11.2 What oracle review may do
Oracle-assisted review may:
- provide bounded comparison
- assist external witness retrieval
- enrich a contradiction check
- help analyze a bounded packet

## 11.3 What oracle review may not do
Oracle-assisted review may not:
- silently replace local continuity
- reopen flow on its own
- issue sovereign finality by itself
- bypass freeze / re-entry discipline

That would not be review.
That would be quiet surrender.

---

## 12. Routing outcomes

At minimum, a routed review task must end in one of the following machine-meaningful results:

- outcome issued
- more evidence needed
- deadlock
- delayed re-entry
- no lawful execution path
- irreversible loss acknowledged

“Still thinking” is not a final routing outcome.

---

## 13. Reopen rule

If review ends without closure,
the queue discipline must enforce:

- no immediate blind relaunch,
- no duplicate equivalent review task,
- no new routing without genuinely new basis.

This should be encoded as a routing refusal rule,
not left to operator mood.

---

## 14. Social Vector / Sisters routing note

Wave one does not require a full separate distributed routing layer for Sisters.

However, routing must remain compatible with later extension where:
- social input may be requested as bounded evidence,
- sister-node contradiction may strengthen freeze,
- and survival-critical disagreement may alter weighting.

This means the routing object should leave room for:
- `social_input_requested`
- `social_input_refs`
- `social_weight_used`

The first wave may leave them empty.
It should not make them impossible.

---

## 15. Human Anchor `a` routing note

Likewise, wave one does not require a giant dedicated anchor-routing subsystem.

But if `a` is invoked in paradox resolution,
the routing model should support:
- explicit intervention task or event
- anchor participation marker
- witness-bound result

The point is simple:
anchor intervention must be routeable,
not mythical.

---

## 16. Recommended first-wave routing record

A compact review-routing record may include:

- `dispute_id`
- `review_mode`
- `template_id`
- `plan_id`
- `queue_ref`
- `needs_oracle`
- `oracle_request_id`
- `scope_ref`
- `budget_ref`
- `status`
- `last_step`
- `last_error`
- `reopen_allowed`
- `new_basis_required`

This can live either:
- inside dispute persistence,
- inside queue state,
- or in both with clear ownership.

---

## 17. What must never happen

The following routing failures must be treated as implementation bugs:

### 17.1 Silent ordinary execution
The dispute exists, but the original action path continues as if nothing happened.

### 17.2 Review without queue identity
The review “ran somewhere,” but no durable queue / plan / routing object exists.

### 17.3 Oracle without explicit routing
The review path touched remote cognition without explicit request + window + budget.

### 17.4 Deadlock without persistent routing status
The system reached unresolved state, but nothing durable says review is blocked.

### 17.5 Appeal by duplication
Instead of bounded appeal, the system just enqueues the same review again with cosmetic wording changes.

---

## 18. Minimal first-wave routing algorithm

A simple first-wave algorithm may be:

1. dispute opened
2. standing checked
3. if rejected → stop
4. state enters hold/freeze
5. template selected deterministically
6. review plan generated deterministically
7. review task persisted to queue
8. executor runs bounded review
9. if oracle needed → explicit request + explicit window
10. evidence and continuity evaluated
11. outcome persisted
12. witness events emitted
13. re-entry status updated
14. reopen only on new basis

That is already a serious system.

---

## 19. Explicit bridge

**dispute intake ↔ template / planner / executor routing ↔ bounded review work ↔ lawful outcome**

---

## 20. Hidden bridges

### 20.1 DEA / EA standing
Routing begins only after procedural legitimacy exists.
That keeps review from turning into ambient noise processing.

### 20.2 SER-FED anti-capture
Routing must not silently crown one executor, one oracle path, or one queue as the new sovereign center.
Bounded review remains bounded review.

---

## 21. Earth paragraph

On a real warehouse floor, once a pallet is disputed, someone does not just “think about it harder.” The pallet gets tagged, a work order is opened, the right supervisor gets assigned, outside inspection is requested only if needed, and the release decision returns through the same documented path. Review-task routing is exactly that in software: the dispute becomes a bounded work order, not a mood.
