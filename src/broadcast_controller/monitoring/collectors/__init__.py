"""Built-in monitoring collectors."""

from broadcast_controller.monitoring.collectors.camera import CameraCollector
from broadcast_controller.monitoring.collectors.network import NetworkCollector
from broadcast_controller.monitoring.collectors.obs import OBSCollector
from broadcast_controller.monitoring.collectors.system import SystemCollector

__all__ = [
    "CameraCollector",
    "NetworkCollector",
    "OBSCollector",
    "SystemCollector",
]