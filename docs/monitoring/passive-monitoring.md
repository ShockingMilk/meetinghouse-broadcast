# Passive Monitoring

## Purpose

Passive monitoring observes the broadcast environment without
intentionally changing its state.

It is suitable for collecting information during normal operation,
including a meeting, provided the workstation and network are being
used in their normal approved configuration.

## What it monitors

| Component | Information |
| --- | --- |
| Network | Interfaces, routes, DNS, Wi-Fi, interface counters |
| System | Host information, CPU, memory, disk, uptime |
| OBS | WebSocket availability and available OBS status information |
| Camera | Configured camera information and optional diagnostics |

The exact records depend on operating-system support and the
availability of each component.

## Collection intervals

Intervals are configured in `config/monitoring.yaml`.

Current defaults:

| Collector | Passive interval |
| --- | ---: |
| Network | 5 seconds |
| System | 15 seconds |
| OBS | 5 seconds |
| Camera | 10 seconds |

These values can be adjusted without changing collector code.

## Start a session

Run:

    meetinghouse-broadcast-monitor

The application prints the session ID and output directory.

Press Ctrl+C when the observation period is complete.

## Run a single snapshot

Run:

    meetinghouse-broadcast-monitor --once

This performs one collection cycle and exits.

## What passive monitoring does not do

Passive monitoring does not:

- Change OBS scenes.
- Start or stop OBS Virtual Camera.
- Move the PTZ camera.
- Change audio devices or audio levels.
- Change network settings.
- Disconnect or reconnect the RTSP stream.
- Join, leave, or control a Zoom meeting.

## Understanding camera status

The camera uses VISCA over UDP for preset commands.

A passive UDP status check is not implemented because sending a preset
command would move the camera and would not be a read-only health check.

As a result, camera reachability may be recorded as unavailable even
when the camera is functioning normally.

This is intentional. Do not interpret that status by itself as proof
that the camera is offline.

## Diagnostic mode

Diagnostic mode supports additional checks that are disabled by
default.

For example, the optional RTSP TCP probe can test whether a configured
RTSP host and port accept a TCP connection.

This does not verify that the video stream is valid or that OBS is
decoding it correctly.

Only enable diagnostic checks after confirming the correct endpoint
and that the additional traffic is acceptable.
