# Ester Clean Code — v0.2.4

## Summary

This release republishes the current `main` state as the new stable snapshot.
It replaces the outdated public `v0.2.3` download references with a fresh stable release tag instead of rewriting the old tag.

## Highlights

- Published a new stable tag from the current `main` branch state.
- Updated public download links in `README.md`, `MACHINE_ENTRY.md`, and `llms.txt` to point to `v0.2.4`.
- Included the public-safe document recall layer in the stable source snapshot:
  - `modules/memory/doc_lookup.py`
  - `modules/memory/doc_store.py`
  - `modules/memory/recent_docs.py`
  - `modules/rag/retrieval_router.py`
  - `tests/test_doc_lookup_semantic.py`
  - `tests/test_retrieval_router_doc_resolution.py`

## Security & Privacy

- The old `v0.2.3` release remains untouched for auditability.
- Stable-download links now point to a new release instead of mutating an existing published tag.
- No runtime state, local data, private artifacts, or repository-ignored files are included in the stable source archive.

## Verification

- `powershell -ExecutionPolicy Bypass -File .\tools\staged_doc_gate.ps1` -> PASS
- `python -m pytest tests/test_retrieval_router_doc_resolution.py -q` -> PASS
- `python -m pytest tests/test_doc_lookup_semantic.py -q` -> PASS

## Links

- AGI v1.1: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
