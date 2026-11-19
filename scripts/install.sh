#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Installing Meetinghouse Broadcast Controller..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is required."
    exit 1
fi

PYTHON_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

echo "Detected Python: $PYTHON_VERSION"

python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip

pip install -r requirements.txt

pip install -e .

chmod +x scripts/*.sh

if [[ ! -f .env ]]; then
    cp .env.example .env
    chmod 600 .env
fi

mkdir -p logs

echo
echo "Installation complete."
echo
echo "Next steps:"
echo "1. Edit .env and configure OBS_WS_PASSWORD."
echo "2. Configure the YAML files in config/."
echo "3. Configure OBS WebSocket."
echo "4. Run scripts/install-desktop.sh."
echo
