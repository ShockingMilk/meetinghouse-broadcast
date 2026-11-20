"""Read-only OBS monitoring collector."""

from __future__ import annotations

import logging
import obsws_python as obs

from typing import Any, Callable

from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord


logger = logging.getLogger("broadcast.monitoring.obs")


class OBSCollector:
    """Collect OBS state through its read-only WebSocket requests."""

    name = "obs"
    safety = CollectorSafety.READ_ONLY

    def __init__(
        self,
        config: dict,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config["obs"]["obs"]
        self.camera_config = config.get("camera", {}).get("camera", {})
        self.client_factory = client_factory or obs.ReqClient

    def _record(
        self,
        context: CollectorContext,
        *,
        name: str,
        status: RecordStatus,
        component: str = "obs",
        value: Any = None,
        unit: str | None = None,
        message: str | None = None,
        attributes: dict[str, Any] | None = None,
        record_type: RecordType = RecordType.MEASUREMENT,
    ) -> MonitoringRecord:
        return MonitoringRecord(
            component=component,
            record_type=record_type,
            name=name,
            status=status,
            session_id=context.session_id,
            mode=context.mode,
            value=value,
            unit=unit,
            message=message,
            attributes=attributes or {},
        )

    def _create_client(self):
        settings = self.config["websocket"]

        return self.client_factory(
            host=settings["host"],
            port=settings["port"],
            password=settings.get("password", ""),
            timeout=settings.get("timeout", 5),
        )

    @staticmethod
    def _response_value(response: Any, key: str) -> Any:
        if isinstance(response, dict):
            return response.get(key)

        return getattr(response, key, None)

    @staticmethod
    def _disconnect(client: Any) -> None:
        """Close a client when its implementation exposes disconnect()."""
        disconnect = getattr(client, "disconnect", None)

        if callable(disconnect):
            try:
                disconnect()
            except Exception:
                logger.debug(
                    "Unable to close OBS monitoring connection.",
                    exc_info=True,
                )

    def collect(self, context: CollectorContext) -> list[MonitoringRecord]:
        records: list[MonitoringRecord] = []

        try:
            client = self._create_client()
        except Exception as error:
            return [
                self._record(
                    context,
                    name="websocket_connection",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                    record_type=RecordType.STATUS,
                )
            ]

        try:
            records.append(
                self._record(
                    context,
                    name="websocket_connection",
                    status=RecordStatus.NORMAL,
                    value=True,
                    record_type=RecordType.STATUS,
                )
            )

            records.extend(self._collect_version(context, client))
            records.extend(self._collect_current_scene(context, client))
            records.extend(self._collect_virtual_camera(context, client))
            records.extend(self._collect_stats(context, client))
            records.extend(self._collect_inputs(context, client))

        finally:
            self._disconnect(client)

        return records

    def _collect_version(
        self,
        context: CollectorContext,
        client: Any,
    ) -> list[MonitoringRecord]:
        try:
            response = client.get_version()

            value = {
                "obs_version": self._response_value(response, "obs_version"),
                "obs_web_socket_version": self._response_value(
                    response,
                    "obs_web_socket_version",
                ),
                "platform": self._response_value(response, "platform"),
                "platform_description": self._response_value(
                    response,
                    "platform_description",
                ),
            }

            return [
                self._record(
                    context,
                    name="version",
                    status=RecordStatus.NORMAL,
                    value=value,
                    record_type=RecordType.STATUS,
                )
            ]

        except Exception as error:
            return [
                self._record(
                    context,
                    name="version",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                    record_type=RecordType.STATUS,
                )
            ]

    def _collect_current_scene(
        self,
        context: CollectorContext,
        client: Any,
    ) -> list[MonitoringRecord]:
        try:
            response = client.send(
                "GetCurrentProgramScene",
                raw=True,
            )

            scene = (
                response.get("currentProgramSceneName")
                or response.get("sceneName")
            )

            if not scene:
                raise ValueError("OBS returned no current program scene.")

            return [
                self._record(
                    context,
                    name="current_program_scene",
                    status=RecordStatus.NORMAL,
                    value=scene,
                    record_type=RecordType.STATUS,
                )
            ]

        except Exception as error:
            return [
                self._record(
                    context,
                    name="current_program_scene",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                    record_type=RecordType.STATUS,
                )
            ]

    def _collect_virtual_camera(
        self,
        context: CollectorContext,
        client: Any,
    ) -> list[MonitoringRecord]:
        try:
            response = client.send(
                "GetVirtualCamStatus",
                raw=True,
            )

            active = response.get("outputActive")

            if not isinstance(active, bool):
                raise ValueError(
                    "OBS returned an invalid virtual camera status."
                )

            return [
                self._record(
                    context,
                    name="virtual_camera",
                    status=RecordStatus.NORMAL,
                    value={"active": active},
                    record_type=RecordType.STATUS,
                )
            ]

        except Exception as error:
            return [
                self._record(
                    context,
                    name="virtual_camera",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                    record_type=RecordType.STATUS,
                )
            ]

    def _collect_stats(
        self,
        context: CollectorContext,
        client: Any,
    ) -> list[MonitoringRecord]:
        try:
            response = client.send(
                "GetStats",
                raw=True,
            )

            # Whitelist numeric performance fields. Do not persist
            # arbitrary response data from OBS.
            fields = (
                "cpuUsage",
                "memoryUsage",
                "availableDiskSpace",
                "activeFps",
                "averageFrameRenderTime",
                "renderTotalFrames",
                "renderMissedFrames",
                "outputTotalFrames",
                "outputSkippedFrames",
            )

            stats = {
                key: response[key]
                for key in fields
                if key in response
                and isinstance(response[key], (int, float))
            }

            if not stats:
                raise ValueError("OBS returned no recognized performance statistics.")

            return [
                self._record(
                    context,
                    name="performance",
                    status=RecordStatus.NORMAL,
                    value=stats,
                    record_type=RecordType.MEASUREMENT,
                )
            ]

        except Exception as error:
            return [
                self._record(
                    context,
                    name="performance",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

    def _collect_inputs(
        self,
        context: CollectorContext,
        client: Any,
    ) -> list[MonitoringRecord]:
        try:
            response = client.send(
                "GetInputList",
                raw=True,
            )

            inputs = response.get("inputs", [])

            inventory = [
                {
                    "name": item.get("inputName"),
                    "kind": item.get("inputKind"),
                }
                for item in inputs
                if isinstance(item, dict)
            ]

            records = [
                self._record(
                    context,
                    name="input_inventory",
                    status=RecordStatus.NORMAL if inventory else RecordStatus.UNAVAILABLE,
                    value=inventory,
                    message=None if inventory else "OBS returned no inputs.",
                    record_type=RecordType.STATUS,
                )
            ]

        except Exception as error:
            return [
                self._record(
                    context,
                    name="input_inventory",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                    record_type=RecordType.STATUS,
                ),
                self._camera_source_unavailable(
                    context,
                    "OBS input inventory could not be read.",
                ),
            ]

        source_name = (
            self.camera_config
            .get("monitoring", {})
            .get("obs_input_name", "")
        )

        if not source_name:
            records.append(
                self._camera_source_unavailable(
                    context,
                    "No OBS camera input name is configured.",
                )
            )
            return records

        matching_inputs = [
            item for item in inventory
            if item["name"] == source_name
        ]

        if not matching_inputs:
            records.append(
                self._camera_source_unavailable(
                    context,
                    "Configured camera input was not found in OBS.",
                    attributes={"input_name": source_name},
                )
            )
            return records

        try:
            response = client.send(
                "GetSourceActive",
                {
                    "sourceName": source_name,
                },
                raw=True,
            )

            video_active = response.get("videoActive")
            video_showing = response.get("videoShowing")

            if not isinstance(video_active, bool) or not isinstance(video_showing, bool):
                raise ValueError("OBS returned incomplete input activity information.")

            records.append(
                self._record(
                    context,
                    component="camera",
                    name="obs_input_activity",
                    status=RecordStatus.NORMAL,
                    value={
                        "video_active": video_active,
                        "video_showing": video_showing,
                    },
                    attributes={"input_name": source_name},
                    record_type=RecordType.STATUS,
                )
            )

        except Exception as error:
            records.append(
                self._camera_source_unavailable(
                    context,
                    str(error),
                    attributes={"input_name": source_name},
                )
            )

        return records

    def _camera_source_unavailable(
        self,
        context: CollectorContext,
        message: str,
        attributes: dict[str, Any] | None = None,
    ) -> MonitoringRecord:
        return self._record(
            context,
            component="camera",
            name="obs_input_activity",
            status=RecordStatus.UNAVAILABLE,
            message=message,
            attributes=attributes,
            record_type=RecordType.STATUS,
        )