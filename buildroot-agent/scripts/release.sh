#!/bin/sh
cd "$(dirname "$0")/.."
./scripts/build.sh
cmake --build build --target release
ls -lh build/bin/buildroot-agent
