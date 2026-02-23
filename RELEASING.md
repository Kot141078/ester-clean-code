# RELEASING

This repository uses GitHub Actions to build a distributable ZIP and attach it to a GitHub Release.

## One-time setup
1. Ensure `scripts/make_release.sh` exists and produces a file like `ester-YYYY.MM.DD-HHMM.zip` or `ester-<version>.zip`.
2. Ensure your presets and templates are in the paths used by the script.
3. Optional: create `CHANGELOG.md` and keep it updated.

## How to cut a release
1. Update version and changelog:
   ```bash
   VERSION=v1.0.0
   git commit -am "chore: release ${VERSION}"
   git tag -a "${VERSION}" -m "Release ${VERSION}"
   git push origin "${VERSION}"
   ```
2. The workflow `Release (build & upload)` will run automatically for tag `v*`.
3. When finished, the release ZIP will be attached to the GitHub Release page.

## Manual run
You can also trigger the workflow from the Actions tab via **Run workflow** (workflow_dispatch).
