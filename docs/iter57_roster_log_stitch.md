# Iter57: Stitch Roster Log Anchor With L4W

## Why `roster_body_sha256` Is Not Enough

`roster_body_sha256` identifies roster content, but not the exact governance event in history.
Two different log positions can reference the same body digest.
Iter57 adds `roster_entry_hash` to bind trust policy to a specific append-only log entry.

## What `roster_entry_hash` Means

`roster_entry_hash` is the canonical hash of one roster-log entry.
It is the commit-like pointer to an exact point in the signed roster transparency chain.

## Export Behavior

`tools/export_audit_bundle.py` now anchors roster policy to a concrete log entry when roster policy is enforced.

Key flags:

- `--roster-entry-hash <hex64>`: explicit anchor override.
- `--anchor-roster-log` / `--no-anchor-roster-log`: enable/disable anchoring (Slot A can disable; Slot B is fail-closed when required).
- `--require-roster-log`: force strict log requirement.
- `--include-roster-log --roster-log-last N`: include head + log slice in bundle.

Manifest additions:

- `publisher_policy.roster_entry_hash`
- `publisher_policy.roster_log_head`
- `publisher_policy.roster_log_required`
- `roster_anchor` section (`ester.publisher.roster_anchor.v1`)

## Auditor Verification

`tools/auditor_verify_bundle.py` verifies:

1. Log chain validity (`ROSTER_LOG_INVALID` on failure).
2. Presence of anchor entry (`ROSTER_LOG_ENTRY_NOT_FOUND`).
3. `entry.body_sha256 == publisher_policy.roster_body_sha256` (`ROSTER_ANCHOR_BODY_MISMATCH`).
4. `entry.roster_id` consistency (`ROSTER_ANCHOR_ROSTER_ID_MISMATCH`).
5. `manifest.roster_anchor` consistency with actual log entry.

New controls:

- `--verify-roster-log`
- `--require-roster-entry-hash`
- `--allow-missing-roster-entry-hash` (BASE downgrade path)

## Envelope-Level Stitching

New envelopes can include:

```json
"roster_anchor": {
  "schema": "ester.publisher.roster_anchor_ref.v1",
  "entry_hash": "<hex64>",
  "body_sha256": "<hex64>",
  "roster_id": "<id>"
}
```

This field is embedded before envelope hash/signature, so it is integrity-protected by `envelope_hash`.

Verifier counters:

- `envelopes_roster_anchor.total`
- `envelopes_roster_anchor.with_anchor`
- `envelopes_roster_anchor.missing`
- `envelopes_roster_anchor.mismatch`
- `envelopes_roster_anchor.unknown_entry`

## Profile Policy

- `BASE`: missing roster anchor can be downgraded with `--allow-missing-roster-entry-hash`.
- `HRO`: missing envelope anchor warns; mismatches fail.
- `FULL`: missing envelope anchor fails; log/anchor mismatch fails.

## Error Codes

- `ROSTER_ENTRY_HASH_REQUIRED`
- `ROSTER_LOG_REQUIRED`
- `ROSTER_LOG_INVALID`
- `ROSTER_LOG_ENTRY_NOT_FOUND`
- `ROSTER_ANCHOR_BODY_MISMATCH`
- `ROSTER_ANCHOR_ROSTER_ID_MISMATCH`

## Troubleshooting

- Missing `--pubkey-roster-root` when log verification is required -> `ROSTER_LOG_REQUIRED`.
- Anchor hash present in policy but missing from provided log slice -> include larger `--roster-log-last` or full log.
- FULL profile failing on envelope anchor missing -> regenerate envelopes after enabling roster-anchor stitching.

## Bridges

- Explicit bridge (provenance): `roster_entry_hash` turns "who is trusted" into a verifiable history point, not just a state digest.
- Hidden bridge #1 (information theory): `entry_hash` is an index in the signed chain, adding addressability and preventing context swapping when body digests match.
- Hidden bridge #2 (Ashby cybernetics): trust control needs observable change trajectory, not only current state.

## Earth Paragraph

Think about it as a Git commit in an access-control ledger: `body_sha256` is file content, while `log_entry_hash` is the exact signed row in the stitched book of approvals. The auditor checks not only "does this roster look similar", but that this exact roster state existed at a concrete published point in history. If someone tries to rewrite access history retroactively, the log chain exposes it.
