from pathlib import Path
import os
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_yaml(filename):
    path = PROJECT_ROOT / "config" / filename

    if not path.exists():
        raise FileNotFoundError(f"Configuration not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}

def load_config():
    config = {
        "application": load_yaml("application.yaml"),
        "obs": load_yaml("obs.yaml"),
        "camera": load_yaml("camera.yaml"),
        "zoom": load_yaml("zoom.yaml"),
        "audio": load_yaml("audio.yaml"),
        "broadcast_profiles": load_yaml("broadcast_profiles.yaml"),
        "monitoring": load_yaml("monitoring.yaml"),
    }

    obs_config = config["obs"]["obs"]
    password_env = (
        obs_config["websocket"]
        ["password_environment_variable"]
    )

    obs_config["websocket"]["password"] = os.getenv(
        password_env, ""
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
