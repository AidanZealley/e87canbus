import pytest
from e87canbus.domain.events import (
    SetSteeringAssistance,
    SteeringCommandReason,
)


def test_steering_effect_rejects_out_of_range_assistance() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        SetSteeringAssistance(1.1, SteeringCommandReason.MAXIMUM)
