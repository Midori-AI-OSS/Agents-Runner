#!/usr/bin/env bash
set -u

echo "[preflight] system: running: yay -Syu --noconfirm && yay -Yccc --noconfirm"

set +e

yay -Syu --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "[preflight] system: yay -Syu failed (exit $STATUS); continuing"
  exit 0
fi

yay -Yccc --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "[preflight] system: yay -Yccc failed (exit $STATUS); continuing"
fi

exit 0
