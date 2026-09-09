# Raspberry Pi image-building whole-feature review

Status: accepted.

## Reviewer task packet

Review the full integration branch against the starting commit and the approved image-building
specification. Read the accepted handoffs, but independently inspect the combined diff and
surrounding deployment code.

Audit specification completeness, Docker privilege and mount boundaries, pinning, cache and
artifact behavior, manifest integrity, common and role ownership, secret exclusion, first-boot
behavior, service failure modes, Pi 4 hardware assumptions, duplicated setup state, test value and
documentation agreement.

Confirm that generated images and credentials are absent from Git. Check that the existing setup
scripts remain a deliberate migration fallback rather than a second undocumented image builder.
Treat the recorded MacBook, Imager and Pi results as external evidence. Do not infer hardware
success from structural tests.

Run proportionate whole-feature checks:

```bash
uv run pytest
uv run ruff check .
uv run mypy
uv run python scripts/generate_custom_protocol.py --check
cd frontend && pnpm api:check && pnpm lint && pnpm typecheck && pnpm test
```

If frontend dependencies are unavailable and the branch did not change frontend code or generated
contracts, record those checks as not run and justify that decision. Do not install or update
dependencies solely for review.

## Initial whole-feature review

- Reviewer: Codex (`gpt-5.6-sol`), fresh whole-feature reviewer.
- Branch, base and reviewed head: `feature/pi-image-building`, starting commit
  `f2601794236cca66d71d7b6389a820fc5064312b`, clean reviewed head
  `a21d4f535b98d8817e0b94198ed738bd022965bd`.
- Verification run: `uv run pytest` passed (`882 passed`); `uv run ruff check .` passed; `uv run
  mypy` passed (`130 source files`); `uv run python scripts/generate_custom_protocol.py --check`
  passed; and `cd frontend && pnpm api:check && pnpm lint && pnpm typecheck && pnpm test` passed
  (`6` coordinator-client files with `18` tests, `24` console files with `101` tests and `21`
  coordinator files with `89` tests). Shell syntax checks passed for the builder, both role hooks
  and the checkpoint script. `git diff --check` passed. The three project layers passed metadata
  lint with pinned `rpi-image-gen` commit `262d4df5a9f9d4133370465399a7958a7c22cdc7`.
- Acceptance-criteria audit: The two public commands share the pinned arm64 Docker builder. The
  repository bind is read-only; `/work` and `/tmp` use disposable Docker volumes; the package
  cache uses one named volume; and only staged output crosses a writable host bind. The builder
  rejects unsupported host and container architectures, keeps the Debian sources on the dated
  snapshot, records the documented rolling Raspberry Pi archive limitation and publishes a
  cleanup-protected image and manifest pair with one computed digest. Generated image state is
  ignored and absent from Git. Both roles consume one common definition, copy canonical runtime
  assets from `deploy/`, contain no application, credential, repository clone or operator account,
  and run no package or application build on first boot. Role boot, CAN, UART, network, display and
  inactive-application expectations agree with the fallback installers and passed Aidan's recorded
  M1 Pro, Raspberry Pi Imager and Pi 4 checks. The role images came from clean commit `c80a9f6`;
  every later commit through the reviewed head changes only the test-card checker, runbook, focused
  tests and workflow records, so the hardware evidence still covers all image-producing source.
  The first-boot provisioning behavior and test-card cleanup exception below prevent full
  acceptance.
- Required findings by owner:
  1. **Workstream 2, common host image:** The approved product specification says each image
     contains the one-time provisioning service that consumes the application and provisioning
     bundles after the CLI places them on the boot partition. The implementation provides only
     `/usr/share/e87canbus/provisioning-interface` and a protected `unprovisioned` marker. No unit
     or executable can validate or consume boot-partition inputs, install the application and
     identity, remove consumed secrets, clear the marker or start the role services. This leaves
     the images unable to enter their specified provisioned state without rebuilding them or
     adding an undocumented ext4 mutation path. The same gap leaves upstream's build-time random
     hostname, observed as `pi4-ocegvv` on the console, shared by every card flashed from that
     artifact rather than replaced with per-host provisioning data. Either implement the smallest
     image-side service contract that does not pre-empt the still-open bundle format, or record an
     explicit approved specification change that moves the service into the later provisioning
     task. Add focused coverage for the chosen executable lifecycle, secret cleanup, marker
     transition and host-identity boundary.
  2. **Workstream 5, hardware acceptance:** The runbook and workstream acceptance criteria require
     confirmation that `systemd.debug_shell=1` and the copied checkpoint script were removed from
     each tested card, or that each card was reflashed. The record contains the successful build,
     flash and Pi checks but no cleanup confirmation. Record Aidan's result before treating the
     hardware gate as fully closed. This does not invalidate either image artifact because the
     debug shell and script changed only the flashed test cards.
- Optional observations: Most image tests assert source strings. The one-off synthetic-root and
  resolved-pipeline checks recorded in the workstreams give useful evidence, but they are not part
  of the repository suite. When correcting the first-boot boundary, prefer one behavioral hook or
  assembled-root test over adding more source-string assertions. The documented rolling Raspberry
  Pi archive is an accepted reproducibility limit because the manifest digest identifies each
  result.
- Questions: Did Aidan explicitly approve marker-only provisioning as a change to the product
  specification, or did the workstream plan mistake a lifecycle marker for the required
  first-boot service? The open provisioning-bundle format makes that distinction architectural and
  should be settled during triage rather than inferred by remediation.
- Verdict: Changes required. The Docker builder and both role images are well supported by
  automated and physical evidence, but the missing image-side provisioning path is a product-spec
  gap and the temporary debug-shell cleanup evidence remains unrecorded.

## Orchestrator triage

- Accepted findings and owners:
  1. Workstream 2 owned the provisioning-boundary finding. Aidan chose to keep this feature small
     rather than decide the still-open bundle, validation and secret-lifecycle contracts here. The
     image-building and provisioning specifications now say plainly that the validated v1
     artifacts are host-image prototypes with a protected marker and fail-closed role services,
     not provisionable images. The provisioning feature must add the image-side consumer, rebuild
     the images and repeat relevant hardware checks before it ships.
  2. Workstream 5 owned the test-card cleanup evidence. Aidan confirmed on 2026-09-09 that both
     cards were returned to their original flashed state and retain neither
     `systemd.debug_shell=1` nor the copied checker.
- Rejected findings and reasons: None.
- Deferred optional observations: Do not broadly replace the structural image tests. The final
  cleanup moved the low-level hardware assertions out of duplicated runbook blocks and made the
  checkpoint script their sole executable source. The remaining source assertions protect static
  image composition that the local suite cannot execute without Docker and a built rootfs.
- Drift requiring user decision: Resolved. Aidan approved deferring the first-boot consumer to the
  provisioning feature. Workstream 2 and both product specifications record the resulting image
  rebuild and hardware-recheck obligation.

## Focused closure

- Reviewed head: Uncommitted remediation diff on
  `a21d4f535b98d8817e0b94198ed738bd022965bd`.
- Finding outcomes: Both accepted findings are closed. Aidan's approved scope change is explicit
  and consistent across the image-building and provisioning specifications, workstream 2,
  `images/README.md`, `docs/setup.md` and `deploy/README.md`. They identify the v1 artifacts as
  validated, fail-closed prototypes that retain one build-time hostname across cards and cannot be
  provisioned by copying future inputs onto them. They assign the consumer, unique host identity,
  image rebuild and repeated hardware checks to the provisioning feature. They leave the bundle
  format, validation rules and secret lifecycle open rather than inventing a protocol in this
  correction. Workstream 5 records Aidan's 2026-09-09 confirmation that both test cards were
  returned to their original flashed state and retain neither `systemd.debug_shell=1` nor the
  copied checker.
- Final simplification assessment: The completed base-checkpoint fallback is gone from
  `scripts/build-pi-image`, `images/builder/base.yaml` is deleted, and focused tests prove that a
  missing definition for either public role fails before artifact creation. The obsolete
  `/.cache/pi-image-build/` ignore is removed and no live source references that path. Retaining
  `images/e87canbus-image-check` is justified by the hardware workflow and Aidan's request for a
  one-command check. `images/README.md` now describes expected outcomes and keeps raw diagnostic
  commands without duplicating the script's low-level assertions. The focused tests fix the script
  as the one executable checkpoint contract.
- Remaining blockers: None. The terminal text audit found no remaining claim that the prototype
  hostname is unique, that the v1 artifacts omit all persistent host identity, or that the current
  artifacts become provisionable merely when the CLI supplies inputs. All edited documentation
  links resolve.
- Verdict: Accepted. The remediation passed `uv run pytest` (`883 passed`), `uv run ruff check .`,
  `uv run mypy` (`130 source files`),
  `uv run python scripts/generate_custom_protocol.py --check`, shell syntax checks for the builder,
  role hooks and checkpoint script, and `git diff --check` before the terminal wording correction.
  The terminal closure reran `git diff --check` and inspected the corrected statements and links;
  no code changed, so repeating the broad suite was not warranted. The two accepted findings are
  resolved, the simplification introduces no release-blocking defect and no required issue remains.

## Orchestrator completion record

- Final head and verification: Accepted implementation commit
  `5ec8ba8fbab0097f74ff019a3b606a27946e13b0`. Final verification passed: `uv run pytest`
  (`883 passed`), `uv run ruff check .`, `uv run mypy`
  (`130 source files`), `uv run python scripts/generate_custom_protocol.py --check`, frontend API
  and lint checks, all frontend typechecks, frontend tests (`18`, `101` and `89` passed), builder
  and checkpoint shell syntax, and `git diff --check`.
- External validation pending: None. Aidan supplied both clean artifact manifests and digests,
  passed Raspberry Pi Imager and every corrected role check on Pi 4 hardware, and returned both
  test cards to their original flashed state.
- Specification drift: Aidan approved the documented v1 prototype boundary. The first-boot
  consumer and unique host identity move to the provisioning feature, which must rebuild both
  images and repeat the relevant hardware checks before treating them as provisionable.
- Completion report delivered: 2026-09-10.
