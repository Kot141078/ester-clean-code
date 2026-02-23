# Iter50: Integrity Stack v1

## Scope
- Evidence packet now supports Ed25519 signature verification.
- Template/capability integrity is enforced via SHA256 manifest.
- Agent spec writes are guarded by trusted write journal + spec guard index.

## A/B Behavior
- Slot A: observe-only for signature/manifest/spec tamper checks (warnings in status/output).
- Slot B: enforce mode:
  - evidence signature required for `drift.quarantine.clear`;
  - integrity manifest mismatch denies create/enqueue/run;
  - spec tamper without trusted write denies enqueue/run and sets quarantine.
- Repeated verifier errors auto-force Slot A in-process and are reflected in status.

## Paths
- Manifest: `data/integrity/template_capability_SHA256SUMS.json`
- Integrity events: `data/integrity/events.jsonl`
- Spec guard: `data/integrity/spec_guard.json`
- Evidence keys (default): `data/keys/evidence_ed25519_private.pem`, `data/keys/evidence_ed25519_public.pem`

## Bridges
- Explicit bridge (cryptographic accountability): SHA256 fixes bytes, Ed25519 fixes author intent; together this is a signed decision act.
- Hidden bridge #1 (information theory): small digests and bounded manifests maximize control with minimal bandwidth and runtime overhead.
- Hidden bridge #2 (physiology): skin/immune barrier analogy; tamper is detected at ingress before execution.

## Earth Paragraph
Eto kak tri sloya na realnom obekte: (1) akt proverki s podpisyu (Ed25519), (2) plomby na shkafakh s instrumentami (manifest na templates/capabilities), (3) zapret «lezt v schitok» bez zapisi v zhurnal (spec-guard). Vmeste eto ubiraet klass tikhikh pravok, iz kotorykh potom rozhdayutsya strashilki pro II.

## Tools
- `python -B tools/generate_ed25519_keypair.py`
- `python -B tools/build_integrity_manifest.py`
- `python -B tools/evidence_signature_smoke.py`
- `python -B tools/integrity_manifest_smoke.py`
- `python -B tools/spec_guard_smoke.py`
- `powershell -File tools/harden_persist_acl.ps1` (best effort, rc=0 on warnings)

