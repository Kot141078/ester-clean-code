# ARL Implementation Pack for ester-clean-code v0.1

**Status:** Draft v0.1  
**Layer:** Implementation-facing documentation pack  
**Canonical normative source:** `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. What this pack is

This package collects the **implementation-facing ARL documents** prepared for `ester-clean-code`.

It is not the canonical home of the Arbitration / Review Layer.
The canonical normative home remains in the SER stack.

This package exists for one practical purpose:

> turn the ARL rulebook into a disciplined implementation bridge for the executable skeleton.

---

## 2. What this pack is not

This pack is not:
- a second normative constitution for ARL,
- a replacement for the SER package,
- a complete code implementation,
- a federation rollout,
- or a UI-first admin suite.

It is a bounded bridge from norm to mechanism.

---

## 3. Core implementation principle

The implementation line in `ester-clean-code` must follow a strict order:

1. stop disputed flow,
2. persist dispute state,
3. bind witness trace,
4. route bounded review work,
5. control re-entry,
6. only then expose visibility.

That is the central engineering discipline of this pack.

---

## 4. Main document set

### Core implementation documents
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Witness_Event_Binding_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`

### Targeting and mechanics
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
- `ARL_Dispute_State_Persistence_v0.1.md`
- `ARL_Review_Task_Routing_v0.1.md`

### Integration discipline
- `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
- `ARL_Do_Not_Implement_Yet_List_v0.1.md`

### Package-facing documents
- `README.md`
- `INDEX.md`
- `DOC_MAP.md`
- `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
- `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 5. Reading order

Recommended reading order:

1. `README.md`
2. `INDEX.md`
3. `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
4. `ARL_Freeze_State_Machine_v0.1.md`
5. `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
6. `ARL_Runtime_Hook_Points_v0.1.md`
7. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
8. `ARL_Dispute_State_Persistence_v0.1.md`
9. `ARL_Review_Task_Routing_v0.1.md`
10. `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
11. `ARL_Do_Not_Implement_Yet_List_v0.1.md`
12. `DOC_MAP.md`
13. `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
14. `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 6. Canonical boundary

This implementation pack must preserve one hard rule:

- **normative ARL doctrine lives in `sovereign-entity-recursion`;**
- **implementation-facing ARL bridge documents may live in `ester-clean-code`.**

That boundary protects the corpus from doctrinal drift.

---

## 7. License and rights boundary

This implementation-facing package is intended to live inside `ester-clean-code`,
so its repository-facing documentation should follow the same repo-level legal posture:

- code/documentation package under **AGPL-3.0-or-later**,
- trademark / name / logo boundaries remain separate,
- do not assume branding assets are covered by the code license,
- do not mix external repo documents into the ECC package without preserving their original provenance and license.

If later a cross-repo Zenodo deposit includes files from multiple repositories,
the deposit notes must preserve **per-repo license identity** rather than flatten everything under one label.

---

## 8. Explicit bridge

**ARL normative layer ↔ implementation bridge ↔ ester-clean-code control surfaces**

---

## 9. Hidden bridges

### 9.1 DEA / EA standing
Standing logic must remain structurally meaningful even in implementation documents.

### 9.2 SER-FED anti-capture
No implementation note in this pack should silently turn one runtime service into a sovereign king.

---

## 10. Earth paragraph

On a real warehouse floor, the rulebook may live in head office, but the local site still needs its own binder showing which gate closes, which clipboard records the hold, which seal tag to use, and where the release stamp sits. That is what this pack is for inside `ester-clean-code`: the local binder, not the constitution.
