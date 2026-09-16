# Console display interference

## Observed behavior

The console's DSI display assembly can severely reduce 2.4 GHz Wi-Fi reception when it is close to
the Raspberry Pi 4 antenna. A controlled disconnect, reconnect and disconnect test found that the
console repeatedly discovered and joined the coordinator with the display ribbon disconnected.
With the ribbon connected and the display enabled, the 2.4 GHz scan census collapsed and the
coordinator disappeared. The 5 GHz scan census did not change.

Moving the powered display away from the Pi while keeping the DSI ribbon connected restored the
production WPA2-RSN, CCMP and required-PMF connection. This rules out the earlier kernel, firmware
and NetworkManager diagnoses for that failure. The accepted images use the kernel and firmware
selected by the pinned Raspberry Pi Trixie image layers.

## Required hardware work

Design and validate a mounting arrangement that keeps the display assembly far enough from the Pi
antenna for reliable 2.4 GHz operation. A disconnected display is not an acceptable configuration,
and the existing test does not establish 5 GHz as a replacement.

Validation must use the production console and coordinator assembly. Confirm repeated discovery,
association and authenticated application traffic with the display enabled, then record the
physical spacing and orientation used by the final mount.
