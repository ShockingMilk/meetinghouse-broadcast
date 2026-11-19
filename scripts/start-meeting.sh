#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

if [[ ! -d .venv ]]; then
    echo "Virtual environment missing."
    echo "Run scripts/install.sh first."
    exit 1
fi

if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

mkdir -p logs

PYTHON="$PROJECT_ROOT/.venv/bin/python"

if "$PYTHON" -m broadcast_controller.main status \
    | grep -q "Controller: RUNNING"; then

    notify-send \
        "Meetinghouse Broadcast" \
        "Broadcast controller is already running."

    exit 0
fi

nohup "$PYTHON" -m broadcast_controller.main start \
    >> "$PROJECT_ROOT/logs/launcher.log" 2>&1 &

sleep 2

if command -v notify-send >/dev/null 2>&1; then
	notify-send \
    	    "Meetinghouse Broadcast" \
    	    "Startup requested. Check status before joining Zoom."
fi

echo "Broadcast startup requested."
echo "Logs: $PROJECT_ROOT/logs/"
