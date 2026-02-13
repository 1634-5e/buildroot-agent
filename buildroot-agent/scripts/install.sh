#!/bin/sh
cd "$(dirname "$0")/.."
MODE="${1:-local}"
./scripts/build.sh "$MODE"
DESTDIR="${2:-/tmp/buildroot-install}"
cmake --install build --prefix "$DESTDIR"
