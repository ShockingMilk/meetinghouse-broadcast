#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/.venv/bin/python"
MONITOR_DIR="$PROJECT_ROOT/logs/monitoring"
PID_FILE="$MONITOR_DIR/monitor.pid"
LOG_FILE="$PROJECT_ROOT/logs/monitoring-launcher.log"

if [[ ! -x "$PYTHON" ]]; then
    echo "Monitoring could not start: virtual environment missing."
    exit 1
fi

mkdir -p "$MONITOR_DIR" "$PROJECT_ROOT/logs"

is_monitor_running() {
    local pid="$1"

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1

    ps -p "$pid" -o args= 2>/dev/null \
        | grep -Fq "broadcast_controller.monitoring.cli"
}

# Avoid starting a second monitoring session.
if [[ -f "$PID_FILE" ]]; then
    EXISTING_PID="$(cat "$PID_FILE")"

    if is_monitor_running "$EXISTING_PID"; then
        echo "Monitoring is already running (PID $EXISTING_PID)."
        exit 0
    fi

    rm -f "$PID_FILE"
fi

echo "Starting passive monitoring..."

nohup "$PYTHON" -m broadcast_controller.monitoring.cli \
    >> "$LOG_FILE" 2>&1 < /dev/null &

MONITOR_PID=$!

echo "$MONITOR_PID" > "$PID_FILE"

sleep 2

if is_monitor_running "$MONITOR_PID"; then
    echo "Monitoring started successfully."
    echo "PID: $MONITOR_PID"
    echo "Log: $LOG_FILE"
    exit 0
fi

rm -f "$PID_FILE"

echo "Monitoring failed to start. Check:"
echo "$LOG_FILE"

exit 1