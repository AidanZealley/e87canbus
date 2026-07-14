# ADR 0004: Generate repository-owned protocol artifacts from one source

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

The repository-owned button-pad protocol was repeated in Python, firmware headers, and Markdown.
Tests covering a subset of constants could not prevent payload lengths, byte positions, or state
values from drifting between participants.

## Decision

`protocol/custom.toml` is the sole editable definition of provisional custom CAN IDs, payload
layouts, button states, and LED colour codes. `scripts/generate_custom_protocol.py` produces the
Python constants module, firmware header, and marked tables in the protocol documentation. Its
`--check` mode and tests fail on single-artifact drift.

Wire codecs remain direct, domain-neutral functions. Application/domain modules do not import the
wire protocol, and generated values do not grant live deployment authority.

## Consequences

- Cross-language protocol changes are coordinated through one reviewable input.
- Generated files must not be edited independently.
- Protocol generation is part of verification whenever the custom definition changes.
- The provisional `0x700` and `0x701` IDs still require collision validation before in-car use.
