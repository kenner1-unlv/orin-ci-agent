#!/usr/bin/env bash
set -u

section() {
  printf '\n=== %s ===\n' "$1"
}

section OS
cat /etc/os-release

section JETPACK
dpkg-query -W -f='${Package} ${Version}\n' nvidia-jetpack nvidia-l4t-core 2>/dev/null || true

section PYTHON
command -v python3 || true
python3 --version 2>/dev/null || true
python3 -m pip --version 2>/dev/null || true

section CUDA
command -v nvcc || true
nvcc --version 2>/dev/null || true
if [[ -f /usr/local/cuda/version.json ]]; then
  cat /usr/local/cuda/version.json
fi

section ROS
if [[ -d /opt/ros ]]; then
  find /opt/ros -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
else
  echo not-installed-under-/opt/ros
fi
find "$HOME" -maxdepth 4 -type f -name setup.bash -path '*install*' -print 2>/dev/null | head -30

section CONTAINERS
docker --version 2>/dev/null || true
containerd --version 2>/dev/null || true

section STORAGE
df -h / "$HOME" /data

section MEMORY
free -h

section WORKSPACES
find "$HOME" -maxdepth 3 -type d \( -name '*_ws' -o -name '*workspace*' -o -name Orinbot \) -print 2>/dev/null | sort
