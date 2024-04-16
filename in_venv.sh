#!/usr/bin/env bash

VENV_DIR="$1"
shift 1

source "${VENV_DIR}/bin/activate"

$@
