from dataclasses import replace

import pytest
from e87canbus.config import (
    CanNetwork,
    EngineTelemetryConfig,
    SimulationConfig,
    SteeringConfig,
    TxPolicyConfig,
    default_config,
    simulator_config,
)


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
    assert default_config().simulation.command_queue_capacity == 64
    assert default_config().simulation.steering_watchdog_timeout_s == 0.25
    assert default_config().simulation.websocket_send_timeout_s == 1.0


@pytest.mark.parametrize(
    "field",
    [
        "trace_capacity",
        "command_queue_capacity",
        "steering_watchdog_timeout_s",
        "websocket_send_timeout_s",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_simulation_limits_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValueError, match="capacity|watchdog|WebSocket"):
        SimulationConfig(**{field: value})


def test_custom_can_ids() -> None:
    config = default_config()

    assert config.custom_can_ids.button_event == 0x700
    assert config.custom_can_ids.led_snapshot == 0x701


def test_steering_level_count() -> None:
    assert default_config().steering.manual_level_count == 8


@pytest.mark.parametrize(
    "config",
    [
        SteeringConfig(manual_level_count=1),
        SteeringConfig(speed_timeout_s=0.1),
    ],
)
def test_valid_steering_configuration(config: SteeringConfig) -> None:
    assert config.manual_level_count >= 1
    assert config.speed_timeout_s > 0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"manual_level_count": 0}, "manual_level_count"),
        ({"speed_timeout_s": 0.0}, "speed_timeout_s"),
    ],
)
def test_steering_configuration_rejects_invalid_values(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SteeringConfig(**changes)  # type: ignore[arg-type]


def test_default_tick_and_speed_timeout_intervals() -> None:
    config = default_config()

    assert config.tick_interval_s == 0.1
    assert config.steering.speed_timeout_s == 1.0
    assert config.engine_telemetry.timeout_s == 1.0
    assert config.engine_telemetry is not config.steering


@pytest.mark.parametrize("tick_interval_s", [0.0, -0.1, float("inf"), float("nan")])
def test_tick_interval_must_be_positive(tick_interval_s: float) -> None:
    with pytest.raises(ValueError, match="tick_interval_s"):
        replace(default_config(), tick_interval_s=tick_interval_s)


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


@pytest.mark.parametrize("value", [float("inf"), float("nan")])
@pytest.mark.parametrize(
    ("config", "field"),
    [
        (SteeringConfig, "speed_timeout_s"),
        (EngineTelemetryConfig, "timeout_s"),
        (SimulationConfig, "steering_watchdog_timeout_s"),
        (SimulationConfig, "websocket_send_timeout_s"),
        (TxPolicyConfig, "network_window_s"),
    ],
)
def test_duration_configuration_rejects_non_finite_values(
    config: (
        type[SteeringConfig]
        | type[EngineTelemetryConfig]
        | type[SimulationConfig]
        | type[TxPolicyConfig]
    ),
    field: str,
    value: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        config(**{field: value})


@pytest.mark.parametrize("timeout_s", [0.0, -1.0])
def test_engine_telemetry_timeout_must_be_positive(timeout_s: float) -> None:
    with pytest.raises(ValueError, match="engine telemetry timeout"):
        EngineTelemetryConfig(timeout_s)


@pytest.mark.parametrize("value", [float("inf"), float("nan")])
def test_runtime_latency_warning_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        replace(default_config(), runtime_queue_latency_warning_s=value)


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
