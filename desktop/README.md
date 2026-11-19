# Desktop Integration

The desktop shortcuts are generated automatically.

Run:

    ./scripts/install-desktop.sh

The installer creates:

- Start Meetinghouse Broadcast
- Stop Meetinghouse Broadcast

The shortcuts are placed in:

- The current user's Desktop directory
- ~/.local/share/applications/

They launch the corresponding shell scripts in the repository.

If the desktop environment asks for permission to execute
the shortcuts, select Allow Launching.
