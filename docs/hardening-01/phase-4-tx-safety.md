# Phase 4 — Transmit safety: deny-by-default TX and rate limiting

## Goal

Make "do not interfere with the car's buses" a property of the code instead of a discipline.
After this phase: the coordinator can only transmit on networks explicitly granted TX in config
(deny by default), and every granted network sits behind a rate limiter that drops and logs
frames exceeding a per-ID gap or a per-network budget. The simulator runs the identical gate, so
flood protection is testable without hardware.

## Why

Today `CoordinatorRuntime._send_outputs` (`runtime.py:74`) sends on any configured bus, and
nothing anywhere limits transmit rate. A single looping bug — or the future strobe feature —
could flood K-CAN at 100 kbit/s and starve real body traffic (the "modules crash" scenario).
Deny-by-default also encodes the intended first in-car deployment posture: listen-only
everywhere, TX granted per network only after captures are verified.

## Design (decided — implement as written)

### Config (`config.py`)

- `CanNetworkConfig` gains `tx_enabled: bool = False`.
- `default_can_networks()` sets `tx_enabled=True` **only for K-CAN** (the project's own devices —
  button pad LEDs — live there). PT-CAN and F-CAN stay receive-only.
- New frozen dataclass:

  ```python
  @dataclass(frozen=True)
  class TxPolicyConfig:
      min_id_gap_s: float = 0.05   # min interval between sends of the same arbitration ID
      max_frames_per_s: int = 20   # total TX budget per network
  ```

  added to `AppConfig` as `tx_policy: TxPolicyConfig = field(default_factory=TxPolicyConfig)`.
  These defaults are deliberately tight — a tiny fraction of K-CAN's ~800 frames/s capacity.
  Features that legitimately need faster cadence (strobe) will justify raising them in their own
  work, in config, where the number is visible.

### Runtime (`runtime.py`)

- `CoordinatorRuntime.__init__` gains `tx_networks: frozenset[CanNetwork] = frozenset()`.
  **The default is deny-all** — composition roots must explicitly grant TX. In `_send_outputs`,
  a routed output whose network is not in `tx_networks` is dropped with a
  `LOGGER.warning("dropped output for tx-disabled network: ...")` in the style of the existing
  warnings there. This is a check and a log line, not a new class.

### Rate limiter (`protocol/can.py`)

- New class `RateLimitedCanBus` in `protocol/can.py`, next to the `CanBus` protocol it
  implements. It wraps any `CanBus` — this is the same object shape, not a new layer:

  ```python
  class RateLimitedCanBus:
      def __init__(self, bus: CanBus, policy: TxPolicyConfig,
                   clock: Callable[[], float] = time.monotonic) -> None: ...
      def send(self, frame: CanFrame) -> None: ...      # drops + warns on violation
      def receive(self, timeout_s: float | None = None) -> CanFrame | None: ...  # passthrough
  ```

- Enforcement, simplest readable implementation:
  - per-ID gap: `dict[int, float]` of last send time per arbitration ID.
  - per-network budget: `deque[float]` of send timestamps; evict entries older than 1 s; refuse
    when `len(deque) >= max_frames_per_s`.
- On violation: **drop the frame and log a warning** — never queue. Queuing hides floods and
  delivers stale commands later; the LED protocol is idempotent state, so a dropped frame is
  corrected by the next update. Put that reasoning in a short comment on the drop path — it is a
  constraint the code cannot show.
- Allowed sends update both structures; dropped sends update neither.

### Composition (`simulation/controller.py`)

In `_build_session`:

- Build `tx_networks` from `config.can_networks` (`frozenset` of networks with `tx_enabled`) and
  pass it to `CoordinatorRuntime`.
- Wrap each **TX-enabled** Pi bus in `RateLimitedCanBus` with `config.tx_policy` and the
  controller's clock (from phase 3) before handing the bus mapping to the runtime. Receive-only
  buses stay unwrapped.

The simulated device nodes (`neotrellis`, `simulated-car`, `steering-controller`) are **not**
rate limited — they model external hardware whose behaviour we do not control; the gate protects
what *the coordinator* transmits.

## Tasks

1. Config changes + update `tests/test_config.py` (assert K-CAN is the only default TX network).
2. Runtime `tx_networks` gate + tests: output on a granted network sends; same output with the
   default deny-all drops and warns (`caplog`); existing runtime tests updated to grant
   `{CanNetwork.KCAN}` where they assert LED sends.
3. `RateLimitedCanBus` + tests, all with a fake clock: same-ID send inside the gap drops, after
   the gap passes; different IDs are independent for the gap rule but share the budget; the
   budget refills as the 1 s window slides; `receive` passes through untouched.
4. Wire up the simulator composition + one end-to-end test: hammer `press_button`/
   `release_button` on the `SimulatorController` fast enough (fake clock held still) that the
   budget trips, and assert the trace shows the coordinator's LED replies stop while button
   events keep flowing — proving the gate sits only on the Pi's TX path.
5. Docs: add a short "Transmit safety" subsection to `docs/simulation.md`'s Safety Boundary
   section and a sentence to `coordinator/README.md`. Mention deny-by-default and the config
   fields.

## Out of scope

- Live SocketCAN wiring of the gate (phase 6 composes it for real interfaces).
- Kernel-level listen-only mode (an `ip link` concern for deployment docs, not Python).
- Raising the default budgets for any feature.

## Acceptance criteria

- A `CoordinatorRuntime` constructed without `tx_networks` cannot transmit on any bus (test).
- Rate-limit tests are fully deterministic (fake clock; no sleeps).
- The simulator still passes all existing behaviour tests — normal workbench interaction stays
  well under the default budgets.
- All checks pass: pytest, mypy, ruff.
