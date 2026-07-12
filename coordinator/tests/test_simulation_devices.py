import logging

import pytest
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import (
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    LED_GREEN,
    CanFrame,
    LedUpdatePayload,
    encode_led_update,
)
from e87canbus.simulation.bus import InMemoryCanNetwork
from e87canbus.simulation.devices import SimulatedNeoTrellisNode


def test_neotrellis_alternates_press_and_release_events() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    observer_bus = network.create_bus("observer")
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        button_index=3,
    )

    first = node.send_next_button_event()
    second = node.send_next_button_event()

    assert first == CanFrame(ids.button_event, bytes([3, BUTTON_PRESSED]))
    assert second == CanFrame(ids.button_event, bytes([3, BUTTON_RELEASED]))
    assert observer_bus.receive(timeout_s=0) == first
    assert observer_bus.receive(timeout_s=0) == second


def test_neotrellis_led_update_changes_led_colours() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(encode_led_update(LedUpdatePayload(button_index=2, colour_code=LED_GREEN), ids))

    updates = node.process_pending_led_updates()

    assert updates == [LedUpdatePayload(button_index=2, colour_code=LED_GREEN)]
    assert node.led_colours == {2: LED_GREEN}


def test_neotrellis_ignores_unknown_frame_id() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(CanFrame(0x123, b"\x00\x01"))

    assert node.process_pending_led_updates() == []
    assert node.led_colours == {}


def test_neotrellis_logs_and_ignores_malformed_led_update(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(CanFrame(ids.led_update, b"\x00"))

    with caplog.at_level(logging.WARNING):
        updates = node.process_pending_led_updates()

    assert updates == []
    assert node.led_colours == {}
    assert "sim neotrellis ignored malformed led update" in caplog.text
