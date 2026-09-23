"""Button profile vocabulary and authored presentation.

Read in this order:

- ``catalogue`` - the list of assignable commands. The file you edit to add one.
- ``commands``  - behaviour derived from that list: codec, LED semantics, config checks.
- ``profiles``  - a profile as sixteen slots and its storage codec.
- ``repository``- the durable-storage boundary profiles are loaded and saved through.

The profile stores presentation choices without producing a device program.
"""
