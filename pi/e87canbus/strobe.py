"""Testable high-beam strobe timing plan."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrobeStep:
    high_beam_on: bool
    duration_s: float


def build_strobe_plan(cycles: int, on_duration_s: float, off_duration_s: float) -> list[StrobeStep]:
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    plan: list[StrobeStep] = []
    for _ in range(cycles):
        plan.append(StrobeStep(high_beam_on=True, duration_s=on_duration_s))
        plan.append(StrobeStep(high_beam_on=False, duration_s=off_duration_s))
    return plan

