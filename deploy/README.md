# Raspberry Pi controller operation

The supported Pi deployment is one `systemd` service running the canonical `e87canbus` command.
It binds to loopback and serves the built frontend, HTTP API and Socket.IO transport from the same
origin. The service is unauthenticated and must not be changed to a non-loopback bind without a
separate security decision.

## Install

Create the service account and application directories using the distribution's normal account
tools, then place the repository at `/opt/e87canbus`. The account needs read/execute access to that
tree and read/write access only to `/var/lib/e87canbus`. Install dependencies and build the frontend:

```bash
cd /opt/e87canbus
uv sync --frozen
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

Install the checked-in service and explicit environment file:

```bash
sudo install -o root -g root -m 0644 deploy/systemd/e87canbus-controller.service /etc/systemd/system/
sudo install -o root -g e87canbus -m 0640 deploy/systemd/controller.env.example /etc/e87canbus/controller.env
sudo install -d -o e87canbus -g e87canbus -m 0750 /var/lib/e87canbus
sudo systemctl daemon-reload
sudo systemctl enable --now e87canbus-controller.service
```

Configure `can0`, `can1` and `can2` independently before starting the service. The application does
not create interfaces, change bitrates, grant device permissions or enable transmission. Default
live composition has no application CAN transmit grant. Use operating-system and CAN-hardware
listen-only configuration as an additional defense.

## Operate

```bash
systemctl status e87canbus-controller.service
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
journalctl -u e87canbus-controller.service -f
sudo systemctl restart e87canbus-controller.service
sudo systemctl stop e87canbus-controller.service
```

`/health/live` proves the ASGI event loop responds. `/health/ready` returns `200` only after database
migration/load, controller startup and publisher startup; it returns `503` during fatal failure or
shutdown. A browser disconnect does not make the controller unready. A fatal controller exit makes
the CLI return non-zero, and `Restart=on-failure` waits five seconds before restarting it. Logs are
written to the journal. High-rate queue warnings are logarithmically rate-limited. The complete
failure-owner table, diagnostic bounds and recorded simulated soak/restart evidence are in
[`docs/reliability.md`](../docs/reliability.md).

## Upgrade and rollback

Stop the service, back up `/var/lib/e87canbus/application.sqlite3` and its WAL/SHM files as one
SQLite set, update the repository, run `uv sync --frozen`, rebuild `frontend/dist`, and restart.
Check both health endpoints and the journal after restart. A newer database migration fails closed;
restore the matching application version and database backup together for rollback. Durable
settings and profiles live in the configured SQLite file. Live telemetry, traces and socket traffic
are process-local and are deliberately not restored.

Development simulator routes are not registered in live composition. Production live mode also
has no development CORS origins; same-origin browser requests remain allowed. The service unit does
not start Chromium or a kiosk session. Direct SPA routes such as `/dev` and `/car` serve the built
entry document, while missing assets and unknown API/health/socket routes remain 404.
