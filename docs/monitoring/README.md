# Meetinghouse Broadcast Monitoring

This documentation covers the monitoring and testing tools used by
Meetinghouse Broadcast.

The monitoring system is designed to observe the broadcast workstation,
network, OBS, and PTZ camera without interfering with a live broadcast.

## Start here

- [Operating Guide](operating-guide.md) — commands and normal operation
- [Passive Monitoring](passive-monitoring.md) — read-only monitoring
- [Active Test Harness](active-test-harness.md) — controlled equipment tests
- [Test Procedures](test-procedures.md) — recommended validation sequence
- [Architecture](architecture.md) — components and data flow
- [Troubleshooting](troubleshooting.md) — common problems
- [Data Schema](data-schema.md) — monitoring record format

## Safety model

The monitoring tools have two distinct responsibilities:

1. Passive and diagnostic monitoring observe system state.
2. The active test harness deliberately changes OBS scenes and sends
   PTZ preset commands.

Passive monitoring must not move the camera, change OBS scenes, change
audio settings, or alter network configuration.

The active test harness requires the broadcast controller to be stopped
and explicit operator confirmation before it can proceed.

Never run active tests during a meeting or live broadcast.

## Output locations

| Output | Location |
| --- | --- |
| Passive and diagnostic sessions | `logs/monitoring/` |
| Active test sessions | `logs/tests/` |
| Application logs | `logs/broadcast.log` |

Each monitoring or test run receives its own session directory.

## Current limitations

- Camera preset transmission uses VISCA over UDP. A successful send does
  not prove that the camera received or executed the command.
- Physical camera movement requires operator verification.
- Passive camera monitoring does not send VISCA commands.
- RTSP diagnostic probing is optional and disabled by default.
- Active RTSP recovery testing requires a safe way to interrupt video
  data without disconnecting PoE power.
- Audio testing and changes are outside the scope of this monitoring work.
