import math

import pytest
from e87canbus.config import CanNetwork
from e87canbus.domain.events import (
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SpeedObserved,
)
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.runners.simulation.protocol import (
    MAX_SIMULATED_ENGINE_RPM,
    SimulationProtocolRouter,
    encode_simulated_coolant_temperature,
    encode_simulated_engine_rpm,
    encode_simulated_oil_temperature,
    encode_simulated_speed,
)


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


def test_simulated_speed_network_is_configurable_without_accepting_it_on_both_buses() -> None:
    router = SimulationProtocolRouter(synthetic_speed_network=CanNetwork.KCAN)
    frame = encode_simulated_speed(42.5)

    event = router.decode(RoutedCanFrame(CanNetwork.KCAN, frame), 12.5)

    assert isinstance(event, SpeedObserved)
    assert event.sample.source_network is CanNetwork.KCAN
    assert router.decode(RoutedCanFrame(CanNetwork.FCAN, frame), 12.5) is None
