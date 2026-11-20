# Monitoring Operating Guide

## Requirements

- Ubuntu workstation used by Meetinghouse Broadcast
- Python 3.12 or newer
- Project dependencies installed
- OBS WebSocket configured when OBS monitoring is required
- Valid project configuration files

## Install or update the project

From the repository root:

    source .venv/bin/activate
    pip install -e .

If the virtual environment does not exist yet, follow the installation
instructions in the root README first.

## Run passive monitoring

Start continuous passive monitoring:

    meetinghouse-broadcast-monitor

The command uses the passive mode configured in
`config/monitoring.yaml`.

Press Ctrl+C to stop the session cleanly.

## Run one snapshot

For a single collection cycle:

    meetinghouse-broadcast-monitor --once

This is useful for confirming that configuration and collectors work
before starting a longer session.

## Run diagnostic monitoring

Start diagnostic mode:

    meetinghouse-broadcast-monitor --mode diagnostic

Diagnostic checks remain disabled unless their corresponding options
are enabled in `config/monitoring.yaml`.

Do not enable network or RTSP probes without understanding the traffic
they generate and confirming that the checks are permitted on the
meetinghouse network.

## Run the active test harness

The active test harness is separate from passive monitoring:

    meetinghouse-broadcast-test

It can change OBS scenes and send PTZ preset commands.

Only run it when:

- No meeting or live broadcast is in progress.
- The broadcast controller is stopped.
- The operator is present and able to observe the equipment.
- The operator can restore any manually interrupted video connection.

The harness requires the exact confirmation phrase shown by the
application.

See [Active Test Harness](active-test-harness.md).

## Output locations

Passive and diagnostic sessions:

    logs/monitoring/

Active test sessions:

    logs/tests/

Each session creates a unique directory. Do not edit session files
while a monitoring or test process is writing to them.

## Stop behavior

When passive monitoring receives Ctrl+C, the CLI closes the monitoring
session and updates its metadata.

The active test harness attempts to restore the original OBS scene,
closes its controller connections, and closes its result session.

The monitoring tools do not shut down the workstation, OBS, or Zoom.
