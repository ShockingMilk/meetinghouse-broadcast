#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APPLICATION_DIR="$HOME/.local/share/applications"

if command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP)"
else
    DESKTOP_DIR="$HOME/Desktop"
fi

mkdir -p "$APPLICATION_DIR"
mkdir -p "$DESKTOP_DIR"

START_SCRIPT="$PROJECT_ROOT/scripts/start-meeting.sh"
STOP_SCRIPT="$PROJECT_ROOT/scripts/stop-meeting.sh"

cat > "$APPLICATION_DIR/meetinghouse-start.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Start Meetinghouse Broadcast
Comment=Start OBS, PTZ automation and Zoom
Exec="$START_SCRIPT"
Icon=camera-video
Terminal=false
Categories=AudioVideo;Video;
EOF

cat > "$APPLICATION_DIR/meetinghouse-stop.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Stop Meetinghouse Broadcast
Comment=Safely stop OBS and PTZ automation
Exec="$STOP_SCRIPT"
Icon=process-stop
Terminal=false
Categories=AudioVideo;Video;
EOF

cp "$APPLICATION_DIR/meetinghouse-start.desktop" \
   "$DESKTOP_DIR/Start Meetinghouse Broadcast.desktop"

cp "$APPLICATION_DIR/meetinghouse-stop.desktop" \
   "$DESKTOP_DIR/Stop Meetinghouse Broadcast.desktop"

chmod +x \
    "$APPLICATION_DIR/meetinghouse-start.desktop" \
    "$APPLICATION_DIR/meetinghouse-stop.desktop" \
    "$DESKTOP_DIR/Start Meetinghouse Broadcast.desktop" \
    "$DESKTOP_DIR/Stop Meetinghouse Broadcast.desktop"

if command -v gio >/dev/null 2>&1; then

    gio set "$DESKTOP_DIR/Start Meetinghouse Broadcast.desktop" \
        metadata::trusted true || true

    gio set "$DESKTOP_DIR/Stop Meetinghouse Broadcast.desktop" \
        metadata::trusted true || true

fi

echo
echo "Desktop shortcuts installed."
echo
echo "Desktop: $DESKTOP_DIR"
echo "Applications: $APPLICATION_DIR"
echo
