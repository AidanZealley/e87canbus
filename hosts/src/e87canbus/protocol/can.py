"""CAN frames and observed network identity."""

from dataclasses import dataclass

from e87canbus.config import CanNetwork


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    is_extended_id: bool = False


@dataclass(frozen=True)
class RoutedCanFrame:
    network: CanNetwork
    frame: CanFrame
