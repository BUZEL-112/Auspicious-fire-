#!/usr/bin/env bash
# ==============================================================================
# Script to create a Google Colab T4 instance via Colab CLI from WSL,
# pull origin repository, and execute end-to-end testing.
# ==============================================================================
set -euo pipefail

SESSION_NAME="${1:-fashion-pipeline-t4}"
REPO_URL="https://github.com/BUZEL-112/Auspicious-fire-.git"
BRANCH="feat/colab-local-runner"

echo "=== [1/4] Ensuring google-colab-cli is installed ==="
if ! command -v colab &>/dev/null; then
    echo "Installing google-colab-cli..."
    pip install -q google-colab-cli
fi

echo "=== [2/4] Provisioning Colab instance with T4 GPU ==="
echo "Creating session '$SESSION_NAME' with GPU T4..."
colab new --gpu T4 -s "$SESSION_NAME"

echo "=== [3/4] Pulling repository on the remote Colab server ==="
colab exec -s "$SESSION_NAME" "
if [ ! -d Auspicious-fire- ]; then
    git clone -b $BRANCH $REPO_URL Auspicious-fire-
else
    cd Auspicious-fire- && git fetch origin && git checkout $BRANCH && git pull origin $BRANCH
fi
"

echo "=== [4/4] Setting up services and running pipeline tests on Colab ==="
colab exec -s "$SESSION_NAME" "
cd Auspicious-fire-
bash scripts/colab_setup.sh
bash scripts/start_services.sh
python scripts/test_pipeline_e2e.py
"

echo "================================================================="
echo "Colab T4 testing completed successfully."
echo "To connect interactively, run: colab console -s $SESSION_NAME"
echo "To terminate the instance when finished, run: colab stop -s $SESSION_NAME"
echo "================================================================="
