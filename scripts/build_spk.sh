#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="${ROOT}/build/spk"
DIST="${ROOT}/dist"
rm -rf "${BUILD}"; mkdir -p "${BUILD}/package" "${BUILD}/scripts" "${DIST}"
cp -R "${ROOT}/backend" "${ROOT}/frontend" "${BUILD}/package/"
[ ! -d "${ROOT}/vendor" ] || cp -R "${ROOT}/vendor" "${BUILD}/package/"
cp "${ROOT}/spk/INFO" "${BUILD}/INFO"
cp "${ROOT}/spk/scripts/start-stop-status" "${BUILD}/scripts/start-stop-status"
chmod +x "${BUILD}/scripts/start-stop-status"
(
  cd "${BUILD}/package"
  tar -czf "${BUILD}/package.tgz" .
)
rm -rf "${BUILD}/package"
(
  cd "${BUILD}"
  tar -cf "${DIST}/Gen8-PhotoExifReader-0.1.0-x86_64.spk" INFO package.tgz scripts
)
echo "Built: ${DIST}/Gen8-PhotoExifReader-0.1.0-x86_64.spk"
