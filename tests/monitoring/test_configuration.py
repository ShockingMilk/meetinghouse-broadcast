from broadcast_controller.monitoring.configuration import MonitoringConfiguration
from broadcast_controller.monitoring.enums import MonitoringMode

def make_configuration(tmp_path, passive_control=False):
    return MonitoringConfiguration.from_mapping(
        {
            "monitoring": {
                "schema_version": "1.0",
                "output_directory": "logs/monitoring",
                "max_file_bytes": 1024,
                "backup_count": 5,
                "default_mode": "passive",
                "modes": {
                    "passive": {
                        "allow_control_actions": passive_control,
                        "collectors": {},
                    },
                    "active": {
                        "allow_control_actions": True,
                        "collectors": {},
                    },
                    "diagnostic": {
                        "allow_control_actions": True,
                        "collectors": {},
                    }
                }
            }
        },
        project_root=tmp_path
    )

def test_configuration_resolves_relative_output_path(tmp_path):
    config = make_configuration(tmp_path)

    assert config.output_directory == tmp_path / "logs/monitoring"

def test_passive_mode_never_allows_control(tmp_path):
    config = make_configuration(tmp_path, passive_control=True)

    assert not config.allows_control_actions(MonitoringMode.PASSIVE)

def test_diagnostic_mode_never_allows_control(tmp_path):
    config = make_configuration(tmp_path)

    assert not config.allows_control_actions(MonitoringMode.DIAGNOSTIC)

def test_active_mode_obeys_configuration(tmp_path):
    config = make_configuration(tmp_path)

    assert config.allows_control_actions(MonitoringMode.ACTIVE)

def test_default_mode_is_passive(tmp_path):
    config = make_configuration(tmp_path)

    assert config.default_mode is MonitoringMode.PASSIVE
