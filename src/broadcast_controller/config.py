import os
import yaml

from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_yaml(filename):
    """Load a YAML configuration file."""

    path = PROJECT_ROOT / "config" / filename

    if not path.exists():
        raise FileNotFoundError(f"Configuration not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def resolve_environment_value(
    variable_name,
    default=None,
    converter=None,
):
    """
    Resolve a value from the environment.

    Operating-system environment variables take precedence over
    values loaded from the project's .env file.

    Args:
        variable_name: Environment variable name.
        default: Value used when the variable is missing or empty.
        converter: Optional conversion function, such as int.

    Returns:
        Resolved and optionally converted value.
    """

    if not variable_name:
        return default

    raw_value = os.getenv(variable_name)

    if raw_value is None or not raw_value.strip():
        return default

    value = raw_value.strip()

    if converter is not None:
        try:
            return converter(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Environment variable {variable_name} has an invalid value: {value!r}") from error

    return value


def load_config():
    """
    Load application configuration and resolve environment settings.
    """

    # Load .env without overriding variables already supplied
    # by the operating system or launching process.
    load_dotenv(
        dotenv_path=ENV_FILE,
        override=False,
    )

    config = {
        "application": load_yaml("application.yaml"),
        "obs": load_yaml("obs.yaml"),
        "camera": load_yaml("camera.yaml"),
        "zoom": load_yaml("zoom.yaml"),
        "audio": load_yaml("audio.yaml"),
        "broadcast_profiles": load_yaml("broadcast_profiles.yaml"),
        "monitoring": load_yaml("monitoring.yaml"),
    }

    # ---------------------------------------------------------
    # OBS configuration
    # ---------------------------------------------------------

    obs_config = config["obs"]["obs"]
    websocket = obs_config["websocket"]

    websocket["host"] = resolve_environment_value(
        websocket.get("host"),
        default="127.0.0.1",
    )

    websocket["port"] = resolve_environment_value(
        websocket.get("port"),
        default=4455,
        converter=int,
    )

    websocket["password"] = resolve_environment_value(
        websocket.get("password_environment_variable"),
        default="",
    )

    # ---------------------------------------------------------
    # OBS camera input configuration
    # ---------------------------------------------------------

    camera_config = config["camera"]["camera"]
    camera_monitoring = camera_config.setdefault(
        "monitoring",
        {},
    )

    camera_monitoring["obs_input_name"] = (
        resolve_environment_value(
            camera_monitoring.get(
                "obs_input_name",
                "OBS_INPUT_NAME",
            ),
            default="",
        )
    )

    # ---------------------------------------------------------
    # Zoom configuration
    # ---------------------------------------------------------

    zoom_config = config["zoom"]["zoom"]

    zoom_config["meeting_url"] = resolve_environment_value(
        zoom_config.get("meeting_url"),
        default="",
    )

    # ZOOM_MEETING_PASSCODE is loaded into os.environ by
    # load_dotenv(). ZoomLauncher currently reads it directly.
    # It is intentionally not copied into the config dictionary.

    # ---------------------------------------------------------
    # PTZ camera configuration
    # ---------------------------------------------------------

    connection = camera_config["connection"]

    connection["host"] = resolve_environment_value(
        connection.get("host"),
        default="",
    )

    connection["port"] = resolve_environment_value(
        connection.get("port"),
        default=None,
        converter=int,
    )

    return config


def get_project_root():
    return PROJECT_ROOT


def get_state_directory(config):
    raw_path = config["application"]["paths"]["state"]
    path = Path(raw_path).expanduser()

    path.mkdir(parents=True, exist_ok=True)

    return path


def get_log_directory(config):
    raw_path = config["application"]["paths"]["logs"]
    path = PROJECT_ROOT / raw_path

    path.mkdir(parents=True, exist_ok=True)

    return path