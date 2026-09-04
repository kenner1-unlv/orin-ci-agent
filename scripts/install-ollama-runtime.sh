#!/usr/bin/env bash
set -euo pipefail

readonly version='v0.32.15'
readonly tools='/data/persistent-worker/tools'
readonly base_archive="$tools/ollama-linux-arm64-$version.tar.zst"
readonly jetpack_archive="$tools/ollama-linux-arm64-jetpack6-$version.tar.zst"
readonly target="$tools/ollama-$version"

mkdir -p "$tools" /data/persistent-worker/models/ollama

download() {
  local name="$1"
  local destination="$2"
  local url="https://github.com/ollama/ollama/releases/download/$version/$name"
  if [[ ! -f "$destination" ]]; then
    curl --fail --location --continue-at - --output "$destination.part" "$url"
    mv "$destination.part" "$destination"
  fi
  sha256sum "$destination" | tee "$destination.sha256"
}

download 'ollama-linux-arm64.tar.zst' "$base_archive"
download 'ollama-linux-arm64-jetpack6.tar.zst' "$jetpack_archive"

if [[ ! -x "$target/bin/ollama" ]]; then
  rm -rf "$target"
  mkdir -p "$target"
  tar --zstd -xf "$base_archive" -C "$target"
  tar --zstd -xf "$jetpack_archive" -C "$target"
fi

ln -sfn "$target" "$tools/ollama-current"
"$tools/ollama-current/bin/ollama" --version
