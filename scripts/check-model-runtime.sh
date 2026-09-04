#!/usr/bin/env bash
set -u

for command_name in docker jetson-containers autotag git curl wget cmake make gcc g++ rg jq sha256sum; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '%-20s %s\n' "$command_name" "$(command -v "$command_name")"
  else
    printf '%-20s %s\n' "$command_name" missing
  fi
done

printf '\nDocker runtime:\n'
docker info --format 'runtimes={{json .Runtimes}} default={{.DefaultRuntime}}' 2>&1 || true

printf '\nNVIDIA devices:\n'
ls -1 /dev/nvhost-gpu /dev/nvmap 2>/dev/null || true

printf '\nExisting model storage:\n'
find /data/persistent-worker/models -mindepth 1 -maxdepth 2 -printf '%y %p %s bytes\n' 2>/dev/null | head -50

printf '\nROS state:\n'
systemctl is-active orin_stack.service 2>/dev/null || true
ps -eo comm,args --no-headers | grep -Ei '[r]os2|[r]oscore|[r]oslaunch|[p]oint_lio|[n]av2|[s]lam_toolbox' || true
