# Ester Clean Code

> **Ester is not a "chatbot".**  
> This repository publishes a **clean-code** core for a long-lived, local-first entity designed for **accountable action under real constraints**.

## What This Repository Is
- **Public clean-code core** (no personal data, no runtime state).
- A codebase built around **operational accountability** (identity, privileges, auditability).
- A practical implementation direction aligned with:
  - **c = a + b** (a responsible human anchor + procedures/constraints -> a long-lived accountable entity)
  - **L4 (Reality Boundary)** as first-class safety: physics + operational constraints.

## What This Repository Is Not
- Not a "general chatbot for conversation".
- Not a promise of autonomy.
- Not a cloud/SaaS product template.
- Not a dump of private memory, logs, keys, or personal datasets.

## Conceptual Anchors (Bridges)
**Explicit bridge (operational):**  
Every privileged action must map to **identity**, **auditable privileges**, and a **tamper-evident witness trail**.

**Hidden bridges (short):**
- **Cybernetics (Ashby):** control fails when regulator variety is lower than disturbance variety.
- **Information theory (Cover and Thomas):** ambiguity lowers signal and coordination capacity.

**Earth paragraph (engineering):**  
Long-lived systems pay the entropy tax: fans fail, disks fill, clocks drift, keys leak, and dependencies decay.  
So Ester is designed to be **fail-closed**: uncertainty degrades into safe behavior, not confident risk.

## L4W Alignment (What "L4W Norms" Mean Here)
This codebase follows a **witness-first** safety posture:
- verified identity for who may act,
- explicit, least-privilege capability grants,
- logged escalation + human veto,
- hard budgets (time / spend / rate),
- tamper-evident records (hash-friendly logs),
- clear challenge windows for disputed actions.

Details: `docs/L4W_ALIGNMENT.md`

## Repository Map
- `ESTER/` - application routes and core runtime surface.
- `modules/` - internal modules and subsystems.
- `docs/` - documentation pack (start here if you are new).
- `logo/` - branding assets (separate rights; see trademark section).
- `tools/` - local safety utilities (repository scanner).

Start here: `docs/README.md`

## Quick Start (Local, Minimal)
> The project is local-first; do not add secrets to the repository.

1. Create a virtual environment and install dependencies (adjust to your toolchain):

```bash
python -m venv .venv
# Windows
.venv\Scripts\pip install -r requirements.txt
# Linux/macOS
source .venv/bin/activate && pip install -r requirements.txt
```

2. Run basic sanity:

```bash
python -m compileall ESTER
python -m compileall modules
```

3. Before publishing changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

More: `docs/QUICKSTART.md`

## Security
- Vulnerability reporting: `SECURITY.md`
- No secrets policy: `.env`, keys, logs, `data/`, and `state/` must never be committed.

## License and Trademark
- Code: GNU AGPL-3.0-or-later (`LICENSE`)
- Notices: `NOTICE`
- Trademark/branding: `TRADEMARK.md`
- Logos: `logo/LICENSE` (separate rights)

## Related Public Corpus (Context)
- AGI v1.1 (Protocol L4 + architecture pack): https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- Reality-Bound AI (L4) notes: https://github.com/Kot141078/ester-reality-bound
- SER (c = a + b protocol spec): https://github.com/Kot141078/sovereign-entity-recursion
