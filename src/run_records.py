"""Immutable per-run job audit records."""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict, deque
from typing import Any, Iterable


def create_run_records(raw_jobs: list[dict], run_id: str) -> list[dict]:
    """Snapshot every crawled job without collapsing duplicate instances."""
    records: list[dict] = []
    for index, job in enumerate(raw_jobs, 1):
        snapshot = deepcopy(job)
        records.append(
            {
                "run_id": run_id,
                "run_record_id": f"{run_id}:{index}",
                "original_job_id": str(
                    job.get("id") or job.get("job_id") or job.get("position_id") or ""
                ),
                "job_hash": str(job.get("hash") or ""),
                "original_url": str(job.get("url") or ""),
                "raw_job": snapshot,
                "processing": {"stage": "crawled", "reason": None},
                "evaluation": None,
            }
        )
    return records


def update_record_stage(
    records: list[dict],
    record_ids: Iterable[str],
    stage: str,
    reason: str | None = None,
) -> None:
    """Update matching records in place without removing audit history."""
    selected = set(record_ids)
    for record in records:
        if record.get("run_record_id") in selected:
            record["processing"] = {"stage": stage, "reason": reason}


def select_record_ids_for_jobs(records: list[dict], jobs: Iterable[dict]) -> set[str]:
    """Match normalized jobs back to distinct raw records by occurrence."""
    available: dict[tuple[str, ...], deque[str]] = defaultdict(deque)
    for record in records:
        raw_job = record.get("raw_job") or {}
        available[_job_identity(raw_job)].append(str(record.get("run_record_id")))

    selected: set[str] = set()
    for job in jobs:
        candidates = available.get(_job_identity(job))
        if candidates:
            selected.add(candidates.popleft())
    return selected


def _job_identity(job: dict) -> tuple[str, ...]:
    job_hash = str(job.get("hash") or "").strip()
    if job_hash:
        return ("hash", job_hash)
    return (
        "fields",
        str(job.get("url") or ""),
        str(job.get("company") or ""),
        str(job.get("title") or ""),
    )


def attach_evaluation(record: dict, evaluation: dict, source: str) -> None:
    """Attach an Agent or deterministic fallback result using one report schema."""
    semantic = evaluation.get("semantic_filter") or evaluation.get("semantic_decision") or {}
    analysis = evaluation.get("match_analysis") or {}
    matched_evidence = evaluation.get("matched_evidence")
    if matched_evidence is None:
        matched_evidence = list(analysis.get("strong_matches") or []) + list(
            analysis.get("potential_matches") or []
        )
    gaps = evaluation.get("gaps")
    if gaps is None:
        gaps = analysis.get("gaps") or []
    risks = evaluation.get("risks")
    if risks is None:
        risks = semantic.get("concerns") or []
        if evaluation.get("risk_warning") and evaluation["risk_warning"] not in risks:
            risks = list(risks) + [evaluation["risk_warning"]]

    record["evaluation"] = {
        "source": source,
        "semantic_decision": deepcopy(semantic),
        "matched_evidence": deepcopy(matched_evidence or []),
        "gaps": deepcopy(gaps or []),
        "risks": deepcopy(risks or []),
        "scoring_breakdown": deepcopy(
            evaluation.get("scoring_breakdown") or evaluation.get("breakdown") or {}
        ),
        "score": evaluation.get("score"),
        "final_decision": evaluation.get("recommendation")
        or evaluation.get("decision"),
        "raw": deepcopy(evaluation),
    }
