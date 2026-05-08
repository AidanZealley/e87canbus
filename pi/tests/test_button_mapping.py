from e87canbus.button_mapping import ActionType, map_mfl_event
from e87canbus.events import ButtonState, MflButton, MflButtonEvent


def test_symbolic_mfl_buttons_map_to_actions() -> None:
    assert (
        map_mfl_event(MflButtonEvent(MflButton.VOLUME_UP, ButtonState.PRESSED)).action_type
        is ActionType.MANUAL_ASSISTANCE_LEVEL_UP
    )
    assert (
        map_mfl_event(MflButtonEvent(MflButton.VOLUME_DOWN, ButtonState.PRESSED)).action_type
        is ActionType.MANUAL_ASSISTANCE_LEVEL_DOWN
    )
    assert (
        map_mfl_event(MflButtonEvent(MflButton.PHONE_PICKUP, ButtonState.PRESSED)).action_type
        is ActionType.HIGH_BEAM_STROBE
    )
    assert (
        map_mfl_event(MflButtonEvent(MflButton.PHONE_HANGUP, ButtonState.PRESSED)).action_type
        is ActionType.DSC_OFF_REQUEST
    )


def test_unmapped_or_release_buttons_return_none() -> None:
    assert map_mfl_event(MflButtonEvent(MflButton.NEXT, ButtonState.PRESSED)) is None
    assert map_mfl_event(MflButtonEvent(MflButton.VOLUME_UP, ButtonState.RELEASED)) is None

