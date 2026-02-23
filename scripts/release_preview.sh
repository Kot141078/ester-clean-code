#!/usr/bin/env bash
set -euo pipefail

# One-shot reliz predprosmotra (v0.1-preview):
#  - generiruet CHANGELOG.md
#  - sobiraet SBOM (esli ustanovlen syft)
#  - upakovyvaet artefakt (tar.gz)
#  - sozdaet git-teg v0.1-preview (esli net)
#  - pytaetsya vygruzit na WebDAV / S3 / cherez storage.uploader (esli dostupno)

VERSION="${VERSION:-v0.1-preview}"
ARTIFACT_NAME="ester-${VERSION#v}.tar.gz"
SBOM="sbom-${VERSION}.spdx.json"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[release] Generate CHANGELOG.md"
python3 scripts/changelog_from_commits.py > CHANGELOG.md

if ! git rev-parse "$VERSION" >/dev/null 2>&1; then
  echo "[release] Create git tag $VERSION"
  git add CHANGELOG.md
  git commit -m "chore: update CHANGELOG for ${VERSION}" || true
  git tag "$VERSION"
fi

echo "[release] Build SBOM (if syft available)"
if command -v syft >/dev/null 2>&1; then
  syft packages dir:. -o spdx-json > "$SBOM"
  echo "[release] SBOM saved: $SBOM"
else
  echo "[release] syft not found, skipping SBOM"
  : > "$SBOM"  # sozdadim pustoy fayl dlya sovmestimosti shagov
fi

echo "[release] Pack artifact: $ARTIFACT_NAME"
# Isklyuchim .git i tyazhelye artefakty, mozhno rasshiryat
tar --exclude=".git"     --exclude="**/__pycache__"     --exclude="**/.pytest_cache"     -czf "$ARTIFACT_NAME" .

echo "[release] Try upload via storage.uploader (if present)"
if python3 - <<'PY'
try:
    import storage.uploader as up  # noqa: F401
    print("OK")
except Exception:
    print("NO")
PY
then
  python3 - <<PY
from storage import uploader as up
up.upload_paths(
    files=["CHANGELOG.md","${SBOM}","${ARTIFACT_NAME}"],
    channels=["auto"]
)
print("uploader: done")
PY
else
  echo "[release] storage.uploader not available, trying WebDAV/S3 fallback"
  if [[ -n "${WEBDAV_URL:-}" && -n "${WEBDAV_USER:-}" && -n "${WEBDAV_PASSWORD:-}" ]]; then
    echo "[release] WebDAV upload -> ${WEBDAV_URL}"
    for f in "CHANGELOG.md" "${SBOM}" "${ARTIFACT_NAME}"; do
      curl -sf --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}"         -T "$f" "${WEBDAV_URL%/}/$f"
      echo "[release] uploaded $f to WebDAV"
    done
  elif command -v aws >/dev/null 2>&1 && [[ -n "${S3_BUCKET:-}" ]]; then
    PREFIX="${S3_PREFIX:-releases/${VERSION}/}"
    for f in "CHANGELOG.md" "${SBOM}" "${ARTIFACT_NAME}"; do
      aws s3 cp "$f" "s3://${S3_BUCKET}/${PREFIX}$f"
      echo "[release] uploaded $f to s3://${S3_BUCKET}/${PREFIX}$f"
    done
  else
    echo "[release] No uploader configured (set storage.uploader or WEBDAV_* or aws S3_BUCKET)"
  fi
fi

echo "[release] Done."
