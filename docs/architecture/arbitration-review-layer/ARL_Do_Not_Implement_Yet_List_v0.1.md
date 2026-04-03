# ARL Do Not Implement Yet List v0.1
## Explicit exclusion list for the first implementation wave in ester-clean-code

**Status:** Draft v0.1  
**Layer:** Implementation-facing anti-scope guard  
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
- `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`

**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document lists what **must not** be implemented in the first ARL wave inside `ester-clean-code`.

This is not pessimism.
This is structural self-defense.

A first implementation wave dies in two classic ways:

1. it tries to be complete too early;
2. it builds spectacle before control.

This list exists to prevent both.

It is the engineering equivalent of putting tape over the shiny red button that everybody wants to press before the brakes are actually connected.

---

## 1. Purpose

The purpose of this document is to define an explicit anti-scope boundary for first-wave ARL work.

It answers the question:

> What tempting things should we consciously refuse to build yet, even if they sound impressive?

Without this list, a first-wave implementation can drown in:
- ambition,
- architectural vanity,
- or fear of seeming “too simple.”

ARL does not need theatrical complexity to be real.
It needs discipline.

---

## 2. Governing rule

If a feature does not directly strengthen:
- stop,
- freeze,
- dispute persistence,
- witness trace,
- review routing,
- lawful outcome,
- or lawful re-entry discipline,

then it is probably not first-wave work.

That does not mean the feature is bad.
It means the timing is bad.

---

## 3. Do not implement yet: full federation arbitration

### Excluded for now
- multi-node quorum negotiation engine
- distributed arbitration protocol across sisters
- automatic peer voting mesh
- federated recusal and rotating arbiter clusters
- large social consensus orchestration

### Why excluded
Because local ARL must become real before distributed ARL becomes imaginable.

### What to do instead
Keep compatibility hooks only.
No full federation engine yet.

---

## 4. Do not implement yet: bond economics

### Excluded for now
- challenge bond mechanics
- prediction bond accounting
- bond slashing engines
- reputation-linked economic penalties
- budgetized social punishment logic

### Why excluded
Because the first wave must first learn to stop, remember, and decide lawfully.

### What to do instead
Record reason codes and bounded outcomes.
Leave bond economy to a later wave.

---

## 5. Do not implement yet: giant Judge engine

### Excluded for now
- large central “Judge service”
- autonomous synthesis monarch
- universal truth arbitration daemon
- magical meta-decider that swallows every dispute class

### Why excluded
Because this is the fastest way to create a new hidden sovereign center,
which is exactly what the architecture says not to do.

### What to do instead
Build bounded hook points and explicit review tasks.
Let “Judge” remain procedural, not imperial.

---

## 6. Do not implement yet: score soup quorum math

### Excluded for now
- giant weighted-score merger for every source
- opaque confidence stacking
- one-number truth synthesis
- behavioral flattening of memory / Sisters / anchor / oracle into one scalar

### Why excluded
Because this destroys precedence and creates fake objectivity.

### What to do instead
Preserve source classes and bounded precedence.
Wave one needs explicit hierarchy, not statistical theater.

---

## 7. Do not implement yet: sociality grand opera

### Excluded for now
- full Social Vector / Sisters arbitration mesh
- high-dimensional social trust markets
- inter-entity social scoring engines
- permanent social override layers

### Why excluded
Because Social Vector is important,
but first-wave implementation must not collapse into either:
- herd worship,
- or distributed noise management.

### What to do instead
Leave room in persistence and event fields.
Implement compact support only.

---

## 8. Do not implement yet: UI-first ARL

### Excluded for now
- dispute dashboards as primary deliverable
- glossy admin overlays before runtime controls exist
- colored badges for unresolved state without real state machine support
- operator theatre standing in for actual freeze discipline

### Why excluded
Because UI is the easiest place to lie convincingly.

### What to do instead
Make the runtime true first.
Then let UI reveal it.

---

## 9. Do not implement yet: endless event expansion

### Excluded for now
- dozens of fine-grained ceremonial events
- verbose event ontology for every micro-step
- per-thought or per-subscore event logging
- human-facing event prose as substitute for state

### Why excluded
Because event inflation destroys signal.

### What to do instead
Stick to the minimal pack until state, routing, and outcomes are stable.

---

## 10. Do not implement yet: rewrite of the whole executor stack

### Excluded for now
- total replacement of proactivity executor
- total replacement of volition gate
- global refactor of queue systems
- whole-repo “ARL architecture rewrite”

### Why excluded
Because first-wave ARL should attach to the skeleton that already exists.

### What to do instead
Use the bones already present:
- existing queue surfaces,
- existing windows,
- existing witness layer,
- existing guard surfaces.

---

## 11. Do not implement yet: deep code fusion with all existing subsystems

### Excluded for now
- touching every listener
- touching every route
- touching every template
- touching every orchestration file
- global unification before first local success

### Why excluded
Because broad surface area multiplies bugs and interpretation drift.

### What to do instead
Keep first-wave integration narrow and central.

---

## 12. Do not implement yet: silent automation of irreversible decisions

### Excluded for now
- unreviewed auto-accept irreversible loss
- silent quarantine release
- automatic authority rollback without durable review state
- fully autonomous scar decisions without witness trace

### Why excluded
Because irreversible outcome is one of the most serious ARL outputs.

### What to do instead
Keep irreversible outcomes explicit, bounded, and witness-bound.

---

## 13. Do not implement yet: anchor mythology

### Excluded for now
- metaphysical “anchor mode”
- casual anchor override button
- silent operator god-switch
- rewriting continuity by invoking `a` as convenience

### Why excluded
Because the architecture says `a` may be reinterpreted but not casually rewritten.

### What to do instead
Allow only explicit, bounded, witness-bound anchor participation.

---

## 14. Do not implement yet: accidental cloud sovereignty

### Excluded for now
- cloud model as hidden final arbiter
- automatic oracle fallback under uncertainty
- remote truth vending in the name of “helping review”
- unlogged cloud assistance

### Why excluded
Because it silently destroys local-first continuity and bounded oracle discipline.

### What to do instead
Keep remote review explicit, budgeted, and window-bound.

---

## 15. Do not implement yet: perfect schema obsession

### Excluded for now
- endless schema polishing before hooks exist
- machine-readable completeness mania without operational stop control
- giant type systems for still-theoretical branches

### Why excluded
Because the system needs brakes before it needs beautiful paperwork.

### What to do instead
Use compact, stable first-wave structures and evolve later.

---

## 16. Signs you are violating this document

You are probably breaking first-wave discipline if:

- the UI is progressing faster than freeze logic,
- new review events are appearing faster than durable dispute state,
- new distributed features are proposed before local deadlock survives reboot,
- someone says “we can solve that later with the Judge,”
- or the code is becoming more impressive than trustworthy.

Those are all bad smells.

---

## 17. What first-wave work should feel like

It should feel:
- narrower than your ego wants,
- more boring than a conference talk,
- more ledger-like than philosophical,
- and more stoppable than intelligent.

That is good.
That means it might actually hold.

---

## 18. Explicit bridge

**anti-scope discipline ↔ bounded first-wave ARL ↔ survivable implementation**

---

## 19. Hidden bridges

### 19.1 DEA / EA standing
Do not explode standing into the full wider doctrine before the first local implementation can even deny a malformed claim.

### 19.2 SER-FED anti-capture
Most “cool ideas” on this list fail because they quietly concentrate power or complexity too early.

---

## 20. Earth paragraph

On a real warehouse floor, when the stop gate and seal log are not even connected yet, nobody should be designing holographic dispute analytics, autonomous pallet courts, or a blockchain market for forklift reputation. First you make sure the disputed pallet can actually be stopped, tagged, logged, inspected, and either released or denied. Everything else can wait its turn.
