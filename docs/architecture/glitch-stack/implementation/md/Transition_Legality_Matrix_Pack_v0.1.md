# Transition Legality Matrix Pack v0.1

**Status:** Draft transition legality pack  
**Scope:** Legal, conditional, and forbidden state transitions for the first implementation layer of the new stack  
**Purpose:** Define the canonical transition matrix that sits above:
- `Object Model Draft Pack v0.1`
- `Schema Pack v0.1`
- `Semantic Validator Rules Pack v0.1`

and below future runtime reducers, validators, and guard functions.

**Applies to**
- `StatusTuple`
- `ExecutionNode`
- `GlitchNode`
- `ResearchNode`
- `BackwardNode`
- `EvidenceRecord`
- `ChallengeRecord`
- `ReviewRecord`
- `TransitionGuard`
- `ReopenabilityGate`
- `GraphNodeView`
- `GraphEdgeView`
- `GraphSlice`

---

## 1. Why this pack exists

Schemas answer:

- “Is the object shaped correctly?”

Semantic rules answer:

- “Does the object mean something coherent?”

This pack answers the next question:

- **“May this object legally move from here to there?”**

That question is different.

An object may be:
- well-formed,
- semantically coherent,
and still not be allowed to transition into a new state.

Examples:
- a valid `ResearchNode` may still not become executable
- a valid `ChallengeRecord` may still not jump directly from `open` to `settled`
- a valid evidence record may still not jump from `asserted` to `signed` without witness basis
- a valid graph object may still not be allowed to move from cinematic projection into runtime authority

This pack exists to make those routes explicit.

---

## 2. Transition principles

### 2.1 State movement must be narrow
The system should permit only a small number of legal transitions.

### 2.2 Conditional transitions must name their conditions
If a transition is not unconditional, the guard must be explicit.

### 2.3 Forbidden transitions must be first-class
“Should probably not happen” is too weak.
Dangerous routes must be encoded as:
- forbidden
- machine-checkable
- rule-coded

### 2.4 Graph and cinema stay downstream
No transition matrix may allow display-layer projection to become runtime truth by shortcut.

### 2.5 Review may reinterpret, not erase
Where transitions produce revised understanding, the original lineage must remain visible.

---

## 3. Transition classes

Every transition belongs to one of three classes.

### 3.1 `LEGAL`
The transition is allowed without extra exceptional evidence beyond ordinary object completeness.

### 3.2 `CONDITIONAL`
The transition is allowed only if specific guards are satisfied.

Examples:
- witness attached
- review outcome exists
- deadline still open
- evidence hash matches
- reopenability gate allows
- explicit role / privilege / policy passes

### 3.3 `FORBIDDEN`
The transition must fail even if the object is otherwise well-formed.

---

## 4. Canonical transition result shape

Future reducers or validators should return something like:

```json
{
  "allowed": false,
  "transition_class": "FORBIDDEN",
  "rule_code": "TRN_RESEARCH_TO_EXECUTABLE_FORBIDDEN",
  "message": "ResearchNode cannot become executable directly.",
  "from_state": "research/evidence_required",
  "to_state": "runtime/executable",
  "required_conditions": []
}
```

Required fields:
- `allowed`
- `transition_class`
- `rule_code`
- `message`

Optional fields:
- `required_conditions`
- `from_state`
- `to_state`
- `target_ref`
- `details`

---

## 5. Transition domains

The matrix must treat different domains separately.

### Domain A — evidence state
- asserted
- observed
- witnessed
- signed
- challenge_open
- settled
- expired
- cinematic_only

### Domain B — challenge state
- open
- queued
- under_review
- resolved_uphold
- resolved_modify
- resolved_split
- dismissed
- expired
- archived

### Domain C — reopenability
- not_reopenable
- evidence_required
- review_required
- reopenable

### Domain D — executability
- executable false -> true
- executable true -> false

### Domain E — lane
- runtime
- research
- witness
- historical
- cinematic

These domains interact, but should not be collapsed.

---

## 6. Evidence-state legality matrix

## 6.1 Canonical evidence transition table

| From | To | Class | Rule code | Notes |
|---|---|---|---|---|
| asserted | observed | LEGAL | TRN_EVID_ASSERTED_TO_OBSERVED | Event linked to concrete observation |
| observed | witnessed | CONDITIONAL | TRN_EVID_OBSERVED_TO_WITNESSED | Requires witness binding |
| witnessed | signed | CONDITIONAL | TRN_EVID_WITNESSED_TO_SIGNED | Requires signer and valid witness path |
| signed | challenge_open | LEGAL | TRN_EVID_SIGNED_TO_CHALLENGE_OPEN | Challenge opens over already grounded object |
| witnessed | challenge_open | LEGAL | TRN_EVID_WITNESSED_TO_CHALLENGE_OPEN | Same principle |
| challenge_open | settled | CONDITIONAL | TRN_EVID_CHALLENGE_TO_SETTLED | Requires linked review outcome |
| any_nonexpired | expired | LEGAL | TRN_EVID_TO_EXPIRED | Context/time/standing lost |
| cinematic_only | any_noncinematic | FORBIDDEN | TRN_EVID_CINEMATIC_ESCAPE_FORBIDDEN | Projection cannot self-upgrade |
| asserted | signed | FORBIDDEN | TRN_EVID_ASSERTED_TO_SIGNED_FORBIDDEN | No witness shortcut |
| asserted | settled | FORBIDDEN | TRN_EVID_ASSERTED_TO_SETTLED_FORBIDDEN | No challenge/review path |
| expired | signed | FORBIDDEN | TRN_EVID_EXPIRED_TO_SIGNED_FORBIDDEN | Must re-enter through revalidation path, not direct |
| expired | witnessed | CONDITIONAL | TRN_EVID_EXPIRED_TO_WITNESSED_REVALIDATE | Only through explicit revalidation workflow |

---

## 7. Challenge-state legality matrix

| From | To | Class | Rule code | Notes |
|---|---|---|---|---|
| open | queued | LEGAL | TRN_CHALLENGE_OPEN_TO_QUEUED | Accepted into process |
| queued | under_review | LEGAL | TRN_CHALLENGE_QUEUED_TO_UNDER_REVIEW | Review begins |
| under_review | resolved_uphold | CONDITIONAL | TRN_CHALLENGE_REVIEW_TO_UPHOLD | Requires ReviewRecord |
| under_review | resolved_modify | CONDITIONAL | TRN_CHALLENGE_REVIEW_TO_MODIFY | Requires ReviewRecord |
| under_review | resolved_split | CONDITIONAL | TRN_CHALLENGE_REVIEW_TO_SPLIT | Requires ReviewRecord + split lineage |
| open | dismissed | CONDITIONAL | TRN_CHALLENGE_OPEN_TO_DISMISSED | Requires procedural insufficiency decision |
| queued | dismissed | CONDITIONAL | TRN_CHALLENGE_QUEUED_TO_DISMISSED | Same |
| any_open_state | expired | LEGAL | TRN_CHALLENGE_OPEN_TO_EXPIRED | Deadline elapsed |
| any_resolved_state | archived | LEGAL | TRN_CHALLENGE_RESOLVED_TO_ARCHIVED | Historical retention |
| open | resolved_uphold | FORBIDDEN | TRN_CHALLENGE_SKIP_REVIEW_FORBIDDEN | No direct settlement |
| queued | resolved_modify | FORBIDDEN | TRN_CHALLENGE_SKIP_UNDER_REVIEW_FORBIDDEN | No jump |
| expired | open | FORBIDDEN | TRN_CHALLENGE_REOPEN_EXPIRED_FORBIDDEN | New challenge required, not resurrection |
| archived | under_review | FORBIDDEN | TRN_CHALLENGE_ARCHIVE_REVIVE_FORBIDDEN | Must reopen via new object |

---

## 8. Reopenability-state legality matrix

| From | To | Class | Rule code | Notes |
|---|---|---|---|---|
| evidence_required | review_required | CONDITIONAL | TRN_REOPEN_EVIDENCE_TO_REVIEW | Evidence obtained, review still needed |
| evidence_required | reopenable | CONDITIONAL | TRN_REOPEN_EVIDENCE_TO_REOPENABLE | If evidence fully sufficient and no review required |
| review_required | reopenable | CONDITIONAL | TRN_REOPEN_REVIEW_TO_REOPENABLE | Requires successful review |
| reopenable | not_reopenable | CONDITIONAL | TRN_REOPEN_REOPENABLE_TO_CLOSED | Conditions expired or refuted |
| not_reopenable | evidence_required | CONDITIONAL | TRN_REOPEN_CLOSED_TO_EVIDENCE | Only if new credible path discovered |
| not_reopenable | reopenable | FORBIDDEN | TRN_REOPEN_CLOSED_SHORTCUT_FORBIDDEN | No leap over evidence/review |
| evidence_required | not_reopenable | LEGAL | TRN_REOPEN_EVIDENCE_TO_CLOSED | Gap proven impossible / invalid |
| review_required | evidence_required | CONDITIONAL | TRN_REOPEN_REVIEW_BACK_TO_EVIDENCE | Review finds evidence insufficient |

---

## 9. Lane legality matrix

| From lane | To lane | Class | Rule code | Notes |
|---|---|---|---|---|
| runtime | historical | LEGAL | TRN_LANE_RUNTIME_TO_HISTORICAL | Runtime object archived/expired |
| runtime | witness | CONDITIONAL | TRN_LANE_RUNTIME_TO_WITNESS | Evidence projection / witness anchoring |
| runtime | research | FORBIDDEN_DIRECT | TRN_LANE_RUNTIME_TO_RESEARCH_DIRECT_FORBIDDEN | Must go through GlitchNode/derivation path |
| research | historical | LEGAL | TRN_LANE_RESEARCH_TO_HISTORICAL | Archived or expired research |
| research | runtime | FORBIDDEN | TRN_LANE_RESEARCH_TO_RUNTIME_FORBIDDEN | Requires new runtime object via guarded re-entry |
| research | witness | CONDITIONAL | TRN_LANE_RESEARCH_TO_WITNESS | If evidence packet created around research object |
| witness | historical | LEGAL | TRN_LANE_WITNESS_TO_HISTORICAL | Archive/expiry |
| cinematic | historical | CONDITIONAL | TRN_LANE_CINEMATIC_TO_HISTORICAL | May archive projection artifact as historical display only |
| cinematic | runtime | FORBIDDEN | TRN_LANE_CINEMATIC_TO_RUNTIME_FORBIDDEN | Never |
| cinematic | witness | FORBIDDEN | TRN_LANE_CINEMATIC_TO_WITNESS_FORBIDDEN | Projection never self-upgrades |
| historical | research | CONDITIONAL | TRN_LANE_HISTORICAL_TO_RESEARCH_RECAST | Only via explicit recast/new derivative object |
| historical | runtime | FORBIDDEN | TRN_LANE_HISTORICAL_TO_RUNTIME_FORBIDDEN | Must instantiate new runtime object |

### Note
“Lane transition” often should mean:
- **create a derived new object in a new lane**
rather than mutate the original object in place.

This is especially true for:
- runtime -> witness
- glitch -> research
- historical -> research recast

---

## 10. Executability legality matrix

| From | To | Class | Rule code | Notes |
|---|---|---|---|---|
| false | false | LEGAL | TRN_EXEC_FALSE_TO_FALSE | No change |
| true | false | LEGAL | TRN_EXEC_TRUE_TO_FALSE | Stop, quarantine, expiry, refusal |
| false | true | CONDITIONAL | TRN_EXEC_FALSE_TO_TRUE_CONDITIONAL | Only for runtime-lane objects with all guards satisfied |
| false (research) | true | FORBIDDEN | TRN_EXEC_RESEARCH_TO_TRUE_FORBIDDEN | No shortcut |
| false (cinematic) | true | FORBIDDEN | TRN_EXEC_CINEMATIC_TO_TRUE_FORBIDDEN | Never |
| false (expired) | true | FORBIDDEN | TRN_EXEC_EXPIRED_TO_TRUE_FORBIDDEN | Must revalidate via new object path |

### Minimum conditions for `false -> true`
- lane == runtime
- not expired
- not cinematic_only
- required privilege/volition/integrity guards pass
- if derived from research, must occur through new guarded runtime object creation, not in-place flip

---

## 11. Object-family transition rules

## 11.1 `ExecutionNode`

Allowed:
- active runtime execution -> ended runtime execution
- ended runtime execution -> historical projection
- execution -> glitch derivation

Forbidden:
- `ExecutionNode` mutated into `ResearchNode`
- `ExecutionNode` mutated into cinematic-only view object as source of truth
- `ExecutionNode` kept executable after terminal expiry

### Rule codes
- `TRN_EXECNODE_TO_GLITCH_DERIVE`
- `TRN_EXECNODE_TO_HISTORICAL_ARCHIVE`
- `TRN_EXECNODE_TO_RESEARCH_INPLACE_FORBIDDEN`

---

## 11.2 `GlitchNode`

Allowed:
- runtime evidence strengthening
- challenge opening
- challenge settlement
- derivation of `ResearchNode`
- archival to historical

Conditional:
- `expired -> witnessed` via explicit revalidation path
- witness strengthening

Forbidden:
- `GlitchNode` executable true
- `GlitchNode` direct runtime continuation without new runtime object
- `GlitchNode` direct cinematic laundering into success path

### Rule codes
- `TRN_GLITCH_TO_RESEARCH_DERIVE`
- `TRN_GLITCH_TO_HISTORICAL_ARCHIVE`
- `TRN_GLITCH_EXECUTABLE_FORBIDDEN`
- `TRN_GLITCH_TO_SUCCESS_SHORTCUT_FORBIDDEN`

---

## 11.3 `ResearchNode`

Allowed:
- evidence_required -> review_required
- evidence_required -> reopenable
- challenge open (if policy allows)
- archival to historical
- derivation of `BackwardNode`

Conditional:
- witness attachment for audit/research use
- recast into new runtime candidate via explicit guarded construction, not in-place mutation

Forbidden:
- direct executable flip
- direct lane mutation to runtime
- direct evidence jump from asserted to signed without witness path

### Rule codes
- `TRN_RESEARCH_TO_BACKWARD_DERIVE`
- `TRN_RESEARCH_TO_HISTORICAL_ARCHIVE`
- `TRN_RESEARCH_TO_RUNTIME_SHORTCUT_FORBIDDEN`
- `TRN_RESEARCH_TO_EXECUTABLE_FORBIDDEN`

---

## 11.4 `BackwardNode`

Allowed:
- remain in research lane
- receive supporting evidence metadata
- archive to historical
- feed future review/research planning

Forbidden:
- executable flip
- runtime lane mutation
- being treated as roadmap commitment

### Rule codes
- `TRN_BACKWARD_EXECUTABLE_FORBIDDEN`
- `TRN_BACKWARD_TO_RUNTIME_FORBIDDEN`

---

## 11.5 `EvidenceRecord`

Allowed:
- asserted -> observed -> witnessed -> signed
- signed/witnessed -> challenge_open
- challenge_open -> settled
- any current evidence -> expired

Conditional:
- expired -> witnessed via explicit revalidation workflow

Forbidden:
- cinematic_only -> witnessed/signed
- asserted -> signed shortcut
- signed -> legitimacy via state mutation shortcut

### Rule codes
- `TRN_EVID_REVALIDATE_EXPIRED`
- `TRN_EVID_ASSERTED_SIGNED_SHORTCUT_FORBIDDEN`
- `TRN_EVID_SIGNATURE_TO_AUTHORITY_FORBIDDEN`

---

## 11.6 `ChallengeRecord`

Allowed:
- open -> queued -> under_review -> resolved_* -> archived
- open/queued/under_review -> expired
- open/queued -> dismissed

Forbidden:
- open -> resolved_* directly
- expired -> under_review
- archived -> live state

### Rule codes
- `TRN_CHALLENGE_DIRECT_RESOLVE_FORBIDDEN`
- `TRN_CHALLENGE_EXPIRED_REVIVE_FORBIDDEN`
- `TRN_CHALLENGE_ARCHIVE_REVIVE_FORBIDDEN`

---

## 11.7 `ReviewRecord`

Allowed:
- creation after valid challenge
- outcome-specific lineage updates
- signed/no-signed variants depending policy

Forbidden:
- reclassify without prior/new class
- split without lineage
- unsigned record masquerading as final signed settlement

### Rule codes
- `TRN_REVIEW_RECLASS_INCOMPLETE_FORBIDDEN`
- `TRN_REVIEW_SPLIT_WITHOUT_LINEAGE_FORBIDDEN`
- `TRN_REVIEW_UNSIGNED_FINALITY_FORBIDDEN`

---

## 11.8 `GraphNodeView` / `GraphEdgeView` / `GraphSlice`

Allowed:
- regeneration from source truth
- audit-mode enrichment
- historical export
- integrity-root binding for slices

Forbidden:
- becoming runtime truth
- changing evidence state by display update
- cinematic edge retyped as execution edge
- graph slice exported as audit-complete if integrity context absent and policy forbids

### Rule codes
- `TRN_GRAPH_TO_RUNTIME_FORBIDDEN`
- `TRN_GRAPH_BADGE_UPGRADE_FORBIDDEN`
- `TRN_GRAPH_CINEMATIC_EDGE_RETYPE_FORBIDDEN`

---

## 12. Conditional guard catalog

Each `CONDITIONAL` transition should name its required guard set.

### Guard families

#### G1 — witness guards
- witness attached
- witness envelope valid
- signature valid
- chain continuity valid

#### G2 — review guards
- review record exists
- reviewer role allowed
- outcome compatible
- lineage preserved

#### G3 — time guards
- window open
- deadline not passed
- expiry not triggered

#### G4 — runtime guards
- privilege passes
- volition passes
- integrity passes
- caution/consent passes
- L4 constraints still satisfied

#### G5 — research guards
- missing evidence satisfied
- reopenability gate allows
- explicit new derivative runtime object created

---

## 13. Anti-collapse transition rules

These are the most important rules in the pack.

## 13.1 Research collapse prohibition

### Rule code
`TRN_ANTI_COLLAPSE_RESEARCH_RUNTIME`

### Forbidden route
`ResearchNode.status.executable: false -> true` in place

### Correct route
Research remains quarantined.
If conditions are satisfied, create a **new runtime candidate object** under guards.

---

## 13.2 Cinematic laundering prohibition

### Rule code
`TRN_ANTI_COLLAPSE_CINEMATIC_AUTHORITY`

### Forbidden route
Any cinematic projection object gains:
- witness authority
- runtime authority
- or legality just by projection update

---

## 13.3 Signature laundering prohibition

### Rule code
`TRN_ANTI_COLLAPSE_SIGNATURE_LEGITIMACY`

### Forbidden route
`signed` evidence becomes “legitimate action” without separate policy/authority evaluation

---

## 13.4 Review erasure prohibition

### Rule code
`TRN_ANTI_COLLAPSE_REVIEW_ERASURE`

### Forbidden route
Review modifies target class or interpretation while deleting or hiding the prior historical branch

---

## 14. Recommended reducer policy

A future reducer should operate like this:

1. schema-validate
2. semantic-validate
3. transition-check
4. integrity-check (when relevant)
5. only then mutate or emit derived object

If transition is conditional and guards fail:
- no partial mutation
- no silent downgrade
- fail closed
- return explicit rule code

---

## 15. Minimal machine-readable matrix sketch

Future code may encode the matrix like:

```python
TRANSITIONS = {
    ("evidence_state", "asserted", "observed"): {"class": "LEGAL", "rule": "TRN_EVID_ASSERTED_TO_OBSERVED"},
    ("evidence_state", "observed", "witnessed"): {
        "class": "CONDITIONAL",
        "rule": "TRN_EVID_OBSERVED_TO_WITNESSED",
        "guards": ["witness_attached"]
    },
    ("executability", False, True): {
        "class": "CONDITIONAL",
        "rule": "TRN_EXEC_FALSE_TO_TRUE_CONDITIONAL",
        "guards": ["lane_runtime", "not_expired", "runtime_guards_pass"]
    },
    ("lane", "cinematic", "runtime"): {
        "class": "FORBIDDEN",
        "rule": "TRN_LANE_CINEMATIC_TO_RUNTIME_FORBIDDEN"
    }
}
```

---

## 16. Example illegal transition set

### Case
A `ResearchNode` with:
- `lane = research`
- `reopenability = evidence_required`
- `executable = false`

attempts in-place change to:
- `lane = runtime`
- `executable = true`

Expected failures:

```json
[
  {
    "allowed": false,
    "transition_class": "FORBIDDEN",
    "rule_code": "TRN_LANE_RESEARCH_TO_RUNTIME_FORBIDDEN",
    "message": "Research lane cannot mutate directly into runtime lane."
  },
  {
    "allowed": false,
    "transition_class": "FORBIDDEN",
    "rule_code": "TRN_RESEARCH_TO_EXECUTABLE_FORBIDDEN",
    "message": "ResearchNode cannot become executable in place."
  }
]
```

---

## 17. Example conditional transition set

### Case
An `EvidenceRecord` moves:
- `observed -> witnessed`

Allowed only if:
- witness attached
- witness envelope valid

Expected output:

```json
{
  "allowed": true,
  "transition_class": "CONDITIONAL",
  "rule_code": "TRN_EVID_OBSERVED_TO_WITNESSED",
  "required_conditions": [
    "witness_attached",
    "witness_envelope_valid"
  ]
}
```

---

## 18. Explicit bridge

This pack turns semantic honesty into route legality.

It defines not only what objects are and mean,
but which state routes are:
- legal,
- conditional,
- or forbidden.

That is the explicit bridge between:
- typed objects,
- semantic truth,
- and reducer-safe future implementation.

---

## 19. Hidden bridges

### Hidden Bridge 1 — Cybernetics
A regulator is not only defined by its states, but by which state changes it forbids.

### Hidden Bridge 2 — Information Theory
Transition matrices preserve lineage by preventing illicit state compression and category shortcuts.

---

## 20. Earth paragraph

In an actual control system, a fault light can become a maintenance ticket, a maintenance ticket can become a signed repair report, and a signed repair report can allow a machine to be returned to service — but only through a narrow sequence. What never happens in a sane plant is that the fault light itself quietly turns green because the dashboard software found an elegant path through the UI. This pack exists to stop exactly that kind of fake smoothness.

---

## 21. Final position

`Transition Legality Matrix Pack v0.1` is the first route map of what the stack is allowed to become.

After this point, future implementation should not only ask:
- “Is this object well-formed?”
- “Is this object meaningful?”

It must also ask:
- **“Does this object have a legal path to become what it wants to become?”**
