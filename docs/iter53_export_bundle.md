# Iter53: L4W Export Bundle + auditor_verify_bundle.py

## What the bundle contains
Directory bundle layout:

- `manifest.json`
- `hashes/SHA256SUMS.txt`
- `hashes/manifest.sha256`
- `keys/l4w_public.pem` (if available)
- `keys/evidence_public.pem` (if available)
- `keys/keys_fingerprint.json`
- `l4w/chains/quarantine_clear/<agent>.jsonl`
- `l4w/envelopes/quarantine_clear/<agent>/<envelope>.json`
- `l4w/disclosures/<envelope_hash>.json` (optional)
- `refs/evidence_index.json`
- `refs/evidence_files/...` (optional)
- `refs/cross_refs.json` (optional, FULL)
- `notes/README_AUDIT.md`
- `notes/PROFILE.md`

By default, evidence files are excluded for privacy. Only evidence refs are exported in `refs/evidence_index.json`.

## Export
Directory:
```powershell
python -B tools/export_audit_bundle.py --agent-id <id> --out D:\out\bundle --profile BASE --json
```

Zip:
```powershell
python -B tools/export_audit_bundle.py --agent-id <id> --out D:\out\bundle --zip --profile BASE --json
```

Useful flags:
- `--include-disclosures`
- `--include-evidence-files`
- `--include-cross-refs`
- `--max-records N`
- `--persist-dir PATH`

## Verify
```powershell
python -B tools/auditor_verify_bundle.py --bundle D:\out\bundle --profile BASE --json
python -B tools/auditor_verify_bundle.py --bundle D:\out\bundle.zip --profile HRO --json
python -B tools/auditor_verify_bundle.py --bundle D:\out\bundle --profile FULL --json
```

Optional external paths:
- `--pubkey-l4w PATH`
- `--pubkey-evidence PATH`
- `--evidence-dir PATH`
- `--events PATH`
- `--volition PATH`
- `--allow-missing-evidence`

## Profile behavior in bundle context
- `BASE`: verifies manifest/tree hashes, chain continuity, envelope hashes/signatures, refs consistency.
- `HRO`: `BASE` + evidence signature/payload checks. Requires evidence files in bundle (or external evidence dir), unless `--allow-missing-evidence`.
- `FULL`: `HRO` + cross-layer refs (either `refs/cross_refs.json` or external `--events` + `--volition`). If missing, fails with `FULL_REFS_MISSING` unless explicit allow flag is used.

## Exit codes
- `0` PASS
- `2` FAIL
- `3` WARN-only (BASE only)
