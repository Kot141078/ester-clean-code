# Relizy
1) `python scripts/version_bump.py <major|minor|patch>` — obnovit VERSION i predlozhit teg.
2) `git tag vX.Y.Z && git push --tags` — triggerit GH workflow `release.yml`.
3) V reliz popadut: obraz (ghcr), SBOM (spdx), podpis cosign, CHANGELOG.md.
