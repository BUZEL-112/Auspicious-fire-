#!/usr/bin/env bash
# ==============================================================================
# Script to create a Google Colab T4 instance via Colab CLI from WSL,
# pull origin repository, and execute end-to-end testing.
# ==============================================================================
set -euo pipefail

SESSION_NAME="${1:-fashion-pipeline-t4}"
REPO_URL="https://github.com/BUZEL-112/Auspicious-fire-.git"
BRANCH="feat/colab-local-runner"

export PATH="$HOME/.local/bin:$PATH"

echo "=== [1/4] Ensuring google-colab-cli is installed ==="
if ! command -v colab &>/dev/null; then
    echo "Installing google-colab-cli..."
    pip install -q google-colab-cli
fi

echo "=== [2/4] Provisioning Colab instance with T4 GPU ==="
echo "Creating session '$SESSION_NAME' with GPU T4..."
colab new --gpu T4 -s "$SESSION_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [3/4] Executing bootstrap and pipeline test suite on T4 GPU ==="
colab exec -s "$SESSION_NAME" --timeout 1800 -f "$SCRIPT_DIR/t4_bootstrap.py"

echo "================================================================="
echo "Colab T4 testing completed successfully."
echo "To connect interactively, run: colab console -s $SESSION_NAME"
echo "To terminate the instance when finished, run: colab stop -s $SESSION_NAME"
echo "================================================================="
