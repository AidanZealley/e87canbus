from dataclasses import replace

import pytest
from e87canbus.config import (
    CanNetwork,
    CustomCanIds,
    EngineTelemetryConfig,
    LivePublicationConfig,
    SimulationConfig,
    SteeringConfig,
    TxPolicyConfig,
    default_config,
    simulator_config,
)
from e87canbus.device import (
    DEFAULT_DEVICE_CATALOGUE,
    DeviceLifecycleStatus,
    DeviceRole,
    DeviceSource,
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
    assert default_config().simulation.steering_watchdog_timeout_s == 0.25


def test_default_live_publication_bounds() -> None:
    publication = default_config().live_publication

    assert publication.telemetry_hz == 25.0
    assert publication.health_hz == 1.0
    assert publication.trace_hz == 10.0
    assert publication.trace_batch_size == 100
    assert publication.resource_capacity == 256
    assert publication.client_queue_capacity == 64
    assert publication.send_timeout_s == 1.0
    assert publication.shutdown_timeout_s == 2.0


@pytest.mark.parametrize(
    "changes",
    [
        {"telemetry_hz": 0.0},
        {"health_hz": 0.0},
        {"trace_hz": float("inf")},
        {"trace_batch_size": 0},
        {"resource_capacity": 0},
        {"client_queue_capacity": 0},
        {"send_timeout_s": 0.0},
        {"shutdown_timeout_s": float("nan")},
    ],
)
def test_live_publication_bounds_reject_invalid_values(
    changes: dict[str, int | float],
) -> None:
    with pytest.raises(ValueError, match="live"):
        LivePublicationConfig(**changes)


@pytest.mark.parametrize(
    "field",
    [
        "trace_capacity",
        "steering_watchdog_timeout_s",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_simulation_limits_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValueError, match="capacity|watchdog"):
        SimulationConfig(**{field: value})


def test_steering_level_count() -> None:
    assert default_config().steering.manual_level_count == 8


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
        (LivePublicationConfig, "send_timeout_s"),
        (TxPolicyConfig, "network_window_s"),
    ],
)
def test_duration_configuration_rejects_non_finite_values(
    config: (
        type[SteeringConfig]
        | type[EngineTelemetryConfig]
        | type[SimulationConfig]
        | type[LivePublicationConfig]
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


def test_default_device_catalogue_and_registry_vocabulary() -> None:
    assert tuple(DeviceRole) == (
        DeviceRole.BUTTON_PAD,
        DeviceRole.SERVOTRONIC_CONTROLLER,
    )
    assert tuple(DeviceSource) == (
        DeviceSource.PHYSICAL,
        DeviceSource.EMULATED,
        DeviceSource.DISABLED,
    )
    assert tuple(DeviceLifecycleStatus) == (
        DeviceLifecycleStatus.DISABLED,
        DeviceLifecycleStatus.NOT_FOUND,
        DeviceLifecycleStatus.PENDING,
        DeviceLifecycleStatus.ACTIVE,
        DeviceLifecycleStatus.STALE,
        DeviceLifecycleStatus.INCOMPATIBLE,
        DeviceLifecycleStatus.FAULT,
    )
    assert [
        (entry.identity.role, entry.identity.device_id) for entry in DEFAULT_DEVICE_CATALOGUE
    ] == [
        (DeviceRole.BUTTON_PAD, 1),
        (DeviceRole.SERVOTRONIC_CONTROLLER, 1),
    ]
    assert all(
        entry.enabled and entry.supported_protocol_version == 1
        for entry in DEFAULT_DEVICE_CATALOGUE
    )
    assert all(entry.instance_limit == 1 for entry in DEFAULT_DEVICE_CATALOGUE)


def test_default_custom_can_ids_cover_all_project_messages() -> None:
    ids = CustomCanIds()

    assert (
        ids.button_event,
        ids.led_snapshot,
        ids.button_pad_hello,
        ids.button_pad_welcome_ack,
        ids.button_pad_heartbeat,
        ids.servotronic_controller_hello,
        ids.servotronic_controller_welcome_ack,
        ids.servotronic_controller_heartbeat,
    ) == tuple(range(0x700, 0x708))


@pytest.mark.parametrize(
    "changes",
    [
        {"button_event": -1},
        {"led_snapshot": 0x800},
        {"button_pad_hello": 0x702, "button_pad_welcome_ack": 0x702},
    ],
)
def test_custom_can_ids_reject_invalid_or_duplicate_standard_ids(
    changes: dict[str, int],
) -> None:
    with pytest.raises(ValueError, match="CAN IDs"):
        CustomCanIds(**changes)


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
