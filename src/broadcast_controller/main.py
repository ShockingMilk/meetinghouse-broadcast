import argparse
import logging
import os
import signal
import socket
import sys
import time

from pathlib import Path

from broadcast_controller.config import (
    load_config,
    get_log_directory,
    get_state_directory,
)
from broadcast_controller.logging_config import (
    configure_logging,
)
from broadcast_controller.services.lifecycle import (
    BroadcastLifecycle,
)
from broadcast_controller.services.audio_service import (
    AudioService,
)
from broadcast_controller.obs.client import (
    OBSController,
)
from broadcast_controller.camera.visca import (
    VISCAController,
)
from broadcast_controller.utils.process import (
    is_process_running,
)

def setup():
    config = load_config()

    log_directory = get_log_directory(config)
    state_directory = get_state_directory(config)

    logger = configure_logging(
        config,
        log_directory
    )

    return config, state_directory, logger

def start(config, state_directory, logger):
    pid_file = state_directory / "controller.pid"

    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())

            if is_process_running(old_pid):
                logger.error(
                    "Controller already running (PID %s).",
                    old_pid
                )
                return 1

        except (ValueError, OSError):
            pass

        pid_file.unlink(missing_ok=True)

    lifecycle = BroadcastLifecycle(
        config,
        state_directory
    )

    try:
        lifecycle.run()
        return 0

    except Exception:
        logger.exception("Application failed.")
        return 1

def stop(state_directory, logger):
    pid_file = state_directory / "controller.pid"

    if not pid_file.exists():
        logger.info("No controller PID file found.")
        return 0

    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        logger.error("Invalid controller PID file.")
        return 1

    if not is_process_running(pid):
        logger.info("Controller is not running.")
        pid_file.unlink(missing_ok=True)
        return 0

    logger.info(
        "Requesting graceful shutdown of PID %s.",
        pid
    )

    os.kill(pid, signal.SIGTERM)

    timeout = 20
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not is_process_running(pid):
            logger.info("Controller stopped.")
            return 0

        time.sleep(0.25)

    logger.error(
        "Controller did not stop within %s seconds.",
        timeout
    )

    return 1

def status(config, state_directory, logger):
    pid_file = state_directory / "controller.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())

            if is_process_running(pid):
                print(f"Controller: RUNNING (PID {pid})")
            else:
                print("Controller: STOPPED (stale PID)")
        except ValueError:
            print("Controller: INVALID PID FILE")
    else:
        print("Controller: STOPPED")

    obs_controller = OBSController(config)

    if obs_controller.is_available():
        print("OBS WebSocket: CONNECTED")

        try:
            active = obs_controller.get_virtual_camera_status()
            print(
                "OBS Virtual Camera: "
                + ("ACTIVE" if active else "INACTIVE")
            )
        except Exception as error:
            print(f"Virtual Camera: ERROR ({error})")

    else:
        print("OBS WebSocket: NOT CONNECTED")

    camera_config = config["camera"]["camera"]

    if camera_config["enabled"]:
        print(
            "PTZ camera: ENABLED "
            f"({camera_config['connection']['host']})"
        )
        print(
            "PTZ protocol: VISCA over IP / UDP"
        )
    else:
        print("PTZ camera: DISABLED")

    return 0

def diagnostics(config):
    print("\nMEETINGHOUSE BROADCAST DIAGNOSTICS")
    print("----------------------------------")

    obs_controller = OBSController(config)

    print(
        "OBS WebSocket: ",
        "PASS" if obs_controller.is_available() else "FAIL"
    )

    camera = config["camera"]["camera"]

    print(
        "Camera configuration: ",
        "ENABLED" if camera["enabled"] else "DISABLED"
    )

    print(
        "Camera destination: "
        f"{camera['connection']['host']}:"
        f"{camera['connection']['port']}/UDP"
    )

    zoom = config["zoom"]["zoom"]

    print(
        "Zoom meeting URL: ",
        "CONFIGURED" if zoom["meeting_url"] else "MISSING"
    )

    print(
        "OBS password: ",
        "CONFIGURED"
        if config["obs"]["obs"]["websocket"]["password"]
        else "MISSING"
    )

    return 0

def test_camera(config):
    camera_config = config["camera"]["camera"]

    if not camera_config["enabled"]:
        print("Camera integration is disabled.")
        return 1

    controller = VISCAController(config)

    try:
        preset = camera_config["initial_preset"]

        print(f"Sending preset {preset}...")

        controller.recall_preset(int(preset))

        print(
            "UDP packet sent. This does NOT confirm "
            "that the camera moved."
        )

        return 0

    finally:
        controller.close()

def audio_test(config):
    service = AudioService(config)

    try:
        service.start()
        service.use_microphone()

        status = service.get_status()
        router_status = status["router"]

        print("\nMEETINGHOUSE AUDIO TEST")
        print("------------------------")
        print("Virtual audio device: READY")
        print(
            "Zoom microphone: "
            f"{router_status['microphone_input']}"
        )
        print(
            "Physical microphone: "
            f"{status['router']['microphone_source']}"
        )

        print("\nNext steps:")
        print("1. Open Zoom audio settings.")
        print("2. Select the Meetinghouse Broadcast Microphone.")
        print("3. Test your microphone.")
        print("4. Speak and verify that Zoom receives audio.")
        print("\nPress Ctrl+C to stop the test.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping audio test.")

    finally:
        service.shutdown()

    return 0

def audio_music_test(config, playlist_name):
    service = AudioService(config)

    try:
        service.start()
        service.use_music(playlist_name)

        status = service.get_status()

        print("\nMEETINGHOUSE MUSIC TEST")
        print("------------------------")
        print("Virtual audio device: READY")
        print(
            "Zoom microphone: "
            f"{status['router']['microphone_input']}"
        )
        print(f"Playlist: {playlist_name}")
        print("Playback: STARTED")

        print("\nNext steps:")
        print("1. Open Zoom audio settings.")
        print("2. Select the Meetinghouse Broadcast Microphone.")
        print("3. Use the Zoom microphone test recording.")
        print("4. Verify that you hear the music.")
        print("\nPress Ctrl+C to stop playback.")

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping music test.")

    finally:
        service.shutdown()

    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Meetinghouse Broadcast Controller"
    )

    parser.add_argument(
        "command",
        choices=[
            "start",
            "stop",
            "status",
            "diagnostics",
            "test-camera",
            "audio-test",
            "audio-music-test",
        ]
    )
    parser.add_argument(
        "--playlist",
        default="sacrament",
        help="Music playlist directory to test.",
    )

    args = parser.parse_args()

    try:
        config, state_directory, logger = setup()

        if args.command == "start":
            return start(
                config,
                state_directory,
                logger
            )

        if args.command == "stop":
            return stop(
                state_directory,
                logger
            )

        if args.command == "status":
            return status(
                config,
                state_directory,
                logger
            )

        if args.command == "diagnostics":
            return diagnostics(config)

        if args.command == "test-camera":
            return test_camera(config)

        if args.command == "audio-test":
            return audio_test(config)

        if args.command == "audio-music-test":
            return audio_music_test(config, args.playlist)

    except Exception:
        logging.exception("Command failed.")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
