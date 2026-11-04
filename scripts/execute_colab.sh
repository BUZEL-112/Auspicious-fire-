#!/usr/bin/env bash
set -e
export PATH="$HOME/.local/bin:$PATH"
echo "Starting Colab execution..."
colab exec -s fashion-cpu --timeout 1800 -f /mnt/c/Users/User/Documents/antigravity/auspicious-fire/scripts/colab_bootstrap.py
echo "Colab execution finished."
