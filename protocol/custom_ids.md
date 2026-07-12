# Custom CAN IDs

These IDs are for the private coordinator-to-device project bus. They are not BMW bus IDs.

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
