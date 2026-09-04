#!/usr/bin/env bash
set -euo pipefail

readonly JETSON_CONTAINERS_REPO='https://github.com/dusty-nv/jetson-containers.git'
readonly JETSON_CONTAINERS_COMMIT='70c149aea6126594153ef7690ec4890f8f396518'
readonly TOOL_ROOT='/data/persistent-worker/tools'
readonly CHECKOUT="$TOOL_ROOT/jetson-containers"

mkdir -p "$TOOL_ROOT"

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$JETSON_CONTAINERS_REPO" "$CHECKOUT"
fi

git -C "$CHECKOUT" fetch --tags origin
git -C "$CHECKOUT" checkout --detach "$JETSON_CONTAINERS_COMMIT"

printf 'Pinned jetson-containers checkout: '
git -C "$CHECKOUT" rev-parse HEAD
printf 'Run the audited upstream installer once with:\n  sudo bash %s/install.sh\n' "$CHECKOUT"
