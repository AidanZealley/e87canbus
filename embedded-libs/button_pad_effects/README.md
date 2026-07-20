# Button-pad effects

A small, pure C++ renderer shared by NeoTrellis firmware. It accepts resolved-track
commands and renders RGB bytes for the device driver; it has no Arduino or Seesaw
dependency.

Every v2 command is 16 bytes and therefore bounded to the transport's 64 bytes:

| bytes | meaning |
| --- | --- |
| `02`, opcode, mask `u16le` | version, replace-all/set-track opcode, target buttons |
| kind, RGB, parameter A/B `u16le` | solid, blink, or breathe track and its parameters |
| repeat, final RGB | zero repeats forever; positive values finish on final RGB |

A program starts with replace-all, assigns every button exactly once across disjoint
masks, and sets bit 7 on its final opcode to commit. Until commit, existing pixels
remain visible; commit starts changed tracks while byte-identical tracks retain their
existing phase. This provides atomic scenes without a second track buffer. Solid is a
track rather than a separate display mode. Breathe uses a fixed integer triangle
wave so the TypeScript observer renders the same colours.

The normative cross-language vectors live in
`protocol/test-vectors/button-pad-program-v2.json`. Run
`python scripts/test_button_pad_effects_cpp.py` from the repository root to compile
this library as native C++ and verify decoding, animation masks, timer wrap, and
rendered frames against those vectors.
