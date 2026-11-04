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

echo "=== [3/4] Pulling repository on the remote Colab server ==="
python3 -c "
import subprocess, sys

script = '''
import os, subprocess

repo = \"$REPO_URL\"
branch = \"$BRANCH\"
target = \"/content/Auspicious-fire-\"

if not os.path.exists(target):
    subprocess.run([\"git\", \"clone\", \"-b\", branch, repo, target], check=True)
else:
    subprocess.run([\"git\", \"fetch\", \"origin\"], cwd=target, check=True)
    subprocess.run([\"git\", \"checkout\", branch], cwd=target, check=True)
    subprocess.run([\"git\", \"pull\", \"origin\", branch], cwd=target, check=True)
'''
p = subprocess.Popen([\"colab\", \"exec\", \"-s\", \"$SESSION_NAME\"], stdin=subprocess.PIPE, text=True)
p.communicate(input=script)
sys.exit(p.returncode)
"

echo "=== [4/4] Setting up services and running pipeline tests on Colab ==="
python3 -c "
import subprocess, sys

script = '''
import subprocess, sys

def run(cmd, cwd=\"/content/Auspicious-fire-\"):
    print(f\"\\n>>> Running: {cmd}\", flush=True)
    p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(p.stdout.readline, ''):
        sys.stdout.write(line)
        sys.stdout.flush()
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f\"Failed: {cmd}\")

run(\"bash scripts/colab_setup.sh\")
run(\"bash scripts/start_services.sh\")
run(\"python scripts/test_pipeline_e2e.py\")
'''
p = subprocess.Popen([\"colab\", \"exec\", \"-s\", \"$SESSION_NAME\", \"--timeout\", \"1800\"], stdin=subprocess.PIPE, text=True)
p.communicate(input=script)
sys.exit(p.returncode)
"

echo "================================================================="
echo "Colab T4 testing completed successfully."
echo "To connect interactively, run: colab console -s $SESSION_NAME"
echo "To terminate the instance when finished, run: colab stop -s $SESSION_NAME"
echo "================================================================="
