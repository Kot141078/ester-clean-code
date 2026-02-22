# Threat Model (Practical)

## Primary Risks
- secret leakage (tokens and keys),
- privilege drift (capabilities expanding silently),
- covert network access,
- audit gaps ("trust me, it happened"),
- task fragmentation across hidden agents,
- infinite retry loops or silent escalation.

## Controls (Repository Level)
- strict `.gitignore` allowlist posture,
- scanner: `tools/scan_repo.ps1`,
- explicit compile targets to avoid accidental junk trees,
- trademark separation to prevent fork impersonation.
