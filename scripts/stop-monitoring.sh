#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/logs/monitoring/monitor.pid"

is_monitor_running() {
    local pid="$1"

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1

    ps -p "$pid" -o args= 2>/dev/null \
        | grep -Fq "broadcast_controller.monitoring.cli"
}

if [[ ! -f "$PID_FILE" ]]; then
    echo "No monitoring PID file found."
    exit 0
fi

MONITOR_PID="$(cat "$PID_FILE")"

if ! is_monitor_running "$MONITOR_PID"; then
    echo "Monitoring is not running."
    rm -f "$PID_FILE"
    exit 0
fi

echo "Stopping monitoring (PID $MONITOR_PID)..."

kill -INT "$MONITOR_PID"

for ((i=0; i<20; i++)); do
    if ! is_monitor_running "$MONITOR_PID"; then
        rm -f "$PID_FILE"
        echo "Monitoring stopped cleanly."
        exit 0
    fi

    sleep 1
done

echo "Monitoring has not stopped within 20 seconds."
echo "The process was not forcefully terminated."
echo "Check the process and try again."

exit 1