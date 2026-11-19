#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

if command -v zenity >/dev/null 2>&1; then

    zenity --question \
        --title="Stop Meetinghouse Broadcast" \
        --text="Before continuing:

1. End the Zoom meeting.
2. Close Zoom.
3. Confirm that you are ready to stop OBS and the PTZ controller.

Continue with shutdown?" \
        || exit 0

else

    read -r -p \
        "Have you ended and closed Zoom? [y/N] " answer

    [[ "$answer" =~ ^[Yy]$ ]] || exit 0

fi

if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

PYTHON="$PROJECT_ROOT/.venv/bin/python"

if "$PYTHON" -m broadcast_controller.main stop; then
    RESULT=0
else
    RESULT=$?
fi

if [[ "$RESULT" -eq 0 ]]; then

    if command -v notify-send >/dev/null 2>&1; then
	    notify-send \
        	"Meetinghouse Broadcast" \
        	"Broadcast controller stopped."
    fi
else

    if command -v notify-send >/dev/null 2>&1; then
	    notify-send \
        	"Meetinghouse Broadcast" \
        	"Shutdown did not complete. Check logs."
    fi
fi

exit "$RESULT"
