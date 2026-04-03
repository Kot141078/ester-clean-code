# INDEX — ARL Implementation Pack for ester-clean-code v0.1

**Status:** Draft v0.1  
**Canonical normative source:** `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. Package purpose

This package exists to make the ARL implementation line inside `ester-clean-code`
readable, navigable, and non-chaotic.

It separates:
- core bridge documents,
- mechanics,
- rollout discipline,
- repository placement,
- and publication notes.

---

## 2. Primary documents

### 2.1 Core bridge
1. `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
2. `ARL_Freeze_State_Machine_v0.1.md`
3. `ARL_Witness_Event_Binding_v0.1.md`
4. `ARL_Quorum_Input_Precedence_v0.1.md`

### 2.2 Mechanics
5. `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
6. `ARL_Runtime_Hook_Points_v0.1.md`
7. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
8. `ARL_Dispute_State_Persistence_v0.1.md`
9. `ARL_Review_Task_Routing_v0.1.md`

### 2.3 Rollout discipline
10. `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
11. `ARL_Do_Not_Implement_Yet_List_v0.1.md`

### 2.4 Package-facing documents
12. `README.md`
13. `INDEX.md`
14. `DOC_MAP.md`
15. `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
16. `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 3. Recommended reading order

### 3.1 For architecture / logic
1. `README.md`
2. `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
3. `ARL_Freeze_State_Machine_v0.1.md`
4. `ARL_Quorum_Input_Precedence_v0.1.md`

### 3.2 For implementation planning
1. `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
2. `ARL_Runtime_Hook_Points_v0.1.md`
3. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
4. `ARL_Dispute_State_Persistence_v0.1.md`
5. `ARL_Review_Task_Routing_v0.1.md`
6. `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
7. `ARL_Do_Not_Implement_Yet_List_v0.1.md`

### 3.3 For repository / release preparation
1. `DOC_MAP.md`
2. `ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md`
3. `ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md`

---

## 4. Interpretation priority

If wording tension appears between documents, interpret in this order:

1. `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
2. `ARL_Freeze_State_Machine_v0.1.md`
3. `ARL_Runtime_Hook_Points_v0.1.md`
4. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
5. `ARL_Dispute_State_Persistence_v0.1.md`
6. `ARL_Review_Task_Routing_v0.1.md`
7. `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
8. package-facing documents

This keeps the implementation line from becoming a pile of equally weighted notes.

---

## 5. Explicit bridge

**bridge → state machine → hook points → events → persistence → routing → rollout**

---

## 6. Earth paragraph

If a warehouse dispute binder has the stop procedure in one tab, the seal instructions in another, and the release criteria in a third, someone still needs an index or the next shift will waste an hour pretending to rediscover the system. This file is that index.
