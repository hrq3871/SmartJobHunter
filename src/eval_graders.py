#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reusable grader helpers for SmartJobHunter evals."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def code_grader(
    name: str,
    passed: bool,
    expected: Any = None,
    actual: Any = None,
    message: str = "",
) -> Dict[str, Any]:
    """Build a deterministic code-based grader result."""
    return {
        "name": name,
        "type": "code",
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
        "message": message,
        "skipped": False,
    }


def skipped_grader(
    name: str,
    grader_type: str,
    message: str,
    expected: Any = None,
    actual: Any = None,
) -> Dict[str, Any]:
    """Build a skipped grader result for model/human graders that are not active."""
    return {
        "name": name,
        "type": grader_type,
        "passed": True,
        "expected": expected,
        "actual": actual,
        "message": message,
        "skipped": True,
    }


def passed_all(graders: Iterable[Dict[str, Any]]) -> bool:
    """Return True when all non-skipped graders pass."""
    active = [grader for grader in graders if not grader.get("skipped")]
    return all(bool(grader.get("passed")) for grader in active)


def declared_graders(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert optional declarative model/human graders into skipped records.

    The first implementation documents the contract without adding an external
    LLM dependency. Enabled model/human graders are still marked as skipped so
    regression runs stay deterministic until a real judge is wired in.
    """
    results: List[Dict[str, Any]] = []
    for grader in case.get("graders", []) or []:
        grader_type = str(grader.get("type", "code"))
        if grader_type == "code":
            continue
        name = grader.get("name") or f"{grader_type}_grader"
        enabled = bool(grader.get("enabled", False))
        reason = "not implemented in offline runner" if enabled else "disabled"
        results.append(skipped_grader(name, grader_type, reason))
    return results


def grader_summary(graders: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Count active/skipped/passed/failed grader results."""
    summary = {"total": 0, "active": 0, "skipped": 0, "passed": 0, "failed": 0}
    for grader in graders:
        summary["total"] += 1
        if grader.get("skipped"):
            summary["skipped"] += 1
            continue
        summary["active"] += 1
        if grader.get("passed"):
            summary["passed"] += 1
        else:
            summary["failed"] += 1
    return summary
