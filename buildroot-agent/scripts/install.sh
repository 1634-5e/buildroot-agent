#!/bin/sh
cd "$(dirname "$0")/.."
DESTDIR="${1:-/tmp/buildroot-install}"
cmake --install build --prefix "$DESTDIR"
