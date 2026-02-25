# Relizy
1) python scripts/version bump.po <major|minor|patch>to — update VERSION and suggest a tag.
2) `git tag vX.Y.Z && git push --tags` — triggerit GH workflow `release.yml`.
3) V reliz popadut: obraz (ghcr), SBOM (spdx), podpis cosign, CHANGELOG.md.
