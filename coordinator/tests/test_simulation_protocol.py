import math

import pytest
from e87canbus.application.events import (
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SpeedObserved,
)
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.simulation.protocol import (
    MAX_SIMULATED_ENGINE_RPM,
    SIMULATION_ONLY_COOLANT_TEMPERATURE_ID,
    SIMULATION_ONLY_ENGINE_RPM_ID,
    SIMULATION_ONLY_OIL_TEMPERATURE_ID,
    SimulationProtocolRouter,
    decode_simulated_high_beam_command,
    encode_simulated_coolant_temperature,
    encode_simulated_engine_rpm,
    encode_simulated_high_beam_command,
    encode_simulated_oil_temperature,
    encode_simulated_speed,
)


@pytest.mark.parametrize("enabled", [False, True])
def test_simulated_high_beam_command_is_private_extended_kcan_frame(enabled: bool) -> None:
    frame = encode_simulated_high_beam_command(enabled)

    assert frame.is_extended_id is True
    assert frame.data == bytes((int(enabled),))
    assert decode_simulated_high_beam_command(frame) is enabled
    assert ProtocolRouter().decode(RoutedCanFrame(CanNetwork.KCAN, frame), 1.0) is None
    assert SimulationProtocolRouter().decode(RoutedCanFrame(CanNetwork.KCAN, frame), 1.0) is None


@pytest.mark.parametrize("enabled", [0, 1, "true"])
def test_simulated_high_beam_command_rejects_non_boolean_values(enabled: object) -> None:
    with pytest.raises(ValueError, match="high-beam command"):
        encode_simulated_high_beam_command(enabled)  # type: ignore[arg-type]


@pytest.mark.parametrize("rpm", [0, 3500, MAX_SIMULATED_ENGINE_RPM])
def test_simulated_engine_rpm_round_trips_on_ptcan(rpm: int) -> None:
    event = SimulationProtocolRouter().decode(
        RoutedCanFrame(CanNetwork.PTCAN, encode_simulated_engine_rpm(rpm)),
        12.5,
    )

    assert isinstance(event, EngineRpmObserved)
    assert (event.sample.rpm, event.sample.observed_at, event.sample.source_network) == (
        rpm,
        12.5,
        CanNetwork.PTCAN,
    )


@pytest.mark.parametrize(
    ("encoder", "event_type", "temperature_c"),
    [
        (encode_simulated_oil_temperature, OilTemperatureObserved, -40.0),
        (encode_simulated_oil_temperature, OilTemperatureObserved, -12.3),
        (encode_simulated_oil_temperature, OilTemperatureObserved, 112.5),
        (encode_simulated_coolant_temperature, CoolantTemperatureObserved, 0.0),
        (encode_simulated_coolant_temperature, CoolantTemperatureObserved, 250.0),
    ],
)
def test_simulated_temperature_round_trips_at_tenth_degree_resolution(
    encoder,
    event_type,
    temperature_c: float,
) -> None:
    event = SimulationProtocolRouter().decode(
        RoutedCanFrame(CanNetwork.PTCAN, encoder(temperature_c)),
        5.0,
    )

    assert isinstance(event, event_type)
    assert event.sample.temperature_c == temperature_c
    assert event.sample.source_network is CanNetwork.PTCAN


@pytest.mark.parametrize("rpm", [-1, 12_001, True, 10.5])
def test_simulated_engine_rpm_encoder_rejects_invalid_values(rpm: object) -> None:
    with pytest.raises(ValueError, match="engine RPM"):
        encode_simulated_engine_rpm(rpm)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "temperature_c",
    [-40.1, 250.1, True, math.nan, math.inf, -math.inf],
)
def test_simulated_temperature_encoder_rejects_invalid_values(
    temperature_c: object,
) -> None:
    with pytest.raises(ValueError, match="simulated temperature"):
        encode_simulated_oil_temperature(temperature_c)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "frame",
    [
        CanFrame(SIMULATION_ONLY_ENGINE_RPM_ID, b"\x00", is_extended_id=True),
        CanFrame(SIMULATION_ONLY_ENGINE_RPM_ID, b"\xff\xff", is_extended_id=True),
        CanFrame(SIMULATION_ONLY_OIL_TEMPERATURE_ID, b"\x00", is_extended_id=True),
        CanFrame(SIMULATION_ONLY_COOLANT_TEMPERATURE_ID, b"\xff\x7f", is_extended_id=True),
    ],
)
def test_simulation_router_rejects_malformed_recognized_payloads(frame: CanFrame) -> None:
    with pytest.raises(ValueError, match="payload"):
        SimulationProtocolRouter().decode(RoutedCanFrame(CanNetwork.PTCAN, frame), 1.0)


@pytest.mark.parametrize(
    "routed",
    [
        RoutedCanFrame(CanNetwork.FCAN, encode_simulated_engine_rpm(3500)),
        RoutedCanFrame(
            CanNetwork.PTCAN,
            CanFrame(SIMULATION_ONLY_ENGINE_RPM_ID, b"\xac\x0d"),
        ),
    ],
)
def test_simulation_router_ignores_wrong_network_and_standard_frames(
    routed: RoutedCanFrame,
) -> None:
    assert SimulationProtocolRouter().decode(routed, 1.0) is None


@pytest.mark.parametrize(
    "frame",
    [
        encode_simulated_engine_rpm(3500),
        encode_simulated_oil_temperature(112.5),
        encode_simulated_coolant_temperature(98.0),
    ],
)
def test_live_router_ignores_all_synthetic_engine_frames(frame: CanFrame) -> None:
    assert ProtocolRouter().decode(RoutedCanFrame(CanNetwork.PTCAN, frame), 1.0) is None


def test_simulated_speed_network_is_configurable_without_accepting_it_on_both_buses() -> None:
    router = SimulationProtocolRouter(synthetic_speed_network=CanNetwork.KCAN)
    frame = encode_simulated_speed(42.5)

    event = router.decode(RoutedCanFrame(CanNetwork.KCAN, frame), 12.5)

    assert isinstance(event, SpeedObserved)
    assert event.sample.source_network is CanNetwork.KCAN
    assert router.decode(RoutedCanFrame(CanNetwork.FCAN, frame), 12.5) is None
