# Monitoring Troubleshooting

## Monitoring command is not found

Confirm that the virtual environment is active:

    source .venv/bin/activate

If the project has not been installed into the environment:

    pip install -e .

Then retry the command.

## Configuration file error

Verify that these files exist:

- `config/monitoring.yaml`
- `config/application.yaml`
- `config/obs.yaml`
- `config/camera.yaml`
- `config/broadcast_profiles.yaml`

Check YAML indentation and confirm that all required monitoring modes
are present.

## No monitoring records appear

Check:

1. The command printed a session directory.
2. The session directory exists.
3. The selected mode has enabled collectors.
4. The process has permission to write to the output directory.
5. The session was not stopped before the first collection cycle.

For a quick check, run:

    meetinghouse-broadcast-monitor --once

## OBS is unavailable

Verify:

- OBS Studio is running.
- OBS WebSocket server is enabled.
- The configured host and port are correct.
- Authentication settings match the local environment.
- The workstation can connect to the configured endpoint.

The OBS collector uses read-only requests. It does not launch OBS.

## Camera is reported unavailable

The passive camera collector does not send VISCA commands.

VISCA over UDP does not provide a safe passive status query in this
implementation. An unavailable reachability status is therefore not
proof that the camera is offline.

Check the camera's web interface and OBS video feed separately.

## RTSP TCP diagnostic fails

Verify:

- The configured RTSP host is correct.
- The configured RTSP port matches the actual camera stream URL.
- The camera is powered and connected.
- The workstation can reach the camera on the required network.
- No network policy or firewall rule is blocking the connection.

Do not assume a default RTSP port. Use the actual configured stream
endpoint.

A successful TCP connection does not prove that OBS can decode the
stream.

## Active harness refuses to run

The harness refuses to proceed if the broadcast controller is still
running.

Stop the controller normally and verify that it has exited.

Do not manually remove a PID file as a workaround until you have
confirmed that the referenced process is no longer running.

The harness also requires the exact confirmation phrase shown on
screen.

## Camera preset command is sent but the camera does not move

A successful VISCA UDP send only confirms that the local operating
system accepted the packet for transmission.

Check:

- Camera address and VISCA port.
- VISCA-over-IP packet configuration.
- Camera preset numbers.
- Camera firmware and preset configuration.
- Network connectivity between workstation and camera.
- Whether the camera physically responds to the preset command.

Use the camera's own interface to confirm that the expected presets
exist.

## RTSP recovery does not complete

Restore the camera's video/data path while keeping PoE power connected.

Wait for OBS to report that the camera input is showing video again.

If video does not return, inspect the OBS source and camera stream
configuration manually.

Do not change managed switch settings without authorization.

## Session ends with failure or interruption

Inspect `session.json` for the final status.

For active tests, review `events.jsonl` and `results.jsonl`.

Before returning the broadcast system to service, manually verify:

- Original OBS scene
- Camera position
- Camera video in OBS
- OBS Virtual Camera status, if used
