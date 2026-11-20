"""Command-line entry point for passive and diagnostic monitoring."""

import argparse
import logging
import threading

from broadcast_controller.config import load_config, get_project_root
from broadcast_controller.monitoring import (
    CameraCollector,
    CollectorSafety,
    JSONLWriter,
    MonitoringConfiguration,
    MonitoringEngine,
    MonitoringMode,
    MonitoringSession,
    NetworkCollector,
    OBSCollector,
    SystemCollector,
)
from broadcast_controller.monitoring.runner import MonitoringRunner


def build_engine(config, mode):
    monitoring_config = MonitoringConfiguration.from_mapping(
        config["monitoring"],
        get_project_root(),
    )

    session = MonitoringSession(
        mode=mode,
        output_directory=monitoring_config.output_directory,
    )

    writer = JSONLWriter(
        session.session_directory,
        max_file_bytes=monitoring_config.max_file_bytes,
        backup_count=monitoring_config.backup_count,
    )

    engine = MonitoringEngine(
        configuration=monitoring_config,
        session=session,
        writer=writer,
    )

    engine.register_collector(NetworkCollector())
    engine.register_collector(SystemCollector())
    engine.register_collector(OBSCollector(config))
    engine.register_collector(CameraCollector(config))

    return monitoring_config, engine


def main():
    parser = argparse.ArgumentParser(description="Meetinghouse Broadcast Monitoring",)

    parser.add_argument(
        "--mode",
        choices=["passive", "diagnostic"],
        default="passive",
        help="Monitoring mode. Active control is not provided by this command.",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Collect one snapshot and exit.",
    )

    args = parser.parse_args()

    engine = None
    status = "completed"

    try:
        config = load_config()
        mode = MonitoringMode(args.mode)

        monitoring_config, engine = build_engine(config, mode)

        print("MEETINGHOUSE BROADCAST MONITORING")
        print("--------------------------------")
        print(f"Mode: {mode.value}")
        print(f"Session: {engine.session.session_id}")
        print(f"Output: {engine.session.session_directory}")

        if args.once:
            engine.run_once()
            return 0

        print("Monitoring is running. Press Ctrl+C to stop.")

        stop_event = threading.Event()

        runner = MonitoringRunner(
            engine=engine,
            configuration=monitoring_config,
        )

        runner.run(stop_event)

        return 0

    except KeyboardInterrupt:
        status = "interrupted"
        print("\nMonitoring stopped by operator.")
        return 130

    except Exception:
        status = "failure"
        logging.exception("Monitoring command failed.")
        return 1

    finally:
        if engine is not None:
            engine.close(status=status)


if __name__ == "__main__":
    raise SystemExit(main())
