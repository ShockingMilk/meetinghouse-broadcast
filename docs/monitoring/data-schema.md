# Meetinghouse Broadcast Monitoring Data Schema

Schema version: 1.0

## Purpose

The monitoring system writes portable, append-only JSON Lines records.

The monitoring system does not depend on the Meetinghouse Technology
website or its database.

The website may later import these records into Django models.

## Directory structure

Each monitoring session has its own directory:

logs/monitoring/
    SESSION_ID/
        session.json
        records-0001.jsonl
        records-0002.jsonl

## Session metadata

session.json describes the monitoring session.

Fields:

- session_id
- mode
- started_at
- ended_at
- status
- software_name
- software_version
- schema_version
- configuration

## Record format

Each line in a JSONL file is one independent JSON object.

Required fields:

- schema_version
- record_id
- timestamp
- session_id
- mode
- component
- record_type
- name
- status
- value
- unit
- message
- attributes

## Field definitions

### schema_version

Version of the record format.

### record_id

Unique identifier for an individual record.

### timestamp

UTC timestamp in ISO 8601 format.

Example:

2026-11-19T15:30:00Z

### session_id

Identifier connecting records to their monitoring session.

### mode

One of:

- passive
- active
- diagnostic

### component

The system being monitored.

Examples:

- network
- system
- obs
- camera

### record_type

One of:

- measurement
- event
- status
- diagnostic

### name

Metric, event, or status name.

Examples:

- wifi_signal
- packet_loss
- cpu_usage
- scene_changed
- camera_reachable

### status

One of:

- normal
- unavailable
- unsupported
- warning
- degraded
- failure

### value

Optional measurement or event value.

Examples:

- -58
- 29.7
- true
- "02 - Chorister"

### unit

Optional measurement unit.

Examples:

- dBm
- ms
- percent
- bytes
- Mbps

### message

Optional human-readable description.

### attributes

Additional structured information specific to the record.

Examples:

- network interface name
- previous and current OBS scene
- camera address
- error type
- measurement source

## Example measurement

{
    "schema_version": "1.0",
    "record_id": "unique-record-id",
    "timestamp": "2026-11-19T15:30:00Z",
    "session_id": "example-session",
    "mode": "passive",
    "component": "network",
    "record_type": "measurement",
    "name": "wifi_signal",
    "status": "normal",
    "value": -58,
    "unit": "dBm",
    "message": null,
    "attributes": {
        "interface": "wlan0"
    }
}

## Example event

{
    "schema_version": "1.0",
    "record_id": "unique-event-id",
    "timestamp": "2026-11-19T15:30:12Z",
    "session_id": "example-session",
    "mode": "passive",
    "component": "obs",
    "record_type": "event",
    "name": "scene_changed",
    "status": "normal",
    "value": null,
    "unit": null,
    "message": "OBS program scene changed.",
    "attributes": {
        "previous_scene": "01 - Speaker",
        "current_scene": "02 - Chorister"
    }
}

## Status interpretation

- normal: measurement or operation completed normally
- unavailable: the component could not currently be reached
- unsupported: the requested measurement is not supported
- warning: an abnormal condition was detected
- degraded: service is operating with reduced quality
- failure: an operation failed

Unavailable and unsupported must not automatically be
interpreted as component failure.

## Data retention

Records are segmented by maximum file size.

The configured segment count applies to each session.

Session metadata is retained separately.

## Website integration

The website should eventually:

1. Read session metadata.
2. Validate schema_version.
3. Validate individual records.
4. Import records into Django models.
5. Preserve the original session_id and record_id.
6. Track import status to prevent duplicate imports.

The website must not be required for live monitoring.

## Security

Monitoring records must not contain:

- OBS WebSocket passwords
- Zoom meeting secrets
- Authentication tokens
- Private credentials

Network addresses and device information should be accessible
only to authorized management users.
