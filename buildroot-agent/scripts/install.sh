#!/bin/sh
cd "$(dirname "$0")/.."
MODE="${1:-local}"
./scripts/build.sh "$MODE"
DESTDIR="${2:-/opt/buildroot-agent}"
cmake --install build --prefix "$DESTDIR"
