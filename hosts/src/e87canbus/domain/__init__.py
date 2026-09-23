"""Pure values and transitions for coordinator-owned state.

The domain defines immutable vehicle observations, desired steering state, steering
curves, button profiles and operator intents. The controller package applies one
input at a time and projects complete browser state. Time enters through inputs;
no domain module reads a clock or performs I/O.

The kernel owns the current state. The service serializes HTTP requests, vehicle
frames and timer inputs before dispatching them to the kernel. A button press has
no physical or simulated producer until a later independent-device slice adds its
HTTP route; direct tests still exercise the retained press-to-intent path.
"""
