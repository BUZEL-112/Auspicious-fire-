#!/usr/bin/env bash
# ==============================================================================
# Script to create a Google Colab CPU instance via Colab CLI from WSL,
# pull origin repository, and execute end-to-end testing.
# ==============================================================================
set -euo pipefail

SESSION_NAME="${1:-fashion-cpu}"

export PATH="$HOME/.local/bin:$PATH"

echo "=== [1/3] Ensuring google-colab-cli is installed ==="
if ! command -v colab &>/dev/null; then
    echo "Installing google-colab-cli..."
    pip install -q google-colab-cli
fi

echo "=== [2/3] Provisioning Colab instance with CPU ==="
echo "Creating session '$SESSION_NAME' with CPU..."
colab new -s "$SESSION_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [3/3] Executing bootstrap and pipeline test suite on CPU ==="
colab exec -s "$SESSION_NAME" --timeout 1800 -f "$SCRIPT_DIR/colab_bootstrap.py"

echo "================================================================="
echo "Colab CPU testing completed successfully."
echo "To connect interactively, run: colab console -s $SESSION_NAME"
echo "To terminate the instance when finished, run: colab stop -s $SESSION_NAME"
echo "================================================================="
