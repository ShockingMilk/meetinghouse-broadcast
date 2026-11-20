# Active Test Harness

## Purpose

The active test harness performs controlled tests that cannot be
completed through read-only monitoring.

It can:

- Connect to OBS WebSocket.
- Read the current OBS program scene.
- Read OBS Virtual Camera status.
- Send configured VISCA camera preset commands.
- Change OBS program scenes.
- Test the camera preset mapping used by SceneMonitor.
- Observe RTSP video interruption and recovery.
- Restore the original OBS scene and its configured camera preset.

The harness does not test or change the audio system.

## Safety requirements

Never run the active test harness during a meeting or live broadcast.

Before proceeding, the harness checks the broadcast controller PID
file and refuses to continue if the controller is running.

The operator must then enter the exact confirmation phrase:

    NO LIVE BROADCAST

The controller state is checked again before the test proceeds.

These checks reduce the chance of interfering with an active broadcast.
They do not replace operator judgment.

## Run the harness

From the project root:

    meetinghouse-broadcast-test

The harness creates a session under:

    logs/tests/SESSION_ID/

The session contains:

- `session.json`
- `events.jsonl`
- `results.jsonl`

## Test sequence

### 1. OBS connectivity

The harness attempts to connect to OBS and retrieve:

- OBS version information
- Current program scene
- OBS Virtual Camera status

The original program scene is saved for restoration.

### 2. Camera preset tests

The harness reads the configured broadcast profiles and identifies
the unique camera presets they reference.

The operator can choose which presets to test.

After each VISCA command, the operator confirms whether the camera
physically reached the expected position.

A successful UDP send is not considered proof of camera movement.

### 3. Scene transition tests

For each configured scene with a camera preset, the harness asks
whether that scene should be tested.

It then:

1. Changes the OBS program scene.
2. Verifies that OBS reports the requested scene.
3. Uses the existing SceneMonitor camera logic.
4. Verifies that the expected preset command was successfully applied.
5. Asks the operator to confirm the physical camera position.

The SceneMonitor is initialized with audio disabled. No audio actions
are performed.

### 4. RTSP interruption and recovery

This test is optional.

The harness first verifies that the configured camera input is
currently showing video in OBS.

The operator must confirm that video data can be interrupted without
disconnecting camera power.

Important:

- Do NOT unplug the camera's PoE Ethernet cable.
- Do NOT disconnect the camera's power.
- Do NOT change managed switch settings without authorization.
- Do NOT perform this test if a safe data-only interruption method
  is unavailable.

The harness checks whether OBS stops showing video and then checks
whether video returns after the operator restores the data path.

A failed interruption check does not eliminate the need to restore
the video path. Follow the harness restoration instructions.

### 5. Restoration

The harness attempts to restore the original OBS program scene.

If that scene has a configured camera preset, the harness sends the
corresponding preset command.

The result confirms command transmission, not physical camera position.
The operator should visually confirm the final camera position.

## Result interpretation

| Status | Meaning |
| --- | --- |
| PASS | The test condition was verified |
| FAIL | The expected condition was not met |
| SKIPPED | The operator chose not to run the test |
| INCONCLUSIVE | The result could not be independently verified |

A PASS for a VISCA command means the operator confirmed the physical
position. A successful UDP send alone is not a PASS.

## Shutdown and recovery

The harness closes the VISCA socket and disconnects its OBS WebSocket
client when finished.

It does not intentionally terminate an OBS process.

If the harness is interrupted, verify the OBS scene, camera position,
and RTSP video path manually before returning the system to service.
