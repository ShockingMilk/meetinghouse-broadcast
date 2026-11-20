# Monitoring Test Procedures

## Purpose

These procedures provide a repeatable way to validate monitoring
software and broadcast equipment.

Automated unit tests and live equipment tests are separate forms of
verification. Passing unit tests does not prove that the meetinghouse
equipment is functioning correctly.

## Procedure 1: Automated software tests

From the repository root:

    source .venv/bin/activate
    pytest -q

Record:

- Test count
- Passed tests
- Failed tests
- Warnings
- Date of test run
- Git branch and commit, if available

Do not treat an automated test result as proof of live equipment
operation.

## Procedure 2: Passive monitoring smoke test

Run:

    meetinghouse-broadcast-monitor --once

Verify:

1. The command exits successfully.
2. A new session directory appears under `logs/monitoring/`.
3. `session.json` exists.
4. At least one `records-NNNN.jsonl` file exists.
5. The records contain the expected session ID and mode.
6. No credentials or secrets appear in the output.

If OBS is unavailable, confirm that the OBS collector records its
status without preventing other collectors from running.

## Procedure 3: Passive meeting observation

When ready to observe an actual meeting:

1. Confirm that the normal broadcast setup is operating.
2. Start passive monitoring.
3. Allow the session to run during the meeting.
4. Stop monitoring with Ctrl+C after the observation period.
5. Confirm that the session metadata has an end time and final status.
6. Review the records for unexpected gaps, failures, or degraded states.

Do not run active tests during this procedure.

## Procedure 4: Active equipment test

Only perform this procedure when no meeting or live broadcast is in
progress.

1. Confirm that the broadcast controller is stopped.
2. Confirm that OBS is available and the camera feed is visible.
3. Start the active test harness.
4. Complete the exact confirmation phrase.
5. Test selected camera presets.
6. Test selected OBS scene transitions.
7. Perform RTSP interruption and recovery only if a safe data-only
   interruption method is available.
8. Allow the harness to restore the original scene.
9. Verify the original camera position and live video manually.
10. Review `logs/tests/SESSION_ID/`.

Do not disconnect PoE power as a way to interrupt RTSP video.

## Procedure 5: Post-test review

Review the active test session:

- `session.json` — session status and timestamps
- `events.jsonl` — actions requested during the test
- `results.jsonl` — individual test outcomes

Record any failed or inconclusive tests with enough context to
reproduce them.

Do not mark a physical camera movement as verified unless it was
visually observed.

## Validation boundaries

| Validation | What it proves |
| --- | --- |
| Automated unit tests | Tested code paths behave as expected under test conditions |
| Passive snapshot | Collectors can execute and write records |
| Passive meeting session | Monitoring operates during real workstation use |
| Active harness | Selected OBS and camera actions work under test conditions |
| Physical inspection | Equipment visibly reaches the expected state |

All of these provide useful evidence, but none should be substituted
for another.
