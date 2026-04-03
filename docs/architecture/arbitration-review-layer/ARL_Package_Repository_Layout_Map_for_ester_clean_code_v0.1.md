# ARL Package Repository Layout Map for ester-clean-code v0.1
## Recommended repository placement map for the ECC-facing ARL package

**Status:** Draft v0.1  
**Layer:** Package layout / repository map  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation-facing home:** `ester-clean-code`  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## 1. Purpose

This document defines the recommended repository layout for the
implementation-facing ARL package inside `ester-clean-code`.

The goal is simple:
- one clean subtree,
- one readable entry path,
- one future PDF path,
- one future hash path,
- and no scattering of related documents across random folders.

This is not the normative home of ARL.
It is the implementation-facing home of the ECC bridge package.

---

## 2. Placement principle

The package should be placed as a coherent document subtree,
not as isolated files dropped into unrelated directories.

Recommended canonical package root inside `ester-clean-code`:

```text
docs/
  architecture/
    arbitration-review-layer/
```

This keeps the package:
- near existing architecture-facing material,
- visible to readers,
- and conceptually separate from executable code.

---

## 3. Recommended package tree

```text
docs/
  architecture/
    arbitration-review-layer/
      README.md
      INDEX.md
      DOC_MAP.md

      ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md
      ARL_Freeze_State_Machine_v0.1.md
      ARL_Witness_Event_Binding_v0.1.md
      ARL_Quorum_Input_Precedence_v0.1.md
      ARL_Target_File_Map_for_ester_clean_code_v0.1.md
      ARL_Runtime_Hook_Points_v0.1.md
      ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md
      ARL_Dispute_State_Persistence_v0.1.md
      ARL_Review_Task_Routing_v0.1.md
      ARL_Integration_Sequence_for_ester_clean_code_v0.1.md
      ARL_Do_Not_Implement_Yet_List_v0.1.md

      ARL_Package_Repository_Layout_Map_for_ester_clean_code_v0.1.md
      ARL_Zenodo_Zip_and_Licensing_Notes_for_ester_clean_code_v0.1.md

      pdf/
        README.txt
      hashes/
        README.txt
      zenodo/
        README.txt
```

---

## 4. Why this layout

### 4.1 Why under `docs/architecture/`
Because this package is:
- architecture-facing,
- implementation-facing,
- and repo-facing,

but not itself executable code.

### 4.2 Why not inside `modules/`
Because the package explains how code should be changed.
It is not the code.

### 4.3 Why not mix into existing glitch-stack subtree
Because ARL deserves its own clean surface.
It should stay bridgeable to the glitch stack, but not disappear inside it.

---

## 5. Reading order

Recommended reading order inside the package:

1. `README.md`
2. `INDEX.md`
3. `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.md`
4. `ARL_Target_File_Map_for_ester_clean_code_v0.1.md`
5. `ARL_Runtime_Hook_Points_v0.1.md`
6. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
7. `ARL_Dispute_State_Persistence_v0.1.md`
8. `ARL_Review_Task_Routing_v0.1.md`
9. `ARL_Freeze_State_Machine_v0.1.md`
10. `ARL_Witness_Event_Binding_v0.1.md`
11. `ARL_Quorum_Input_Precedence_v0.1.md`
12. `ARL_Integration_Sequence_for_ester_clean_code_v0.1.md`
13. `ARL_Do_Not_Implement_Yet_List_v0.1.md`
14. `DOC_MAP.md`

---

## 6. Discoverability rule

The ECC-facing ARL package should be visible from the default branch.

That means:
- at least one repo-visible pointer in a higher-level doc,
- package README present,
- package INDEX present,
- and no reliance on direct file links only.

The package must be discoverable by an ordinary reader,
not only by someone who already knows the exact path.

---

## 7. Future PDF layer

The future `pdf/` subdirectory should contain human-corrected PDF renders of the key package files.

Recommended first PDF set:

- `ARL_Implementation_Bridge_to_ester_clean_code_v0.1.pdf`
- `ARL_Freeze_State_Machine_v0.1.pdf`
- `ARL_Witness_Event_Binding_v0.1.pdf`
- `ARL_Quorum_Input_Precedence_v0.1.pdf`
- `ARL_Target_File_Map_for_ester_clean_code_v0.1.pdf`
- `ARL_Runtime_Hook_Points_v0.1.pdf`
- `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.pdf`
- `ARL_Dispute_State_Persistence_v0.1.pdf`
- `ARL_Review_Task_Routing_v0.1.pdf`
- `ARL_Integration_Sequence_for_ester_clean_code_v0.1.pdf`
- `ARL_Do_Not_Implement_Yet_List_v0.1.pdf`

---

## 8. Future integrity layer

The future `hashes/` subdirectory should contain, at minimum:

- `SHA256SUMS_arl_ecc_v0.1.txt`

That manifest should hash:
- all canonical Markdown files in the package,
- all human-facing PDF files,
- and optionally package-level helper files.

---

## 9. Future Zenodo helper layer

The future `zenodo/` subdirectory may contain:
- deposit notes,
- metadata helpers,
- ZIP preparation notes,
- and future deposit manifests.

This layer is deposit-facing.
It should not become a second package home.

---

## 10. Explicit bridge

**ARL normative layer ↔ ECC implementation bridge package ↔ future code integration**

---

## 11. Hidden bridges

### 11.1 DEA / EA standing
Standing remains structurally present in the package but does not need its own giant subtree here.

### 11.2 SER-FED anti-capture
The package layout must not imply that `ester-clean-code` is the new sovereign home of ARL.
It is a bridge package, not a coronation.

---

## 12. Earth paragraph

On a real warehouse floor, if the dispute procedures are scattered between a clipboard near the loading dock, a sticky note in the office, and a PDF hidden on someone’s laptop, then the process is already broken. A clean repository layout is the software equivalent of keeping the binder in one labeled cabinet where the next shift can actually find it.
