from e87canbus.application.events import ButtonState, MflButton, MflButtonEvent
from e87canbus.features.button_mapping import (
    NEOTRELLIS_BUTTON_NOTES,
    ActionType,
    map_mfl_event,
)


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


def test_neotrellis_button_notes_document_active_steering_controls() -> None:
    assert NEOTRELLIS_BUTTON_NOTES == {
        0: "steering mode",
        1: "manual assistance down",
        2: "manual assistance up",
        3: "maximum assistance override",
    }
