# Simulation

The simulator runs without CAN hardware. Start it with `uv run e87canbus run --profile simulator --reload`, then start the frontend from `frontend` with `pnpm dev`.

The simulator has an in-memory vehicle bus on each enabled CAN network. Vehicle controls emit extended simulation-only CAN frames. The runtime timestamps and decodes those frames through the kernel's normal received-frame input. The car profile does not decode synthetic IDs. The bench profile can use vehicle controls, but injects their frames locally without transmitting on physical CAN.

`PUT /api/dev/simulation/vehicle/speed` selects a speed. The vehicle emits a fresh encoded frame on each timer until `/api/dev/simulation/vehicle/speed/silence` clears it. The sweep control selects a virtual car sweep of speed, RPM and temperatures. No simulator API injects a domain event or steering state directly.

A fresh application database selects one `Default` button profile with sixteen empty slots. No physical or simulated pad produces presses. Steering mode, manual level, maximum override and active curve are desired coordinator state; they produce no Servotronic output. Browser SSE publishes complete projections and reset starts a new simulation session.

The live coordinator creates no transmitter. In-memory and SocketCAN endpoints retain their basic `send` operation for future verified vehicle actions, but current application commands do not call it.
