#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Strict, deterministic acceptance checks for crawler repair output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .reporting import validate_original_url


REQUIRED_FIELDS = ("company", "title", "url", "duty", "requirement")


def verify_crawler_output(
    jobs: Iterable[dict[str, Any]],
    *,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    """Return a machine-readable pass/fail report for normalized jobs."""
    job_list = list(jobs)
    field_counts = {field: 0 for field in REQUIRED_FIELDS}
    checked_jobs: list[dict[str, Any]] = []

    for index, job in enumerate(job_list):
        issues: list[str] = []
        for field in REQUIRED_FIELDS:
            if str(job.get(field) or "").strip():
                field_counts[field] += 1
            else:
                issues.append(f"missing_{field}")

        url = str(job.get("url") or "")
        url_valid, _ = validate_original_url(url)
        if url and not url_valid:
            issues.append("invalid_url")

        checked_jobs.append({
            "index": index,
            "company": job.get("company"),
            "title": job.get("title"),
            "url": url,
            "issues": issues,
            "valid": not issues,
        })

    total = len(job_list)
    valid_count = sum(1 for job in checked_jobs if job["valid"])
    url_valid_count = sum(
        1
        for job in checked_jobs
        if "missing_url" not in job["issues"] and "invalid_url" not in job["issues"]
    )
    field_completeness = {
        field: round(field_counts[field] / total, 4) if total else 0.0
        for field in REQUIRED_FIELDS
    }
    if not total:
        status = "failed"
        failure_reason = "zero_jobs"
    elif valid_count != total:
        status = "failed"
        failure_reason = "incomplete_or_invalid_jobs"
    else:
        status = "passed"
        failure_reason = None

    return {
        "status": status,
        "failure_reason": failure_reason,
        "jobs_count": total,
        "valid_jobs_count": valid_count,
        "valid_jobs_rate": round(valid_count / total, 4) if total else 0.0,
        "url_valid_rate": round(url_valid_count / total, 4) if total else 0.0,
        "elapsed_ms": elapsed_ms,
        "field_completeness": field_completeness,
        "jobs": checked_jobs,
    }


def write_verification_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Persist verification output without rewriting or shortening URLs."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
