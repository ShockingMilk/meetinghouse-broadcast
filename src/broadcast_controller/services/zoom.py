import logging
import os
import subprocess
import time

from urllib.parse import (
    urlencode,
    urlparse,
    parse_qsl,
    urlunparse,
)


logger = logging.getLogger(__name__)


class ZoomLauncher:

    def __init__(self, config):
        self.config = config
        self.zoom_config = config.get("zoom", {}).get("zoom", {})
        self.process = None

    def build_meeting_url(self):
        """Build the Zoom meeting URL using the configured URL and .env passcode."""

        meeting_url = self.zoom_config.get(
            "meeting_url", ""
        ).strip()

        passcode = os.getenv(
            "ZOOM_MEETING_PASSCODE", ""
        ).strip()

        if not meeting_url:
            logger.warning(
                "No Zoom meeting URL configured."
            )
            return None

        if not passcode:
            logger.info(
                "No Zoom passcode supplied. "
                "Opening meeting URL as configured."
            )
            return meeting_url

        parsed_url = urlparse(meeting_url)

        query_params = dict(
            parse_qsl(parsed_url.query)
        )

        query_params["pwd"] = passcode

        updated_query = urlencode(query_params)

        return urlunparse(
            parsed_url._replace(query=updated_query)
        )

    def launch(self):
        """Open the configured Zoom meeting."""

        if not self.zoom_config.get("enabled", True):
            logger.info(
                "Zoom launching is disabled."
            )
            return False

        meeting_url = self.build_meeting_url()

        if not meeting_url:
            return False

        launcher = self.zoom_config.get(
            "launcher", "xdg-open"
        )

        startup_delay = self.zoom_config.get(
            "startup_delay", 3
        )

        try:
            self.process = subprocess.Popen(
                [launcher, meeting_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            logger.info(
                "Zoom meeting launch requested."
            )

            time.sleep(startup_delay)

            return True

        except FileNotFoundError:
            logger.exception(
                "Zoom launcher executable was not found."
            )
            return False

        except Exception:
            logger.exception(
                "Unable to launch Zoom."
            )
            return False
