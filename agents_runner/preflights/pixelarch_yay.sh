#!/usr/bin/env bash
set -u

echo "[preflight/yay][INFO] running: yay -Syu --noconfirm && yay -Yccc --noconfirm"

set +e

yay -Syu --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "[preflight/yay][WARN] yay -Syu failed (exit $STATUS); continuing"
  exit 0
fi

yay -Yccc --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "[preflight/yay][WARN] yay -Yccc failed (exit $STATUS); continuing"
fi

exit 0
