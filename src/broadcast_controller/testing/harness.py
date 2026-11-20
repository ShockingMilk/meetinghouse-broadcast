import time

from pathlib import Path

from broadcast_controller.camera.visca import VISCAController
from broadcast_controller.config import get_project_root
from broadcast_controller.monitoring.configuration import MonitoringConfiguration
from broadcast_controller.obs.client import OBSController
from broadcast_controller.services.scene_monitor import SceneMonitor
from broadcast_controller.testing.event_dispatcher import EventDispatcher
from broadcast_controller.testing.events import HarnessEvent, HarnessEventType
from broadcast_controller.testing.results import TestResult, TestResultWriter, TestStatus
from broadcast_controller.utils.process import is_process_running

CONFIRMATION_PHRASE = "NO LIVE BROADCAST"


class ActiveTestHarness:
    def __init__(
        self,
        config: dict,
        state_directory: Path,
        input_fn=input,
        output_fn=print,
        obs_factory=OBSController,
        camera_factory=VISCAController,
        result_writer_factory=TestResultWriter,
        scene_wait_seconds: float = 5,
        rtsp_wait_seconds: float = 20,
        poll_interval: float = 0.5,
    ):
        self.config = config
        self.state_directory = Path(state_directory)

        self.input = input_fn
        self.output = output_fn

        self.obs_factory = obs_factory
        self.camera_factory = camera_factory
        self.result_writer_factory = result_writer_factory

        self.scene_wait_seconds = scene_wait_seconds
        self.rtsp_wait_seconds = rtsp_wait_seconds
        self.poll_interval = poll_interval

        self.dispatcher = EventDispatcher()

        self.writer = None
        self.obs = None
        self.camera = None

        self.original_scene = None
        self.obs_connected = False

        self._register_handlers()

    # ---------------------------------------------------------
    # Event handling
    # ---------------------------------------------------------

    def _register_handlers(self):
        self.dispatcher.subscribe_all(self._record_event)

    def _record_event(self, event):
        if self.writer:
            self.writer.write_event(event)

    def _dispatch(self, event_type, **payload):
        event = HarnessEvent(
            event_type=event_type,
            payload=payload,
        )

        self.dispatcher.dispatch(event)

    # ---------------------------------------------------------
    # Safety
    # ---------------------------------------------------------

    def check_controller_stopped(self):
        pid_file = self.state_directory / "controller.pid"

        if not pid_file.exists():
            return

        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError) as error:
            raise RuntimeError("Unable to verify broadcast controller state. Check the controller PID file before testing.") from error

        if is_process_running(pid):
            raise RuntimeError(f"Broadcast controller is running (PID {pid}). Active testing is prohibited while it is running.")

    def confirm_test_environment(self):
        self.check_controller_stopped()

        self.output("")
        self.output("ACTIVE BROADCAST TEST HARNESS")
        self.output("-----------------------------")
        self.output("This harness can change OBS scenes and move the PTZ camera.")
        self.output("Do not run during a meeting or live broadcast.")
        self.output("The broadcast controller must be stopped.")
        self.output("")

        confirmation = self.input(f"Type '{CONFIRMATION_PHRASE}' to continue: ").strip()

        if confirmation != CONFIRMATION_PHRASE:
            raise RuntimeError("Active test confirmation was not provided.")

        # Recheck immediately before creating controllers.
        self.check_controller_stopped()

    # ---------------------------------------------------------
    # Results
    # ---------------------------------------------------------

    def _result(
        self,
        name: str,
        status: TestStatus,
        message: str,
        **details,
    ):
        result = TestResult(
            test_name=name,
            status=status,
            message=message,
            details=details,
        )

        self.writer.write_result(result)

        self.output(f"[{status.value.upper()}] {name}: {message}")

        return result

    def _ask_yes_no(self, prompt: str) -> bool:
        answer = self.input(f"{prompt} [y/N]: ").strip().lower()

        return answer in {"y", "yes"}

    # ---------------------------------------------------------
    # OBS tests
    # ---------------------------------------------------------

    def test_obs_connection(self) -> bool:
        self.output("\nOBS CONNECTIVITY")

        try:
            self.obs = self.obs_factory(self.config)
            self.obs.connect()
            self.obs_connected = True

            version = self.obs.client.get_version()

            version_value = {
                "obs_version": getattr(
                    version,
                    "obs_version",
                    None,
                ),
                "websocket_version": getattr(
                    version,
                    "obs_web_socket_version",
                    None,
                ),
            }

            self._result(
                "obs_connection",
                TestStatus.PASS,
                "OBS WebSocket connection established.",
                version=version_value,
            )

        except Exception as error:
            self._result(
                "obs_connection",
                TestStatus.FAIL,
                "Unable to connect to OBS.",
                error=str(error),
                error_type=type(error).__name__,
            )
            return False

        try:
            self.original_scene = self.obs.get_current_scene()

            self._result(
                "obs_current_scene",
                TestStatus.PASS,
                "Current program scene retrieved.",
                scene=self.original_scene,
            )

        except Exception as error:
            self._result(
                "obs_current_scene",
                TestStatus.FAIL,
                "Unable to retrieve current program scene.",
                error=str(error),
            )

        try:
            active = self.obs.get_virtual_camera_status()

            self._result(
                "obs_virtual_camera",
                TestStatus.PASS,
                "Virtual camera status retrieved.",
                active=bool(active),
            )

        except Exception as error:
            self._result(
                "obs_virtual_camera",
                TestStatus.FAIL,
                "Unable to retrieve virtual camera status.",
                error=str(error),
            )

        self._dispatch(HarnessEventType.OBS_CONNECTED)

        return True

    # ---------------------------------------------------------
    # Camera preset tests
    # ---------------------------------------------------------

    def _configured_presets(self) -> list[int]:
        profiles = self.config["broadcast_profiles"]["profiles"]

        presets = {int(profile["camera_preset"]) for profile in profiles.values() if "camera_preset" in profile}

        return sorted(presets)

    def test_camera_presets(self):
        camera_config = self.config["camera"]["camera"]

        if not camera_config.get("enabled", False):
            self._result(
                "camera_presets",
                TestStatus.SKIPPED,
                "Camera integration is disabled.",
            )
            return

        self.output("\nPTZ PRESET TESTS")

        try:
            self.camera = self.camera_factory(self.config)
        except Exception as error:
            self._result(
                "camera_initialization",
                TestStatus.FAIL,
                "Unable to initialize VISCA controller.",
                error=str(error),
            )
            return

        for preset in self._configured_presets():
            if not self._ask_yes_no(f"Test camera preset {preset}?"):
                self._result(
                    f"camera_preset_{preset}",
                    TestStatus.SKIPPED,
                    "Operator skipped this preset.",
                    preset=preset,
                )
                continue

            self._dispatch(
                HarnessEventType.CAMERA_PRESET_REQUESTED,
                preset=preset,
            )

            try:
                bytes_sent = self.camera.recall_preset(preset)

            except Exception as error:
                self._result(
                    f"camera_preset_{preset}",
                    TestStatus.FAIL,
                    "VISCA command could not be sent.",
                    preset=preset,
                    error=str(error),
                )
                continue

            self.output(f"VISCA command sent ({bytes_sent} bytes). UDP transmission does not confirm camera movement.")

            answer = self.input("Did the camera reach the expected position? [y/n/u for unsure]: ").strip().lower()

            if answer in {"y", "yes"}:
                status = TestStatus.PASS
                message = "Operator confirmed physical camera position."
            elif answer in {"n", "no"}:
                status = TestStatus.FAIL
                message = "Operator reported incorrect camera position."
            else:
                status = TestStatus.INCONCLUSIVE
                message = "Physical camera movement was not verified."

            self._result(
                f"camera_preset_{preset}",
                status,
                message,
                preset=preset,
                bytes_sent=bytes_sent,
                physical_verification=answer,
            )

    # ---------------------------------------------------------
    # Scene transition tests
    # ---------------------------------------------------------

    def _wait_for_scene(self, expected_scene: str) -> bool:
        deadline = time.monotonic() + self.scene_wait_seconds

        while time.monotonic() < deadline:
            if self.obs.get_current_scene() == expected_scene:
                return True

            time.sleep(self.poll_interval)

        return False

    def test_scene_transitions(self):
        if not self.obs_connected or not self.camera:
            self._result(
                "scene_transitions",
                TestStatus.SKIPPED,
                "OBS or camera controller is unavailable.",
            )
            return

        profiles = self.config["broadcast_profiles"]["profiles"]

        scenes = [(scene_name, int(profile["camera_preset"])) for scene_name, profile in profiles.items() if "camera_preset" in profile]

        self.output("\nSCENE TRANSITION TESTS")
        self.output("Audio is disabled for these tests. The existing SceneMonitor camera logic will be used.")

        for scene_name, preset in scenes:
            if not self._ask_yes_no(f"Switch OBS to '{scene_name}' and test preset {preset}?"):
                self._result(
                    f"scene_{scene_name}",
                    TestStatus.SKIPPED,
                    "Operator skipped this scene.",
                    scene=scene_name,
                    expected_preset=preset,
                )
                continue

            self._dispatch(
                HarnessEventType.SCENE_TRANSITION_REQUESTED,
                scene=scene_name,
                expected_preset=preset,
            )

            try:
                self.obs.set_scene(scene_name)

                if not self._wait_for_scene(scene_name):
                    self._result(
                        f"scene_{scene_name}",
                        TestStatus.FAIL,
                        "OBS did not report the requested program scene.",
                        scene=scene_name,
                    )
                    continue

                monitor = SceneMonitor(
                    obs_controller=self.obs,
                    camera_controller=self.camera,
                    audio_service=None,
                    config=self.config,
                )

                monitor.process_scene(scene_name)

                # SceneMonitor catches camera exceptions internally.
                # A fresh monitor starts with no last_camera_preset, so
                # this verifies that recall_preset returned successfully.
                if monitor.last_camera_preset != preset:
                    self._result(
                        f"scene_{scene_name}",
                        TestStatus.FAIL,
                        "SceneMonitor did not successfully apply "
                        "the expected camera preset command.",
                        scene=scene_name,
                        expected_preset=preset,
                        applied_preset=monitor.last_camera_preset,
                    )
                    continue

                answer = self.input(f"Did the camera reach the expected position for '{scene_name}'? [y/n/u]: ").strip().lower()

                if answer in {"y", "yes"}:
                    status = TestStatus.PASS
                    message = "Scene and physical camera position verified."
                elif answer in {"n", "no"}:
                    status = TestStatus.FAIL
                    message = "Camera position did not match the scene."
                else:
                    status = TestStatus.INCONCLUSIVE
                    message = "Physical camera position was not verified."

                self._result(
                    f"scene_{scene_name}",
                    status,
                    message,
                    scene=scene_name,
                    expected_preset=preset,
                    applied_preset=monitor.last_camera_preset,
                    physical_verification=answer,
                )

            except Exception as error:
                self._result(
                    f"scene_{scene_name}",
                    TestStatus.FAIL,
                    "Scene transition test encountered an error.",
                    scene=scene_name,
                    error=str(error),
                )

    # ---------------------------------------------------------
    # RTSP interruption and recovery
    # ---------------------------------------------------------

    def _get_camera_input_activity(self):
        source_name = (
            self.config["camera"]["camera"]
            .get("monitoring", {})
            .get("obs_input_name", "")
        )

        if not source_name:
            raise ValueError("OBS camera input name is not configured.")

        response = self.obs.client.send(
            "GetInputActive",
            {"sourceName": source_name},
            raw=True,
        )

        return {
            "video_active": response.get("videoActive"),
            "video_showing": response.get("videoShowing"),
            "input_name": source_name,
        }

    def _wait_for_video_showing(self, expected: bool) -> bool:
        deadline = time.monotonic() + self.rtsp_wait_seconds

        while time.monotonic() < deadline:
            activity = self._get_camera_input_activity()

            if activity["video_showing"] is expected:
                return True

            time.sleep(self.poll_interval)

        return False

    def test_rtsp_recovery(self):
        if not self.obs_connected:
            self._result(
                "rtsp_recovery",
                TestStatus.SKIPPED,
                "OBS connection is unavailable.",
            )
            return

        self.output("\nRTSP INTERRUPTION AND RECOVERY")

        try:
            baseline = self._get_camera_input_activity()

            if baseline["video_showing"] is not True:
                self._result(
                    "rtsp_baseline",
                    TestStatus.INCONCLUSIVE,
                    "Camera input is not currently showing video. "
                    "Select a scene where the camera is visible first.",
                    activity=baseline,
                )
                return

        except Exception as error:
            self._result(
                "rtsp_baseline",
                TestStatus.FAIL,
                "Unable to read OBS camera input activity.",
                error=str(error),
            )
            return

        # The camera uses PoE. Interrupting its Ethernet connection
        # may also remove its power. Only proceed if the operator has
        # a safe way to interrupt video/data without disconnecting PoE.
        if not self._ask_yes_no(
            "Can you interrupt the camera's video/data path "
            "while keeping its power connection intact?"
        ):
            self._result(
                "rtsp_interruption",
                TestStatus.SKIPPED,
                (
                    "No safe data-only interruption method is available. "
                    "Camera power must remain connected."
                ),
            )
            return

        self._dispatch(
            HarnessEventType.RTSP_INTERRUPTION_REQUESTED,
            input_name=baseline["input_name"],
        )

        self.output("\nInterrupt only the camera's video/data path.")
        self.output("Do NOT unplug the camera's PoE Ethernet cable.")
        self.output("Do NOT change managed switch settings without authorization.")

        interruption_detected = self._wait_for_video_showing(False)

        if interruption_detected:
            self._result(
                "rtsp_interruption",
                TestStatus.PASS,
                "OBS reported that the camera input stopped showing video.",
            )
        else:
            self._result(
                "rtsp_interruption",
                TestStatus.FAIL,
                "OBS did not report the camera input as no longer showing.",
                input_name=baseline["input_name"],
            )

        self._dispatch(
            HarnessEventType.RTSP_RESTORATION_REQUESTED,
            input_name=baseline["input_name"],
        )

        self.output("\nRestore the camera's video/data path.")
        self.output("Keep the camera's PoE power connection intact.")

        if not self._wait_for_video_showing(True):
            self._result(
                "rtsp_recovery",
                TestStatus.FAIL,
                "OBS did not report the camera input showing video again.",
                input_name=baseline["input_name"],
            )
            return

        self._result(
            "rtsp_recovery",
            TestStatus.PASS,
            "OBS reported that the camera input is showing video again.",
            input_name=baseline["input_name"],
        )

    # ---------------------------------------------------------
    # Restoration and shutdown
    # ---------------------------------------------------------

    def restore_original_scene(self):
        if not self.obs_connected or not self.original_scene:
            return

        try:
            self.output(f"\nRestoring original OBS scene: {self.original_scene}")

            self.obs.set_scene(self.original_scene)

            if not self._wait_for_scene(self.original_scene):
                self._result(
                    "restore_original_scene",
                    TestStatus.FAIL,
                    "Unable to verify restoration of the original OBS scene.",
                    scene=self.original_scene,
                )
                return

            # Restore the camera preset associated with the original scene.
            if self.camera:
                monitor = SceneMonitor(
                    obs_controller=self.obs,
                    camera_controller=self.camera,
                    audio_service=None,
                    config=self.config,
                )

                monitor.process_scene(self.original_scene)

                profile = (
                    self.config["broadcast_profiles"]["profiles"].get(
                        self.original_scene
                    )
                )

                expected_preset = (
                    int(profile["camera_preset"])
                    if profile and "camera_preset" in profile
                    else None
                )

                if (
                    expected_preset is not None
                    and monitor.last_camera_preset != expected_preset
                ):
                    self._result(
                        "restore_original_camera",
                        TestStatus.FAIL,
                        (
                            "Original scene was restored, but its camera "
                            "preset command was not successfully applied."
                        ),
                        scene=self.original_scene,
                        expected_preset=expected_preset,
                        applied_preset=monitor.last_camera_preset,
                    )
                    return

                if expected_preset is not None:
                    self._result(
                        "restore_original_camera",
                        TestStatus.PASS,
                        (
                            "Original scene camera preset command was sent. "
                            "Physical camera position was not independently "
                            "verified."
                        ),
                        scene=self.original_scene,
                        expected_preset=expected_preset,
                        applied_preset=monitor.last_camera_preset,
                        physical_verification="not_checked",
                    )

            self._result(
                "restore_original_scene",
                TestStatus.PASS,
                "Original OBS scene restored.",
                scene=self.original_scene,
            )

        except Exception as error:
            self._result(
                "restore_original_scene",
                TestStatus.FAIL,
                "Unable to restore the original scene.",
                error=str(error),
            )

    def close(self):
        if self.camera:
            try:
                self.camera.close()
            except Exception:
                pass

        if self.obs and self.obs.client:
            disconnect = getattr(
                self.obs.client,
                "disconnect",
                None,
            )

            if callable(disconnect):
                try:
                    disconnect()
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Harness execution
    # ---------------------------------------------------------

    def run(self) -> Path:
        self.confirm_test_environment()

        monitoring_configuration = MonitoringConfiguration.from_mapping(
            self.config["monitoring"],
            get_project_root(),
        )

        output_directory = monitoring_configuration.output_directory.parent / "tests"

        self.writer = self.result_writer_factory(output_directory)

        status = "completed"

        try:
            self._dispatch(HarnessEventType.HARNESS_STARTED)

            self.test_obs_connection()
            self.test_camera_presets()
            self.test_scene_transitions()
            self.test_rtsp_recovery()

        except KeyboardInterrupt:
            status = "interrupted"
            self.output("\nTest session interrupted by operator.")

        except Exception:
            status = "failure"
            raise

        finally:
            try:
                self.restore_original_scene()

            finally:
                self.close()

                self._dispatch(HarnessEventType.HARNESS_STOPPED)
                self.writer.close(status=status)

        self.output("")
        self.output("ACTIVE TEST SESSION COMPLETE")
        self.output(f"Results: {self.writer.session_directory}")

        return self.writer.session_directory