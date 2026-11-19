# Meetinghouse Broadcast Controller

Version: 0.1.0

A local broadcast automation system for coordinating:

- OBS Studio
- OBS Virtual Camera
- Zoom
- Tongveo PTZ cameras
- OBS Blade remote control

Designed for Ubuntu 26.04.

---

# 1. Architecture

OBS is the central video production application.

Zoom receives the OBS Virtual Camera output.

A separate Python service monitors OBS program scene changes
and sends VISCA-over-IP preset commands to the PTZ camera.

OBS Blade controls OBS through its WebSocket interface.

All components operate locally on the network.

---

# 2. Requirements

- Ubuntu 26.04
- Python 3.12 or newer
- OBS Studio 28 or newer
- OBS WebSocket 5
- Zoom desktop application
- Tongveo NV20U-4K or compatible VISCA-over-IP camera
- Android phone running OBS Blade
- Network connectivity between the required devices

---

# 3. Installation

Clone or copy the repository.

From the project root:

    chmod +x scripts/*.sh

    ./scripts/install.sh

This creates a Python virtual environment and installs
the application dependencies.

---

# 4. Configuration

Edit:

    config/application.yaml
    config/obs.yaml
    config/camera.yaml
    config/zoom.yaml

Create the local environment file:

    cp .env.example .env

Edit .env and configure the OBS WebSocket password.

Protect it:

    chmod 600 .env

Do not commit .env to Git.

---

# 5. OBS Setup

Open OBS Studio.

Create a profile:

    Meetinghouse

Create a scene collection:

    Meetinghouse

Create the following scenes:

    00 - Opening
    01 - Speaker
    02 - Choir
    03 - Congregation

Add the Tongveo video feed as an OBS source.

Configure OBS Virtual Camera.

Open:

    Tools -> WebSocket Server Settings

Enable the WebSocket server.

Configure:

    Port: 4455
    Authentication: Enabled

Use the same password stored in .env.

Save your profile and scene collection.

---

# 6. Zoom Setup

Open Zoom manually.

Open video settings.

Select:

    OBS Virtual Camera

Confirm that the video feed appears.

Join a test meeting and verify that the selected camera
remains OBS Virtual Camera.

Configure the scheduled meeting URL in:

    config/zoom.yaml

The application opens the meeting URL after OBS initializes.

The operator manually confirms and joins the meeting.

---

# 7. Camera Setup

Connect the camera using PoE.

Configure a static IP address through its web interface.

Set the camera address in:

    config/camera.yaml

The VISCA-over-IP connection uses:

    Protocol: UDP
    Port: 52381

The camera and controller should be on the same network segment.

Store the required camera presets using the camera's supported
configuration interface or remote control.

Set:

    enabled: true

in config/camera.yaml.

Map OBS scenes to camera presets.

Example:

    "00 - Default": 0
    "01 - Speaker": 1
    "02 - Conductor": 2
    "03 - Choir": 3

---

# 8. OBS Blade

Enable OBS WebSocket.

Install OBS Blade on the Android phone.

Connect to the Ubuntu computer using:

    Host: Precision laptop IP
    Port: 4455
    Password: OBS WebSocket password

Both devices must be able to communicate over the network.

Do not expose OBS WebSocket to the public internet.

---

# 9. Desktop Shortcuts

Run:

    ./scripts/install-desktop.sh

This creates Start Meetinghouse and Stop Meetinghouse
desktop shortcuts.

---

# 10. Operation

Start:

    ./scripts/start-meeting.sh

Check status:

    ./scripts/check-status.sh

Diagnostics:

    ./scripts/diagnostics.sh

Test camera:

    ./scripts/test-camera.sh

Stop:

    ./scripts/stop-meeting.sh

---

# 11. Logs

Application logs:

    logs/broadcast.log

Launcher logs:

    logs/launcher.log

Runtime state:

    ~/.local/state/meetinghouse-broadcast/

---

# 12. Testing

Run the unit tests:

    source .venv/bin/activate

    python -m unittest discover -s tests -v

---

# 13. Shutdown Behavior

The shutdown process:

1. Operator ends Zoom.
2. Operator closes Zoom.
3. Operator runs Stop Meetinghouse.
4. Controller receives SIGTERM.
5. OBS Virtual Camera is stopped if started by this controller.
6. PTZ controller socket is closed.
7. OBS is gracefully terminated if launched by this controller.
8. Runtime state is removed.

The computer remains powered on.

An OBS instance that existed before the controller started
is not terminated.

---

# 14. Security

- OBS WebSocket authentication must remain enabled.
- Do not expose port 4455 to the internet.
- Keep .env outside Git.
- Restrict access to the project directory.
- Use a dedicated local administrator account where practical.
- Do not change Stake network firewall or VLAN settings
  without authorization.

---

# 15. Known Limitations

- Zoom camera selection is configured manually.
- Zoom meeting joining requires operator confirmation.
- Zoom shutdown is manual.
- UDP packet transmission does not confirm camera movement.
- VISCA command compatibility must be tested with the
  actual camera firmware.
- RTSP video source configuration is performed in OBS.
- Audio automation is not currently implemented.
- Wi-Fi client isolation may prevent OBS Blade connectivity.
- Camera and workstation network access must be verified.

---

# 16. Future Improvements

- VISCA response verification.
- Camera movement completion detection.
- Camera connection health monitoring.
- PTZ manual control from the controller.
- Preset configuration interface.
- OBS preview/program coordination.
- Audio device management.
- Zoom meeting status detection.
- Operator dashboard.
- Network diagnostics.
