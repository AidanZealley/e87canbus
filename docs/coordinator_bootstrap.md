# Coordinator Bootstrap

Target OS: Raspberry Pi OS Lite.

Run on the Pi:

```bash
sudo ./scripts/coordinator_bootstrap.sh \
  --repo-url git@github.com:<owner>/<repo>.git \
  --branch main \
  --can-interface can0 \
  --bitrate 100000 \
  --oscillator 12000000 \
  --interrupt 25 \
  --spi-max-frequency 2000000
```

Defaults:

- CAN interface: `can0`.
- Bitrate: `100000` (the eventual K-CAN rate).
- MCP2515 overlay: `oscillator=12000000`, `interrupt=25`, `spimaxfrequency=2000000`.
- Repo directory: `/opt/e87canbus`.
- Service user: `pi`.

The script installs system packages, installs `uv` for the service user if missing, enables SPI in the active boot config, clones or updates the repo, runs `uv sync`, installs `/usr/local/bin/e87canbus-can-up`, and enables `e87canbus.service`.

Reboot after bootstrap so the MCP2515 overlay is applied:

```bash
sudo reboot
```

After reboot, confirm SocketCAN exists:

```bash
ip -details link show can0
```

This bootstrap path configures the current single-interface bench service. The live coordinator's
default configuration also expects `can1` and `can2`; provision and bring up those interfaces
before running `uv run e87canbus`.
