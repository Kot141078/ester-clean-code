# Iter55: Publisher Roster + Multi-signer (2-of-3)

## What Iter55 decides
- epublisher_roster.jsonyo introduces a manageable list of trusted publisher keys: eaktivee, eretyredyo, erevokedyo, validity windows and rotation.
- A bundle can now contain multiple epublisher_signature signatures and epublisher_police policy with a threshold (etnreshold/ofo), for example е2-of-3е.
- The auditor checks not only the signatures of the Bundle, but also the Roster's power of attorney through Trust Anchor Yoroster-Roote.

## Trust Anchor
- The roaster is signed with the key yoester-rooto (yoester.publisher.roster_sig.v1yo).
- The auditor must receive a yo-rooster-roote public key (yo--pubkeys-roster-roote or yoESTER_ROSTER_ROOT_PYUBKEY_PATNyo).
- Without a trusted yoster root, the enforce mode is considered untrusted and the closed file crashes.

## Formaty
- `manifest.publisher_sigs`: massiv podpisey formata Iter54 (`ester.l4w.publisher_sig.v1`).
- `manifest.publisher_policy`:
  - `schema: ester.publisher.bundle_policy.v1`
  - `threshold`, `of`
  - `roster_body_sha256`
  - `roster_id`
  - `enforce_roster`
- Snapshot roster v bundle:
  - `keys/publisher_roster.json`
  - `keys/publisher_roster.sha256`

## Eksport signed bundle (multi-signer)
```powershell
python -B tools/export_audit_bundle.py `
  --agent-id <agent_id> `
  --out <bundle_dir> `
  --multi-signer `
  --publisher-roster <persist\keys\publisher_roster.json> `
  --pubkey-roster-root <persist\keys\roster_root_public.pem> `
  --profile BASE `
  --json
```

## Bundle audit by auditor
```powershell
python -B tools/auditor_verify_bundle.py `
  --bundle <bundle_dir_or_zip> `
  --profile BASE `
  --pubkey-roster-root <persist\keys\roster_root_public.pem> `
  --json
```

## Roster CLI
```powershell
python -B tools/publisher_roster_manage.py init --out <roster.json> --threshold 2 --of 3 --roster-id <id> --roster-root-privkey <priv.pem> --roster-root-pubkey <pub.pem>
python -B tools/publisher_roster_manage.py add-key --roster <roster.json> --key-id publisher-A --pubkey <publisher_A_public.pem> --status active
python -B tools/publisher_roster_manage.py retire-key --roster <roster.json> --key-id publisher-A --not-after-ts <ts>
python -B tools/publisher_roster_manage.py revoke-key --roster <roster.json> --key-id publisher-A --revoked-ts <ts> --reason "compromised"
python -B tools/publisher_roster_manage.py show --roster <roster.json>
```

## Typical errors
- `ROSTER_REQUIRED`
- `ROSTER_ROOT_PUBKEY_REQUIRED`
- `ROSTER_SIG_INVALID`
- `ROSTER_DIGEST_MISMATCH`
- `ROSTER_KEY_UNKNOWN`
- `ROSTER_KEY_NOT_ACTIVE`
- `ROSTER_KEY_REVOKED`
- `MULTISIG_THRESHOLD_NOT_MET`
- `LEGACY_SINGLE_SIG_NOT_ALLOWED`

## Troubleshooting
- YOROSTER_SIG_INVALIDE: check the Yoroster-roote bobkeys and roster signature after the last change.
- yoROSTER_KEY_REVOKEDYO: the key was revoked at the time of yomanifest.created_tso; re-export the bundle with current keys.
- EMULTISEG_THRESHOLD_NOT_METH: increase the number of active signers or lower the police threshold (if allowed by policy).

## Bridges
- Explicit bridge (safety governance): roster + revoke + `2-of-3` ubirayut single-point-of-failure podpisi.
- Hidden bridge #1 (info theory): three-hold signature reduces the risk of a single error channel.
- Hidden Bridge #2 (Anatomy/Engineering): This is redundancy where one failure does not break the entire circuit of trust.

## Earth paragraph
It's like two keys to a safe (е2-of-3е): one key was stolen, but the safe still cannot be opened.
The roster is a log of admissions: who is currently on shift (yoaktivee), who is withdrawn (yoryetyredyo), who has been urgently recalled (yerevkedyo).
Auditing ultimately rests not on promises, but on verifiable rules that outlive individual machines and people.
