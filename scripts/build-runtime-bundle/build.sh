#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGS=(--version "${1:-0.1.0}")

if [[ -n "${2:-}" ]]; then
  ARGS+=(--platform "$2")
fi

if [[ -n "${3:-}" ]]; then
  ARGS+=(--wheelhouse "$3")
fi

python3 "${SCRIPT_DIR}/build_runtime_bundle.py" "${ARGS[@]}"
