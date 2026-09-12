# Setup

## Coordinator and console Raspberry Pis

Use the [provisioning runbook](../deploy/README.md) for blank coordinator and console SD cards.
Provisioning is the only supported setup path. The reusable images contain stable OS, CAN,
network, kiosk and first-boot behavior; the per-card bundle supplies the current application,
installation identity, device identity and secrets. The [image runbook](../images/README.md)
documents the image contents and temporary physical-check helper.

## Local development

Install dependencies and run the checks:

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy
uv run python scripts/generate_custom_protocol.py --check
```

Run the visual simulator in three terminals:

```bash
uv run e87canbus run --profile simulator --reload
uv run e87canbus-console --port 8001
cd frontend && pnpm dev
```

The closed application profiles remain `car`, `bench` and `simulator`. Physical host selection and
device secrets belong to provisioning, not application CLI flags.

## Device firmware

Build and upload the button pad:

```bash
cd devices/button-pad
pio run
cd ../..
./scripts/button_pad_upload.sh
```

Build and upload the coordinator panel with its complete four-wire Pi harness disconnected:

```bash
cd devices/coordinator-panel
pio run -e qtpy_rp2040
cd ../..
./scripts/coordinator_panel_upload.sh
```

Set `UPLOAD_PORT=/dev/cu.usbmodemXXXX` or the matching Linux device when more than one board is
connected. The panel's first upload may require manually entering the RP2040 bootloader. See its
[board-specific instructions](../devices/coordinator-panel/README.md).

## Capture physical CAN traffic

From a provisioned coordinator on a safe bench or vehicle setup:

```bash
./scripts/capture_can.sh ccc-knob
```

The capture helper validates `kcan`, stops the coordinator to prevent application transmissions,
records until Ctrl-C, and restores the prior service state. It writes captures outside the checkout
under `~/e87canbus-captures/` by default.
