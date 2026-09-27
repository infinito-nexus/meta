#!/bin/sh
# Param: $1  env file whose MIG_MTU is written (default: .env)
set -eu

ENV_FILE="${1:-.env}"
PYTHON="${PYTHON:-python3}"

# Refused rather than created: a file holding MIG_MTU alone starts no stack.
if [ ! -f "$ENV_FILE" ]; then
  echo "mig: no $ENV_FILE to write, run make .env first" >&2
  exit 1
fi

numeric() {
  case "$1" in
    '' | *[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

probe() {
  # The module call covers a virtualenv that holds the package without
  # putting its script on PATH.
  automtu "$@" 2>/dev/null || "$PYTHON" -m automtu "$@" 2>/dev/null || true
}

mtu="$(probe --print-mtu effective)"
source="automtu"

if ! numeric "$mtu"; then
  mtu="$(docker network inspect bridge \
    --format '{{index .Options "com.docker.network.driver.mtu"}}' 2>/dev/null || true)"
  source="the docker bridge"
fi

if ! numeric "$mtu"; then
  mtu=1500
  source="the ethernet default"
fi

if grep -q '^MIG_MTU=' "$ENV_FILE"; then
  sed -i "s/^MIG_MTU=.*/MIG_MTU=$mtu/" "$ENV_FILE"
else
  printf 'MIG_MTU=%s\n' "$mtu" >> "$ENV_FILE"
fi

echo "mig: compose network MTU $mtu, from $source"
