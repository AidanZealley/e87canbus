from e87canbus.config import default_config


def test_default_can_bitrates() -> None:
    config = default_config()

    assert config.can_bitrates.kcan == 100_000
    assert config.can_bitrates.fcan == 500_000


def test_custom_can_ids() -> None:
    config = default_config()

    assert config.custom_can_ids.button_event == 0x700
    assert config.custom_can_ids.led_update == 0x701


def test_steering_level_count() -> None:
    assert default_config().steering.manual_level_count == 8

