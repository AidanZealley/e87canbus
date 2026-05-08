# Custom CAN IDs

These IDs are for the private Pi-to-Arduino project bus. They are not BMW bus IDs.

| ID | Direction | Purpose | Payload |
|---|---|---|---|
| `0x700` | Arduino to Pi | Button event | byte 0 = button index, byte 1 = state |
| `0x701` | Pi to Arduino | LED update | byte 0 = button index, byte 1 = colour code |

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

`arduino/neotrellis_node/include/can_ids.h` must manually mirror this document.

