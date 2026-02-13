#!/bin/sh
cd "$(dirname "$0")/.."
MODE="${1:-local}"
./scripts/build.sh "$MODE"
cmake --build build --target release
ls -lh build/bin/buildroot-agent
