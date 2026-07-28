"""Probe module for the autonomous dev-team Worker's operational test — NOT product code.

It exists only to exercise the fix-it cycle end to end on a real PR: it introduces one deliberate,
LINE-level mypy error (unlike the structural duplicate-module failure the Developer correctly
declines). Delete this branch / PR after the run.
"""

from __future__ import annotations


def probe_answer() -> int:
    value: str = 42  # deliberate: int assigned to a str-annotated variable -> mypy [assignment]
    return len(value)
