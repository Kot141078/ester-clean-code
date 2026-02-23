# Iter56: Publisher Roster Transparency Log

## What It Is

`publisher_roster_log.jsonl` is an append-only governance chain for publisher roster changes.
Each line is a signed event with:

- `prev_hash` (chain link)
- `entry_hash` (canonical digest of entry body)
- `sig_entry` (roster-root signature over `entry_hash`)
- `publication` reference to a concrete roster snapshot

This turns roster updates from mutable config edits into auditable, tamper-evident history.

## Data Layout

Under `PERSIST_DIR/keys`:

- `publisher_roster.json`
- `publisher_roster_log.jsonl`
- `publisher_roster_log_head.json`
- `roster_publications/<ts>_<bodysha8>/publisher_roster.json`
- `roster_publications/<ts>_<bodysha8>/publisher_roster.sha256`

## Publish Flow

Use `tools/publisher_roster_publish.py` to publish a signed roster snapshot and append a log entry.

Example:

```powershell
python -B tools/publisher_roster_publish.py `
  --persist-dir .\data `
  --roster .\data\keys\publisher_roster.json `
  --roster-root-privkey .\data\keys\roster_root_private.pem `
  --roster-root-pubkey .\data\keys\roster_root_public.pem `
  --op update `
  --reason "rotate signer"
```

## Manage Tool Behavior (Fail-Closed)

`tools/publisher_roster_manage.py` mutating commands (`init`, `add-key`, `retire-key`, `revoke-key`) now:

1. Build and sign new roster in temp file.
2. Publish snapshot + log entry.
3. Replace working roster atomically only if publish succeeds.

In Slot B, publish-to-log is forced. If publish fails, roster file is not overwritten.

## Verify Flow

Standalone verifier:

```powershell
python -B tools/auditor_verify_roster_log.py `
  --persist-dir .\data `
  --pubkey-roster-root .\data\keys\roster_root_public.pem `
  --require-publications `
  --json
```

Optional target check:

```powershell
python -B tools/auditor_verify_roster_log.py `
  --persist-dir .\data `
  --pubkey-roster-root .\data\keys\roster_root_public.pem `
  --find-body-sha256 <sha256>
```

## Rotation / Revoke Semantics In Log

Operations are represented by `op`:

- `init`
- `update`
- `rotate`
- `retire`
- `revoke`

Auditors can reconstruct key lifecycle from ordered entries and referenced roster snapshots.

## Auditor Bundle Integration

- `tools/export_audit_bundle.py --include-roster-log --roster-log-last N`
  copies log head and last `N` entries into `bundle/keys/`.
- `tools/auditor_verify_bundle.py --verify-roster-log`
  verifies bundled roster log chain and checks that bundle roster digest exists in log.

## Error Codes

- `LOG_MISSING`
- `LOG_PARSE_ERROR`
- `LOG_ENTRY_HASH_MISMATCH`
- `LOG_CHAIN_BROKEN`
- `LOG_SIG_INVALID`
- `LOG_PUBLICATION_MISSING`
- `LOG_PUBLICATION_SHA_MISMATCH`
- `LOG_TARGET_NOT_FOUND`
- `ROSTER_LOG_TARGET_NOT_FOUND`

## Earth Analogy

This is a stitched paper shift-book for access control changes:

- `prev_hash` is the stitching,
- roster-root signature is the supervisor seal,
- publication snapshot is the attached written order.

You audit not only the current access list, but the provable sequence of how it changed.
