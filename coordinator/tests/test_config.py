from dataclasses import replace

import pytest
from e87canbus.config import CanNetwork, TxPolicyConfig, default_config, simulator_config


def test_default_can_network_configuration_is_ordered_and_enabled() -> None:
    config = default_config()

    assert [item.network for item in config.can_networks] == [
        CanNetwork.KCAN,
        CanNetwork.PTCAN,
        CanNetwork.FCAN,
    ]
    assert [item.label for item in config.can_networks] == ["K-CAN", "PT-CAN", "F-CAN"]
    assert [item.interface for item in config.can_networks] == ["can0", "can1", "can2"]
    assert [item.bitrate for item in config.can_networks] == [100_000, 500_000, 500_000]
    assert all(item.enabled for item in config.can_networks)
    assert not any(item.tx_enabled for item in config.can_networks)


def test_simulator_configuration_explicitly_enables_kcan_tx() -> None:
    config = simulator_config()

    assert [item.network for item in config.can_networks if item.tx_enabled] == [CanNetwork.KCAN]


def test_default_simulation_trace_capacity() -> None:
    assert default_config().simulation.trace_capacity == 2_000


def test_custom_can_ids() -> None:
    config = default_config()

    assert config.custom_can_ids.button_event == 0x700
    assert config.custom_can_ids.led_update == 0x701


def test_steering_level_count() -> None:
    assert default_config().steering.manual_level_count == 8


def test_default_tick_and_speed_timeout_intervals() -> None:
    config = default_config()

    assert config.tick_interval_s == 0.1
    assert config.steering.speed_timeout_s == 1.0


def test_default_runtime_inbox_limits() -> None:
    config = default_config()

    assert config.runtime_inbox_capacity == 1_024
    assert config.runtime_queue_latency_warning_s == 0.1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"runtime_inbox_capacity": 0}, "runtime_inbox_capacity"),
        ({"runtime_queue_latency_warning_s": -0.1}, "runtime_queue_latency_warning_s"),
    ],
)
def test_runtime_inbox_limits_reject_unsafe_values(
    changes: dict[str, int | float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(default_config(), **changes)


def test_default_tx_policy() -> None:
    policy = default_config().tx_policy

    assert policy.network_window_s == 1.0
    assert policy.max_frames_per_network_window == 20


@pytest.mark.parametrize(
    "changes",
    [
        {"network_window_s": 0.0},
        {"max_frames_per_network_window": 0},
    ],
)
def test_tx_policy_rejects_non_positive_limits(changes: dict[str, int | float]) -> None:
    with pytest.raises(ValueError, match="TX policy"):
        TxPolicyConfig(**changes)
