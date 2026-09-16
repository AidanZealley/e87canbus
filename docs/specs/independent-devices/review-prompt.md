# Independent devices: independent review prompt

Adversarial review of the plan by a different model, before implementation. Re-run it when the
plan changes materially, and before workflow 04, which is the largest and least reversible.

Keep the rejected-decisions list in step with the "Deliberately not specified" section of
[README.md](README.md). That list is what stops a thorough reviewer proposing mechanisms already
considered and removed.

```bash
codex exec -s read-only "$(cat <<'EOF'
Review a planned architectural change in this repository before implementation begins.
Read-only. Do not edit files.

The plan is in docs/specs/independent-devices/: a README describing the effort and six
workflows, plus three specifications. It is recorded as
docs/decisions/0017-independent-devices-over-wifi.md. Read all five, plus the ADRs 0017
supersedes, and enough of the codebase to check the claims they make.

Summary: project devices stop speaking a custom CAN protocol to the coordinator and become
independent HTTPS clients on the existing provisioned Wi-Fi network. CAN becomes only the
car. Socket.IO is replaced with server-sent events. e87ctl gains ESP32 firmware build and
provisioning.

This plan was produced in a single conversation with a single model and has had no
independent read. Your job is to find where it is wrong, incomplete, or carrying weight it
does not need. Verify claims against the code rather than accepting the documents'
description of it.

Prioritise these:

1. The removal inventory in device-platform.md drives most of workflow 04 and was built by
   grepping. Search the repository yourself and report anything it misses: consumers of the
   generated protocol, the device registry, the ISO-TP transport, or the live contract
   fields it deletes. A missed consumer is the most likely way that workflow stalls.

2. The README claims that if workflows 01 to 05 are complete, workflow 06 adds no
   coordinator and no frontend code. Check that against what specifications 03 and 04
   actually deliver. If something workflow 06 needs is specified nowhere, say so.

3. Identify machinery that could be deleted rather than built. Prefer the smallest complete
   solution. If the plan introduces an abstraction, configuration point or mechanism that a
   direct alternative would cover, name the direct alternative.

4. Find dependencies between the six workflows that the README's ordering does not state,
   and anything in a workflow's scope that belongs in a different one.

5. Report correctness problems in the designs themselves: SSE resume and generation
   semantics, the device configuration envelope, certificate-based addressing, and the
   authorisation changes.

This is a single-operator, track-only car built and maintained by one person. These were
considered during design and deliberately rejected or deferred. Do not report them as gaps,
and do not propose implementing them:

  - Configuration persists across power cycles with no expiry and no field-level
    exceptions, including an elevated steering assistance override. A lease or expiry
    mechanism was designed and removed.
  - No requirement that vehicle-affecting stored state has a durable indication. This was
    specified and then removed because it coupled one device's behaviour to another
    device's configuration.
  - Nothing on the network prevents devices reaching each other. Access-point client
    isolation was considered and rejected. The rule is a design rule.
  - No flash encryption, no secure boot, and unencrypted identity partitions.
  - No device inventory in e87ctl, no credential rotation, no per-device revocation.
  - No network firmware update, though partition space is reserved for it.
  - No UI for assigning configuration to a specific device; deferred until a role has more
    than one device.
  - No device-to-device communication on any transport, and no CAN fallback for degraded
    operation.
  - The simulator loses all frame visibility when the trace view is deleted.
  - The Servotronic device knows nothing about discrete manual levels. It receives a
    resolved 0 to 1 fraction, and maximum assistance is that fraction at 1.0 rather than
    a separate device mode.
  - Configuration writes are not gated on device presence. Saving while a device is
    disconnected is accepted and the UI says the change is not reaching the device.
  - No status heartbeat and no staleness rule. An open stream is presence; status is
    posted on change only.
  - Button presses are never retried and carry no sequence or idempotency key, and no
    device sends a timestamp.
  - No installation-composition source. A role appears in the UI because it is in
    DeviceRole.
  - The identity partition is NVS rather than a custom binary layout, and firmware does
    not verify the certificate chain, the key pair or the validity window.
  - Simulated devices authenticate by injecting the same headers nginx injects, against
    the unchanged production authentication path.
  - The live contract is generated from OpenAPI by the existing hey-api pipeline. The
    bespoke JSON Schema generators and json-schema-to-typescript are deleted rather
    than ported.
  - The live channel is one stream per topic, not one multiplexed stream. There are no
    event names on the wire. HTTP/2 is enabled in nginx to carry the connection count.
  - No button availability. A button whose command the car cannot currently obey renders
    like any other assigned button. The replacement design is described and deferred.
  - The button pad document carries an animation type and its parameters, not a compiled
    animation. An unknown type is ignored by the pad.

If you believe one of those decisions is wrong, report it as a Question that engages with
the reasoning the specification gives, and say what that reasoning fails to account for.
Do not report it as Required and do not propose the rejected mechanism as though it were an
oversight. The stated reasoning is in the specifications; argue with it or leave it alone.

Do not propose reorganising the documents or adding process.

Report findings as:

  Required  - a defect, incorrect claim, or missing piece that blocks implementation
  Optional  - a real improvement that does not block
  Question  - an ambiguity needing a decision, or a challenge to a rejected decision above

Cite file and line for every finding. State what you verified and how. If you checked
something and it held up, say so briefly; knowing what survived review is as useful as
knowing what did not.
EOF
)"
```
