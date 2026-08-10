"""Steering vocabulary: assistance curves and the storage boundary for saved ones.

- ``curves``     - curve values, interpolation, fingerprints and activation status.
- ``repository`` - the durable-storage boundary saved curves are loaded and saved through.

Computing the assistance command to send for a given state lives one layer up, in
``domain.controller.steering``.
"""
