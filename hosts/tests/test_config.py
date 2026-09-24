from dataclasses import replace

import pytest
from e87canbus.config import (
    CanNetwork,
    EngineTelemetryConfig,
    LivePublicationConfig,
    NetworkConfigError,
    SteeringConfig,
    configure_can_networks,
    default_config,
    parse_network_names,
    simulator_config,
    sorted_network_names,
)


def test_default_can_network_configuration_is_ordered_and_receive_only() -> None:
    config = default_config()
    assert [item.network for item in config.can_networks] == list(CanNetwork)
    assert [item.bitrate for item in config.can_networks] == [100_000, 500_000, 500_000]
    assert all(item.enabled for item in config.can_networks)
    assert all(not hasattr(item, "tx_enabled") for item in config.can_networks)
    assert simulator_config() == config


@pytest.mark.parametrize(
    "changes",
    [
        {"telemetry_hz": 0.0},
        {"health_hz": 0.0},
        {"client_queue_capacity": 0},
        {"shutdown_timeout_s": float("nan")},
    ],
)
def test_live_publication_bounds_reject_invalid_values(changes: dict[str, int | float]) -> None:
    with pytest.raises(ValueError, match="live"):
        LivePublicationConfig(**changes)


@pytest.mark.parametrize("changes", [{"manual_level_count": 0}, {"speed_timeout_s": 0.0}])
def test_steering_configuration_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SteeringConfig(**changes)


def test_telemetry_timeout_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        EngineTelemetryConfig(timeout_s=float("nan"))


def test_runtime_bounds_reject_invalid_values() -> None:
    with pytest.raises(ValueError):
        replace(default_config(), tick_interval_s=0.0)
    with pytest.raises(ValueError):
        replace(default_config(), runtime_inbox_capacity=0)


def test_network_selection_only_changes_receive_enablement() -> None:
    config = configure_can_networks(default_config(), enabled_networks=frozenset({CanNetwork.KCAN}))
    assert [item.network for item in config.can_networks if item.enabled] == [CanNetwork.KCAN]
    assert sorted_network_names(parse_network_names("fcan,kcan")) == ["kcan", "fcan"]
    with pytest.raises(NetworkConfigError):
        parse_network_names("unknown")
