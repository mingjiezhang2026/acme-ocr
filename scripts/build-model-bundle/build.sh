#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGS=(--version "${1:-0.1.0}" --model-key "${2:-ppocr-zh}")

python3 "${SCRIPT_DIR}/build_model_bundle.py" "${ARGS[@]}"

