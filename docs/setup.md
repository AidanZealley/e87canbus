# Setup

## Python

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run lint and type checks:

```bash
uv run ruff check .
uv run mypy pi/e87canbus
```

Run the dry-run CLI:

```bash
uv run e87canbus --dry-run
```

## Arduino

From the PlatformIO project directory:

```bash
cd arduino/neotrellis_node
pio run
```

## Pi CAN

Pi SocketCAN setup, MCP2515 overlays, interface startup, and bus capture workflow are future work. This scaffold should run tests without Raspberry Pi GPIO, SocketCAN, MCP2515, or vehicle CAN access.

