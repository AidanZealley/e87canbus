"""Button-pad vocabulary: what a command is, what a profile is, what the pad displays.

Read in this order:

- ``catalogue`` - the list of assignable commands. The file you edit to add one.
- ``commands``  - behaviour derived from that list: codec, LED semantics, config checks.
- ``profiles``  - a profile as sixteen slots, its storage codec, and the running pad.
- ``repository``- the durable-storage boundary profiles are loaded and saved through.
- ``pad``       - the resolved LED track program the physical pad is sent.

These are values and rules only. Turning them into what the pad should show right now
lives one layer up, in ``domain.controller.button_leds``.
"""
