# DOC_MAP — ARL Implementation Pack for ester-clean-code v0.1
## Canonical document map for the ECC-facing ARL package

**Status:** Draft v0.1  
**Canonical normative source:** `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. Purpose

This file classifies the documents in the ECC-facing ARL package by role.

Its purpose is to stop three future problems:

- not knowing which file is foundational,
- not knowing which file is only packaging/support,
- and not knowing which papers are about implementation versus publication.

---

## 2. Document classes

### 2.1 Core implementation doctrine
These define the main implementation logic:

- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Witness_Event_Binding_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`

### 2.2 Mechanical implementation papers
These define the practical mechanics:

- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
- `ARL_Dispute_State_Persistence_v0.1.md`
- `ARL_Review_Task_Routing_v0.1.md`

### 2.3 Rollout / anti-scope discipline
These define staged integration and boundaries:

- `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
- `ARL_Do_Not_Implement_Yet_List_v0.1.md`

### 2.4 Package-facing and release-facing papers
These support packaging, navigation, repository placement, and release/deposit work:

- `README.md`
- `INDEX.md`
- `DOC_MAP.md`
- `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
- `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 3. What is canonical here and what is not

### 3.1 Canonical here
Canonical here means:
- implementation-facing package truth for the ECC bridge,
- internal reading order,
- packaging and placement logic for this pack.

### 3.2 Not canonical here
Not canonical here:
- the normative ARL constitution itself,
- the full doctrinal home of arbitration/review semantics.

That remains upstream in `sovereign-entity-recursion`.

---

## 4. Recommended reading paths

### 4.1 Architect / author path
- `README.md`
- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
- `ARL_Freeze_State_Machine_v0.1.md`
- `ARL_Quorum_Input_Precedence_v0.1.md`

### 4.2 Implementation path
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
- `ARL_Runtime_Hook_Points_v0.1.md`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
- `ARL_Dispute_State_Persistence_v0.1.md`
- `ARL_Review_Task_Routing_v0.1.md`
- `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`

### 4.3 Release / deposit path
- `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
- `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 5. Explicit bridge

**normative ARL upstream ↔ ECC implementation pack ↔ future code iteration**

---

## 6. Hidden bridges

### 6.1 DEA / EA standing
Even package-facing docs must not erase the standing structure behind the implementation.

### 6.2 SER-FED anti-capture
Package organization itself should not encourage hidden doctrinal drift toward a new implementation sovereign.

---

## 7. Earth paragraph

On a real warehouse floor, one binder tab says “stop,” another says “inspect,” and another says “release.” Somebody still has to mark which tabs are actual procedure, which are local notes, and which are shipping paperwork. That is the whole job of a document map.
