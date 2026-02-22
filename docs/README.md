# Documentation Map

## Start Here

- `QUICKSTART.md` explains local setup, checks, and publish hygiene.
- `ARCHITECTURE.md` maps trust boundaries, modules, and execution flow.
- `L4W_ALIGNMENT.md` states witness-first norms and fail-closed posture.
- `THREAT_MODEL.md` lists concrete risks and repository-level controls.
- `RELEASE_CHECKLIST.md` is the release gate before commit and push.

## Repository Claims

- Ester is not a chatbot; it is an accountable operations core.
- Safety posture is Reality-Bound (L4): constraints are first-class inputs.
- c = a + b: a responsible human anchor plus bounded procedures.
- Privileged actions must be attributable and reviewable.

## What Is Explicitly In Scope

- Local-first workflows.
- Auditable privilege use.
- Witness trail that is tamper-evident and hash-friendly.
- Budget controls for time, spend, and rate.
- Veto/challenge windows for contested actions.

## What Is Not Claimed

- No autonomy promises.
- No perfect containment guarantees.
- No hidden background task guarantees in this repo.

## Navigation Tips

- If you are onboarding: read `QUICKSTART.md`, then `ARCHITECTURE.md`.
- If you are reviewing policy: read `L4W_ALIGNMENT.md` and `THREAT_MODEL.md`.
- If you are preparing release: complete `RELEASE_CHECKLIST.md` line by line.
