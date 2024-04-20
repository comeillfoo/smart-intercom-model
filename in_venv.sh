#!/usr/bin/env bash

ROOT="$1"
shift 1
VENV_DIR="$1"
shift 1
CMD="$@"

cd $ROOT || exit 2

source "${VENV_DIR}/bin/activate"

$CMD >/dev/null 2>&1 &
echo $!
