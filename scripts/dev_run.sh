#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 -m backend.app --host 0.0.0.0 --port "${PHOTOEXIF_PORT:-9865}"
