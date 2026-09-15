"""Guided coordinator and console pair verification.

The operator runs this while the Mac is attached only to the coordinator's isolated network,
so every local input is collected and validated before the network switch is requested. The flow
only sequences calls into `verify_device`; it performs no device checks of its own.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from e87ctl.artifacts import Role
from e87ctl.recovery import load_recovery_package
from e87ctl.verify import (
    INSTALLATION_PATTERN,
    SSH_FINGERPRINT_PATTERN,
    VerificationResult,
    VerifyCommandError,
    render_human,
    verify_device,
)

PASS_COUNT = 2
ROLE_ORDER: tuple[Role, ...] = ("coordinator", "console")
NETWORK_CONFIRMATION = "ready"

Prompt = Callable[[str], str]
Clock = Callable[[], float]
Verifier = Callable[..., VerificationResult]


class GuidedInputs(BaseModel):
    """Everything the guided flow needs before it touches the installation network."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    installation_path: Path
    installation_id: Annotated[str, StringConstraints(pattern=INSTALLATION_PATTERN)]
    fingerprints: dict[Role, Annotated[str, StringConstraints(pattern=SSH_FINGERPRINT_PATTERN)]]
    report_path: Path


class PairVerificationPass(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    pass_number: int = Field(ge=1, le=PASS_COUNT)
    role: Role
    elapsed_seconds: float = Field(ge=0)
    verification: VerificationResult


class PairVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1] = 1
    result: Literal["passed", "failed"]
    installation_id: Annotated[str, StringConstraints(pattern=INSTALLATION_PATTERN)]
    passes: tuple[PairVerificationPass, ...]
    incomplete_reason: str | None

    @model_validator(mode="after")
    def validate_result(self) -> PairVerificationReport:
        complete = (
            self.incomplete_reason is None
            and len(self.passes) == PASS_COUNT * len(ROLE_ORDER)
            and all(entry.verification.result == "passed" for entry in self.passes)
        )
        if self.result != ("passed" if complete else "failed"):
            raise ValueError("pair verification result does not match its passes")
        return self


def collect_inputs(prompt: Prompt) -> GuidedInputs:
    """Read and validate every local input. Raises before any device is contacted."""

    installation_path = Path(_ask(prompt, "Installation recovery package path: "))
    try:
        installation_id = load_recovery_package(installation_path).installation_id
    except Exception:
        raise VerifyCommandError("could not read the installation recovery package") from None

    fingerprints = {role: _ask_fingerprint(prompt, role) for role in ROLE_ORDER}
    report_path = _ask_report_path(prompt)
    return GuidedInputs(
        installation_path=installation_path,
        installation_id=installation_id,
        fingerprints=fingerprints,
        report_path=report_path,
    )


def confirm_network(prompt: Prompt) -> None:
    print("Connect this Mac to the installation Wi-Fi network now. It has no internet gateway.")
    if _ask(prompt, f"Type '{NETWORK_CONFIRMATION}' once connected: ") != NETWORK_CONFIRMATION:
        raise VerifyCommandError("the network switch was not confirmed")


def run_passes(
    inputs: GuidedInputs,
    *,
    clock: Clock = time.monotonic,
    verify: Verifier = verify_device,
) -> PairVerificationReport:
    """Verify both roles twice, keeping whatever evidence completes before an abort."""

    passes: list[PairVerificationPass] = []
    incomplete_reason: str | None = None
    for pass_number in range(1, PASS_COUNT + 1):
        for role in ROLE_ORDER:
            started = clock()
            try:
                verification = verify(
                    role,
                    inputs.installation_path,
                    expected_host_key_fingerprint=inputs.fingerprints[role],
                )
            except VerifyCommandError as error:
                incomplete_reason = str(error)
                break
            passes.append(
                PairVerificationPass(
                    pass_number=pass_number,
                    role=role,
                    elapsed_seconds=round(clock() - started, 3),
                    verification=verification,
                )
            )
            print(render_human(verification))
        if incomplete_reason is not None:
            break

    complete = incomplete_reason is None and all(
        entry.verification.result == "passed" for entry in passes
    )
    return PairVerificationReport(
        result="passed" if complete and len(passes) == PASS_COUNT * len(ROLE_ORDER) else "failed",
        installation_id=inputs.installation_id,
        passes=tuple(passes),
        incomplete_reason=incomplete_reason,
    )


def write_report(path: Path, report: PairVerificationReport) -> None:
    try:
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    except OSError:
        raise VerifyCommandError("could not write the verification report") from None


def render_report_human(report: PairVerificationReport) -> str:
    lines = [f"Pair verification v{report.format_version} {report.result}"]
    for entry in report.passes:
        lines.append(
            f"{entry.verification.result.upper():7} pass {entry.pass_number} {entry.role} "
            f"in {entry.elapsed_seconds:.3f}s"
        )
    if report.incomplete_reason is not None:
        lines.append(f"Stopped early: {report.incomplete_reason}")
    return "\n".join(lines)


def _ask(prompt: Prompt, question: str) -> str:
    try:
        return prompt(question).strip()
    except EOFError:
        raise VerifyCommandError("required input was not provided") from None


def _ask_fingerprint(prompt: Prompt, role: Role) -> str:
    fingerprint = _ask(prompt, f"{role.capitalize()} SSH host-key fingerprint (SHA256:...): ")
    if re.fullmatch(SSH_FINGERPRINT_PATTERN, fingerprint) is None:
        raise VerifyCommandError(f"the {role} SSH host-key fingerprint is invalid")
    return fingerprint


def _ask_report_path(prompt: Prompt) -> Path:
    report_path = Path(_ask(prompt, "Report output path: "))
    if report_path.exists():
        raise VerifyCommandError("the report path already exists")
    if not report_path.parent.is_dir():
        raise VerifyCommandError("the report directory does not exist")
    return report_path
