# Iter55: Publisher Roster + Multi-signer (2-of-3)

## Chto reshaet Iter55
- `publisher_roster.json` vvodit upravlyaemyy spisok doverennykh klyuchey publisher: `active`, `retired`, `revoked`, okna validnosti i rotatsiyu.
- Bundle teper mozhet soderzhat neskolko podpisey `publisher_sigs` i politiku `publisher_policy` s porogom (`threshold/of`), naprimer `2-of-3`.
- Auditor proveryaet ne tolko podpisi bundle, no i doverennost roster cherez trust anchor `roster-root`.

## Trust Anchor
- Roster podpisyvaetsya klyuchom `roster-root` (`ester.publisher.roster_sig.v1`).
- Auditor dolzhen poluchit `roster-root` public key (`--pubkey-roster-root` ili `ESTER_ROSTER_ROOT_PUBKEY_PATH`).
- Bez doverennogo `roster-root` enforce-rezhim schitaetsya nedoverennym i valitsya fail-closed.

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

## Proverka bundle auditorom
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

## Tipovye oshibki
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
- `ROSTER_SIG_INVALID`: proverit `roster-root` pubkey i podpis roster posle poslednego izmeneniya.
- `ROSTER_KEY_REVOKED`: klyuch otozvan na moment `manifest.created_ts`; pereeksportirovat bundle aktualnymi klyuchami.
- `MULTISIG_THRESHOLD_NOT_MET`: uvelichit chislo aktivnykh signer ili ponizit policy threshold (esli eto dopustimo politikoy).

## Bridges
- Explicit bridge (safety governance): roster + revoke + `2-of-3` ubirayut single-point-of-failure podpisi.
- Hidden bridge #1 (infoteoriya): threshold-podpis snizhaet risk odinochnogo kanala oshibki.
- Hidden bridge #2 (anatomiya/inzheneriya): eto rezervirovanie, gde odin otkaz ne lomaet ves kontur doveriya.

## Earth paragraph
Eto kak dva klyucha ot seyfa (`2-of-3`): odin klyuch ukrali, no seyf vse ravno ne otkryt.  
Roster — eto zhurnal dopuska: kto seychas v smene (`active`), kto vyveden (`retired`), kogo srochno otozvali (`revoked`).  
Audit v itoge opiraetsya ne na obeschaniya, a na proveryaemye pravila, kotorye perezhivayut otdelnye mashiny i lyudey.
