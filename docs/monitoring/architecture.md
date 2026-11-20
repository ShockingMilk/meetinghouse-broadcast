# Monitoring Architecture

## Purpose

The monitoring system collects information about the workstation and
broadcast environment without becoming part of the broadcast control
path.

It is independent of the Meetinghouse Technology website and does not
require a database or internet connection.

## Component overview

The monitoring architecture consists of:

- MonitoringConfiguration — validates and resolves monitoring settings
- MonitoringSession — creates and tracks a monitoring session
- MonitoringEngine — coordinates collectors and writes their records
- MonitoringRunner — schedules collectors at configured intervals
- JSONLWriter — writes records to rotating JSON Lines files
- Collectors — gather information from individual system components

## Data flow

    Configuration
         |
         v
    MonitoringConfiguration
         |
         v
    MonitoringSession
         |
         v
    MonitoringEngine
         |
         +---- NetworkCollector
         |
         +---- SystemCollector
         |
         +---- OBSCollector
         |
         +---- CameraCollector
         |
         v
    JSONLWriter
         |
         v
    logs/monitoring/SESSION_ID/

The MonitoringRunner controls when each collector executes.

## Collectors

### NetworkCollector

Collects available network interface, route, DNS, Wi-Fi, and interface
counter information.

Diagnostic connectivity checks are optional and disabled by default.

The collector does not change addresses, routes, DNS, Wi-Fi settings,
firewall rules, or switch configuration.

### SystemCollector

Collects workstation information and available resource measurements,
including CPU, memory, disk, and uptime information.

Some measurements are Linux-specific. Unsupported measurements should
be recorded as unsupported or unavailable rather than treated as a
system failure.

### OBSCollector

Connects through OBS WebSocket using read-only requests.

It collects available OBS version, connection, scene, output, and
related status information.

It does not change scenes or start or stop outputs.

### CameraCollector

Collects non-secret camera configuration information.

The camera uses VISCA over UDP. Since UDP transmission does not provide
a safe passive status query, the collector does not send VISCA commands
to test reachability.

An optional diagnostic RTSP TCP connection check is available when
explicitly configured.

## Operating modes

### Passive

Normal read-only monitoring.

This mode is intended for observing the system during ordinary
operation, including a meeting.

### Diagnostic

Read-only monitoring with optional additional connectivity checks.

Additional checks must be explicitly enabled in `config/monitoring.yaml`.

### Active

Reserved for operations that require control permissions.

The passive monitoring CLI does not expose active mode. The separate
active test harness performs its own safety checks before sending
control commands.

## Failure handling

A collector failure is recorded as a diagnostic failure record.

The engine continues with other collectors where possible.

A collector reporting a component as unavailable or unsupported does
not necessarily mean the component itself has failed.

## Data storage

Each session has its own directory containing:

- `session.json`
- One or more `records-NNNN.jsonl` files

The writer enforces configured segment size and retention limits.

See [Data Schema](data-schema.md) for the record format.
