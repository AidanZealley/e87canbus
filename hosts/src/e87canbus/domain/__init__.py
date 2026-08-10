"""The pure heart of the coordinator: values, rules and decisions, no I/O.

Nothing here opens a socket, touches SQLite, reads a clock or starts a thread. Every
function is deterministic: given the same inputs it returns the same outputs, which is
why the whole domain is testable without a CAN bus or a car. Time arrives as an
explicit argument, never from ``time.monotonic()``.


Two layers, and the direction between them
------------------------------------------

**Vocabulary** - the packages and modules directly in ``domain/``. These are the nouns:
what a steering curve *is*, what a button profile *is*, what an event *is*, and the
validation and encoding that go with them. Grouped by feature:

    buttons/    assignable commands, profiles, the pad's LED program
    steering/   assistance curves
    devices/    device roles and their registry lifecycle
    settings/   user-configurable application settings

plus the shared spine that every feature depends on:

    state       the authoritative application state, as immutable values
    events      the closed set of things that happen and effects that result
    intents     what an operator can ask for, independent of how they asked
    timestamps  canonical UTC formatting for anything persisted
    revisioned_profiles
                the optimistic-concurrency vocabulary buttons and steering share

**Decisions** - ``domain/controller/``. These are the verbs: pure functions from state
plus an input to the next state plus the effects it implies. The reducer, applying
operator intents, the snapshot projection, the LED projection, the steering command
math.

The dependency runs one way and is enforced by the import graph: ``controller`` imports
vocabulary, and no vocabulary module imports ``controller``. If you find yourself
wanting the reverse, the thing you are reaching for is a value and belongs in the
vocabulary layer.

A feature usually appears in both layers, and that is the intended shape rather than a
split to tidy up. Steering is the clearest example: ``steering/curves.py`` says what a
curve is, ``controller/steering.py`` says what assistance to command right now.
``buttons/profiles.py`` and ``controller/button_leds.py`` are the same pairing.


Where the rest of the system sits
---------------------------------

The domain decides; everything outside it arranges for those decisions to happen and
carries them out.

    kernel/     owns the state, feeds one input at a time into the domain and turns
                each result into a Commit: new snapshot, effects to perform, topics
                that changed. Single-owner and single-threaded by construction.
    service/    runs the kernel: one thread, a bounded inbox, timer scheduling and a
                start/stop lifecycle. Nothing else may mutate the kernel.
    runners/    the two things the kernel can drive - real CAN hardware (``live``) or
                an in-memory simulated car (``simulation``).
    adapters/   the outside world: SQLite storage, CAN transmission, effect execution.
    api/        HTTP and Socket.IO. Translates requests into kernel inputs and
                snapshots into JSON; holds no rules of its own.
    protocol/   frame encoding and decoding, shared with the firmware in ``devices/``.

So a button press travels: CAN frame -> ``protocol`` decodes -> ``kernel`` asks
``domain.controller`` what it means -> Commit -> ``adapters`` transmit the resulting
LED program. A profile edit travels: HTTP -> ``api`` -> ``adapters`` persist ->
``kernel`` input -> the same Commit path.
"""
