# Iter54: Bundle Signing (Publisher Signature)

## What is signed
Bundle publisher signs only the deterministic tree hash:

- message domain: `ester.l4w.bundle_tree_sha256.v1`
- signed bytes: `b"ester.l4w.bundle_tree_sha256.v1:" + bundle_tree_sha256_hex`

This gives provenance for the whole exported bundle without signing each file separately.

## Manifest field
`manifest.json` includes:

```json
"publisher_sig": {
  "schema": "ester.l4w.publisher_sig.v1",
  "alg": "ed25519",
  "key_id": "publisher-default",
  "msg": "ester.l4w.bundle_tree_sha256.v1",
  "signed": "<bundle_tree_sha256 hex>",
  "pub_fingerprint": "<sha256(raw_pubkey)>",
  "sig_b64": "<base64 signature>"
}
```

Invariant:
- `publisher_sig.signed` must equal `manifest.hashes.bundle_tree_sha256`.

## Key management
Private key is never copied to bundle.

Env:
- `ESTER_BUNDLE_PUBLISHER_PRIVKEY_PATH`
- `ESTER_BUNDLE_PUBLISHER_PUBKEY_PATH`
- `ESTER_BUNDLE_PUBLISHER_KEY_ID` (default `publisher-default`)
- `ESTER_BUNDLE_PUBLISHER_SIGNING` (default `1`)

Export CLI flags:
- `--sign-publisher` / `--no-sign-publisher`
- `--publisher-privkey PATH`
- `--publisher-pubkey PATH`
- `--publisher-key-id STR`
- `--include-publisher-pubkey`

## Export example
```powershell
python -B tools/export_audit_bundle.py `
  --agent-id <id> `
  --out D:\out\bundle `
  --sign-publisher `
  --include-publisher-pubkey `
  --json
```

## Verify example
```powershell
python -B tools/auditor_verify_bundle.py --bundle D:\out\bundle --profile BASE --json
python -B tools/auditor_verify_bundle.py --bundle D:\out\bundle.zip --profile HRO --json
```

Verifier options:
- `--pubkey-publisher PATH`
- `--require-publisher-sig`
- `--allow-missing-publisher-sig` (BASE only warning mode)

## Profile enforcement
- `BASE`: publisher signature required by default; can be downgraded only with `--allow-missing-publisher-sig` (warning).
- `HRO/FULL`: publisher signature strictly required (fail-closed).

## Typical errors
- `PUBLISHER_SIG_REQUIRED`
- `PUBLISHER_PUBKEY_MISSING`
- `PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH`
- `PUBLISHER_SIG_SIGNED_MISMATCH`
- `PUBLISHER_SIG_INVALID`
- `BUNDLE_TREE_HASH_MISMATCH`
- `ED25519_UNAVAILABLE`

## Why this exists
- Explicit bridge: publisher signature adds “who produced this proof bundle” on top of integrity checks.
- Hidden bridge #1 (information theory): one signed tree hash compresses full bundle state.
- Hidden bridge #2 (Ashby cybernetics): control loop needs observable + immutable channel; signature makes delivery channel auditable.

## Earth paragraph
It's like a seal on a sealed envelope: inside is a list of seals (hashes), and outside is the sender's signature.
Auditor beret bundle, proveryaet pechat (`publisher_sig`), sveryaet plomby (`tree hash` i `SHA256SUMS`) i srazu vidit podmenu dazhe pri vneshne “akkuratnom” soderzhimom.
