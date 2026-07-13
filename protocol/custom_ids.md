# Custom CAN IDs

These provisional project messages run on K-CAN; there is no private project bus. They are enabled
only in simulation and bench tooling in this milestone.

The default live coordinator has application transmission disabled on every network. A future live
grant for these IDs requires collision validation; SocketCAN kernel or hardware listen-only mode is
a separate deployment defense.

| ID | Direction | Purpose | Payload |
|---|---|---|---|
| `0x700` | Button pad to coordinator | Button event | byte 0 = button index, byte 1 = state |
| `0x701` | Coordinator to button pad | LED update | byte 0 = button index, byte 1 = colour code |

## Button State Constants

| Value | Meaning |
|---|---|
| `0x00` | released |
| `0x01` | pressed |

## LED Colour Codes

| Value | Meaning |
|---|---|
| `0x00` | off |
| `0x01` | red |
| `0x02` | green |
| `0x03` | blue |
| `0x04` | amber |
| `0x05` | white |

`devices/button-pad/include/can_ids.h` must manually mirror this document.

`0x700` and `0x701` require collision validation against a real K-CAN capture before any in-car
transmission. Their location in the high standard-ID range is not evidence that they are unused by
the vehicle.
