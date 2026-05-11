#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline evaluation runner for the SmartJobHunter agent workflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List

import yaml

from .cli import JobHunter
from . import filters
from .eval_graders import code_grader, declared_graders, grader_summary, passed_all
from .eval_transcript import TranscriptRecorder
from .matching import evaluate_job_fit, match_job_intent, summarize_resume_ability
from .site_inspector import inspect_html_signals
from .strategy_planner import plan_strategy_action


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "evals" / "regression" / "jobhunter_core.yaml"
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "evals"


CASE_TYPE_TO_METRIC = {
    "matching_intent": "matching_filtering",
    "job_fit": "recommendation_quality",
    "strategy_action": "crawler_strategy",
    "url_filter": "output_quality",
    "application_package": "output_quality",
    "workflow_outcome": "output_quality",
    "instruction_alignment": "instruction_alignment",
}


def load_dataset(path: str | Path = DEFAULT_DATASET) -> Dict[str, Any]:
    """Load an evaluation dataset from YAML."""
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as handle:
        dataset = yaml.safe_load(handle) or {}
    dataset["_dataset_path"] = str(dataset_path)
    return dataset


def run_dataset(
    dataset: Dict[str, Any],
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    write_artifacts: bool = True,
    trials: int = 1,
) -> Dict[str, Any]:
    """Run all cases and return aggregate metrics plus per-case details."""
    output_root = Path(output_root)
    run_started = datetime.now()
    run_dir = output_root / run_started.strftime("%Y-%m-%d") / run_started.strftime("%Y%m%d_%H%M%S_%f")
    if write_artifacts:
        run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for case in dataset.get("cases", []):
        results.append(run_case(case, run_dir if write_artifacts else None, trials=max(1, int(trials))))

    metrics = compute_metrics(results)
    report = {
        "name": dataset.get("name", "SmartJobHunter Agent Evaluation"),
        "dataset": dataset.get("_dataset_path"),
        "version": dataset.get("version"),
        "run_started_at": run_started.isoformat(timespec="seconds"),
        "case_count": len(results),
        "trial_count": max(1, int(trials)),
        "metrics": metrics,
        "results": results,
    }

    if write_artifacts:
        json_path = run_dir / "agent_eval_results.json"
        md_path = run_dir / "agent_eval_report.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(render_markdown_report(report), encoding="utf-8")
        report["artifact_dir"] = str(run_dir)
        report["json_report"] = str(json_path)
        report["markdown_report"] = str(md_path)

    return report


def run_case(case: Dict[str, Any], run_dir: Path | None = None, trials: int = 1) -> Dict[str, Any]:
    """Run one case for one or more trials."""
    trial_results = [
        _run_case_once(case, run_dir=run_dir, trial_index=index, trial_count=trials)
        for index in range(1, trials + 1)
    ]
    if trials == 1:
        result = trial_results[0]
        result["trial_count"] = 1
        result["pass_at_k"] = 1.0 if result["passed"] else 0.0
        result["pass_all_k"] = 1.0 if result["passed"] else 0.0
        result["trials"] = [_trial_summary(result, 1)]
        return result

    first = dict(trial_results[0])
    pass_at_k = any(result["passed"] for result in trial_results)
    pass_all_k = all(result["passed"] for result in trial_results)
    first["passed"] = pass_all_k
    first["trial_count"] = trials
    first["pass_at_k"] = 1.0 if pass_at_k else 0.0
    first["pass_all_k"] = 1.0 if pass_all_k else 0.0
    first["trials"] = [_trial_summary(result, index) for index, result in enumerate(trial_results, 1)]
    first["transcript_paths"] = [result.get("transcript_path") for result in trial_results if result.get("transcript_path")]
    return first


def _run_case_once(
    case: Dict[str, Any],
    run_dir: Path | None = None,
    trial_index: int = 1,
    trial_count: int = 1,
) -> Dict[str, Any]:
    """Dispatch one case by type."""
    case_type = case.get("type")
    handlers = {
        "matching_intent": _run_matching_intent_case,
        "job_fit": _run_job_fit_case,
        "strategy_action": _run_strategy_action_case,
        "url_filter": _run_url_filter_case,
        "application_package": _run_application_package_case,
        "workflow_outcome": _run_workflow_outcome_case,
        "instruction_alignment": _run_instruction_alignment_case,
    }
    transcript_path = _transcript_path(run_dir, case, trial_index, trial_count)
    recorder = TranscriptRecorder(transcript_path)
    recorder.record("case_started", case_id=case.get("id"), type=case_type, trial_index=trial_index)
    handler = handlers.get(case_type)
    if handler is None:
        result = _case_result(
            case,
            False,
            {"error": f"unsupported case type: {case_type}"},
            transcript_path=recorder.path_text,
        )
        recorder.record("case_finished", passed=False)
        return result

    try:
        result = handler(case, recorder, run_dir)
        result["transcript_path"] = recorder.path_text
        recorder.record("case_finished", passed=result["passed"])
        return result
    except Exception as exc:  # pragma: no cover - defensive reporting
        recorder.record("exception", exception_type=type(exc).__name__, error=str(exc))
        result = _case_result(
            case,
            False,
            {"error": str(exc), "exception_type": type(exc).__name__},
            transcript_path=recorder.path_text,
        )
        recorder.record("case_finished", passed=False)
        return result


def _trial_summary(result: Dict[str, Any], trial_index: int) -> Dict[str, Any]:
    return {
        "trial_index": trial_index,
        "passed": result["passed"],
        "transcript_path": result.get("transcript_path"),
        "failed_graders": [
            grader.get("name")
            for grader in result.get("graders", [])
            if not grader.get("skipped") and not grader.get("passed")
        ],
    }


def _transcript_path(
    run_dir: Path | None,
    case: Dict[str, Any],
    trial_index: int,
    trial_count: int,
) -> Path | None:
    if run_dir is None:
        return None
    case_id = str(case.get("id") or "case")
    suffix = f"_trial_{trial_index:02d}" if trial_count > 1 else ""
    return run_dir / "transcripts" / f"{case_id}{suffix}.jsonl"


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute product-level metrics from case results."""
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    by_type = defaultdict(lambda: {"passed": 0, "total": 0, "rate": 0.0})
    by_metric = defaultdict(lambda: {"passed": 0, "total": 0, "rate": 0.0})
    attribution = Counter()
    all_graders: List[Dict[str, Any]] = []

    for result in results:
        case_type = result.get("type", "unknown")
        metric_name = result.get("metric_group") or CASE_TYPE_TO_METRIC.get(case_type, case_type)
        by_type[case_type]["total"] += 1
        by_metric[metric_name]["total"] += 1
        all_graders.extend(result.get("graders", []))
        if result["passed"]:
            by_type[case_type]["passed"] += 1
            by_metric[metric_name]["passed"] += 1
        else:
            attribution[result.get("attribution") or metric_name] += 1

    for group in list(by_type.values()) + list(by_metric.values()):
        group["rate"] = _safe_rate(group["passed"], group["total"])

    matching_confusion = _matching_confusion(results)
    strategy_action_accuracy = _case_rate(results, "strategy_action")
    tool_call_accuracy = strategy_action_accuracy
    trial_count = max([int(result.get("trial_count", 1)) for result in results] or [1])

    return {
        "task_completion_rate": _safe_rate(passed, total),
        "passed_cases": passed,
        "total_cases": total,
        "trial_count": trial_count,
        "pass_at_k": _safe_rate(sum(1 for result in results if result.get("pass_at_k", 0.0) > 0), total),
        "pass_all_k": _safe_rate(sum(1 for result in results if result.get("pass_all_k", 0.0) >= 1.0), total),
        "by_type": dict(sorted(by_type.items())),
        "by_metric": dict(sorted(by_metric.items())),
        "graders": grader_summary(all_graders),
        "tool_call_accuracy": tool_call_accuracy,
        "strategy_action_accuracy": strategy_action_accuracy,
        "matching": matching_confusion,
        "bad_case_attribution": dict(sorted(attribution.items())),
    }


def render_markdown_report(report: Dict[str, Any]) -> str:
    """Render a concise Markdown report."""
    metrics = report["metrics"]
    lines = [
        "# SmartJobHunter Agent Evaluation Report",
        "",
        f"- Dataset: {report.get('dataset')}",
        f"- Run started: {report.get('run_started_at')}",
        f"- Cases: {metrics['passed_cases']}/{metrics['total_cases']} passed",
        f"- Trials per case: {metrics.get('trial_count', 1)}",
        f"- Task completion rate: {_pct(metrics['task_completion_rate'])}",
        f"- pass@k: {_pct(metrics.get('pass_at_k', metrics['task_completion_rate']))}",
        f"- pass^k: {_pct(metrics.get('pass_all_k', metrics['task_completion_rate']))}",
        f"- Tool/action accuracy: {_pct(metrics['tool_call_accuracy'])}",
        f"- Matching precision: {_pct(metrics['matching']['precision'])}",
        f"- Matching recall: {_pct(metrics['matching']['recall'])}",
        f"- Matching F1: {_pct(metrics['matching']['f1'])}",
        f"- Graders: {metrics.get('graders', {}).get('passed', 0)} passed, "
        f"{metrics.get('graders', {}).get('failed', 0)} failed, "
        f"{metrics.get('graders', {}).get('skipped', 0)} skipped",
        "",
        "## Metric Groups",
        "",
        "| Group | Passed | Total | Rate |",
        "|:--|--:|--:|--:|",
    ]
    for name, group in metrics["by_metric"].items():
        lines.append(f"| {name} | {group['passed']} | {group['total']} | {_pct(group['rate'])} |")

    lines.extend(["", "## Bad Case Attribution", ""])
    if metrics["bad_case_attribution"]:
        for name, count in metrics["bad_case_attribution"].items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- No failed cases in this run.")

    lines.extend(["", "## Case Results", ""])
    for result in report["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        lines.append(f"- {status} `{result['id']}` ({result['type']})")
        if result.get("transcript_path"):
            lines.append(f"  - Transcript: `{result['transcript_path']}`")
        if not result["passed"]:
            failed_graders = [
                grader
                for grader in result.get("graders", [])
                if not grader.get("skipped") and not grader.get("passed")
            ]
            if failed_graders:
                for grader in failed_graders:
                    lines.append(
                        f"  - Grader `{grader.get('name')}` failed: "
                        f"expected={json.dumps(grader.get('expected'), ensure_ascii=False)}, "
                        f"actual={json.dumps(grader.get('actual'), ensure_ascii=False)}"
                    )
            else:
                lines.append(f"  - Details: {json.dumps(result.get('details', {}), ensure_ascii=False)}")

    return "\n".join(lines) + "\n"


def _run_matching_intent_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    recorder.record(
        "function_called",
        name="match_job_intent",
        input_summary={"title": case.get("job", {}).get("title"), "profile": case.get("profile", {}).get("name")},
    )
    actual = match_job_intent(
        case.get("job", {}),
        case.get("profile", {}),
        decision_level=case.get("decision_level", "moderate"),
    )
    recorder.record(
        "function_result",
        name="match_job_intent",
        output_summary={"should_keep": actual.get("should_keep"), "match_score": actual.get("match_score")},
    )

    graders = [
        code_grader(
            "should_keep",
            actual.get("should_keep") == expected.get("should_keep"),
            expected=expected.get("should_keep"),
            actual=actual.get("should_keep"),
        )
    ]
    if "min_match_score" in expected:
        graders.append(code_grader(
            "min_match_score",
            actual.get("match_score", 0) >= float(expected["min_match_score"]),
            expected=expected["min_match_score"],
            actual=actual.get("match_score", 0),
        ))
    if "max_match_score" in expected:
        graders.append(code_grader(
            "max_match_score",
            actual.get("match_score", 0) <= float(expected["max_match_score"]),
            expected=expected["max_match_score"],
            actual=actual.get("match_score", 0),
        ))
    graders.extend(declared_graders(case))
    _record_graders(recorder, graders)

    return _case_result(case, passed_all(graders), {
        "actual": actual,
        "expected_should_keep": expected.get("should_keep"),
    }, graders=graders)


def _run_job_fit_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    resume_text = case.get("resume", "")
    recorder.record(
        "function_called",
        name="evaluate_job_fit",
        input_summary={"title": case.get("job", {}).get("title"), "resume_chars": len(resume_text)},
    )
    actual = evaluate_job_fit(
        case.get("job", {}),
        case.get("profile", {}),
        resume_text=resume_text,
        ability_profile=summarize_resume_ability(resume_text),
    )
    recorder.record(
        "function_result",
        name="evaluate_job_fit",
        output_summary={"score": actual.get("score"), "recommendation": actual.get("recommendation")},
    )

    graders: List[Dict[str, Any]] = []
    if "min_score" in expected:
        graders.append(code_grader(
            "min_score",
            actual.get("score", 0) >= int(expected["min_score"]),
            expected=expected["min_score"],
            actual=actual.get("score", 0),
        ))
    if "max_score" in expected:
        graders.append(code_grader(
            "max_score",
            actual.get("score", 0) <= int(expected["max_score"]),
            expected=expected["max_score"],
            actual=actual.get("score", 0),
        ))
    if "recommendation_in" in expected:
        graders.append(code_grader(
            "recommendation_in",
            actual.get("recommendation") in expected["recommendation_in"],
            expected=expected["recommendation_in"],
            actual=actual.get("recommendation"),
        ))
    if "recommendation_not_in" in expected:
        graders.append(code_grader(
            "recommendation_not_in",
            actual.get("recommendation") not in expected["recommendation_not_in"],
            expected=expected["recommendation_not_in"],
            actual=actual.get("recommendation"),
        ))
    graders.extend(declared_graders(case))
    _record_graders(recorder, graders)

    return _case_result(case, passed_all(graders), {"actual": actual}, graders=graders)


def _run_strategy_action_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    inspection = dict(case.get("inspection") or {})
    if case.get("html") is not None or case.get("text") is not None:
        recorder.record("function_called", name="inspect_html_signals")
        signal_result = inspect_html_signals(case.get("html", ""), case.get("text", ""))
        inspection["signals"] = sorted(set(inspection.get("signals") or []) | set(signal_result["signals"]))
        recorder.record("function_result", name="inspect_html_signals", output_summary=signal_result)

    recorder.record(
        "function_called",
        name="plan_strategy_action",
        input_summary={"company": case.get("company", {}).get("id"), "signals": inspection.get("signals", [])},
    )
    actual = plan_strategy_action(case.get("company", {}), inspection)
    recorder.record("function_result", name="plan_strategy_action", output_summary=actual)
    graders = [
        code_grader(
            "action",
            actual.get("action") == expected.get("action"),
            expected=expected.get("action"),
            actual=actual.get("action"),
        )
    ]
    if "requires_agent" in expected:
        graders.append(code_grader(
            "requires_agent",
            actual.get("requires_agent") == expected["requires_agent"],
            expected=expected["requires_agent"],
            actual=actual.get("requires_agent"),
        ))
    if "block_type" in expected:
        graders.append(code_grader(
            "block_type",
            actual.get("block_type") == expected["block_type"],
            expected=expected["block_type"],
            actual=actual.get("block_type"),
        ))
    if "reason_contains" in expected:
        graders.append(code_grader(
            "reason_contains",
            expected["reason_contains"] in str(actual.get("reason", "")),
            expected=expected["reason_contains"],
            actual=actual.get("reason", ""),
        ))
    if "signal_absent" in expected:
        graders.append(code_grader(
            "signal_absent",
            expected["signal_absent"] not in set(inspection.get("signals") or []),
            expected=f"absent:{expected['signal_absent']}",
            actual=inspection.get("signals") or [],
        ))
    graders.extend(declared_graders(case))
    _record_graders(recorder, graders)

    return _case_result(case, passed_all(graders), {
        "actual": actual,
        "inspection": inspection,
    }, graders=graders)


def _run_url_filter_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    jobs = case.get("jobs", [])
    evaluations = case.get("evaluations", [])
    availability = {job.get("url", ""): bool(job.get("mock_available")) for job in jobs}
    hunter = JobHunter()
    hunter._url_is_available = lambda url: availability.get(url, False)  # type: ignore[method-assign]
    recorder.record(
        "function_called",
        name="JobHunter._filter_live_urls",
        input_summary={"job_count": len(jobs), "available_urls": [url for url, ok in availability.items() if ok]},
    )
    valid_jobs, valid_evaluations = hunter._filter_live_urls(jobs, evaluations)

    actual_titles = [job.get("title") for job in valid_jobs]
    recorder.record(
        "function_result",
        name="JobHunter._filter_live_urls",
        output_summary={"kept_titles": actual_titles, "evaluation_count": len(valid_evaluations)},
    )
    graders = [
        code_grader(
            "kept_titles",
            actual_titles == expected.get("kept_titles", []),
            expected=expected.get("kept_titles", []),
            actual=actual_titles,
        ),
        code_grader(
            "evaluation_alignment",
            len(valid_jobs) == len(valid_evaluations),
            expected=len(valid_jobs),
            actual=len(valid_evaluations),
        ),
    ]
    graders.extend(declared_graders(case))
    _record_graders(recorder, graders)
    return _case_result(case, passed_all(graders), {
        "actual_titles": actual_titles,
    }, graders=graders)


def _run_application_package_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    with TemporaryDirectory() as tmp_dir:
        hunter = JobHunter()
        hunter.output_dir = Path(tmp_dir if run_dir is None else run_dir / "artifacts")
        recorder.record(
            "function_called",
            name="JobHunter.generate_application_package",
            input_summary={"job_count": len(case.get("jobs", [])), "output_dir": str(hunter.output_dir)},
        )
        package_path = Path(hunter.generate_application_package(
            case.get("jobs", []),
            case.get("profile", {}),
            case.get("evaluations", []),
        ))
        cover_letters = sorted(package_path.glob("cover_letter_*.md"))
        combined_text = "\n".join(path.read_text(encoding="utf-8") for path in cover_letters)
        recorder.record(
            "function_result",
            name="JobHunter.generate_application_package",
            output_summary={"package_path": str(package_path), "cover_letter_count": len(cover_letters)},
        )
        graders = [
            code_grader(
                "cover_letter_count",
                len(cover_letters) == int(expected.get("cover_letter_count", 0)),
                expected=int(expected.get("cover_letter_count", 0)),
                actual=len(cover_letters),
            ),
            code_grader(
                "index_exists",
                (package_path / "index.md").exists(),
                expected=True,
                actual=(package_path / "index.md").exists(),
            ),
            code_grader(
                "required_text",
                all(text in combined_text for text in expected.get("required_text", [])),
                expected=expected.get("required_text", []),
                actual=[text for text in expected.get("required_text", []) if text in combined_text],
            ),
        ]
        graders.extend(declared_graders(case))
        _record_graders(recorder, graders)
        details = {
            "package_path": str(package_path),
            "cover_letter_count": len(cover_letters),
        }
        return _case_result(case, passed_all(graders), details, graders=graders)


def _run_workflow_outcome_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    with TemporaryDirectory() as tmp_dir:
        short_case_id = _safe_artifact_name(str(case.get("id") or "workflow"))[:24]
        base_dir = Path(tmp_dir if run_dir is None else run_dir / "wf" / short_case_id)
        hunter = JobHunter()
        hunter.output_dir = base_dir / "output"
        hunter.memory_dir = base_dir / "memory"
        hunter.memory_dir.mkdir(parents=True, exist_ok=True)
        jobs = [dict(job) for job in case.get("jobs", [])]
        evaluations = [dict(evaluation) for evaluation in case.get("evaluations", [])]
        availability = {job.get("url", ""): bool(job.get("mock_available")) for job in jobs}
        hunter._url_is_available = lambda url: availability.get(url, False)  # type: ignore[method-assign]

        recorder.record("workflow_step", name="filter_live_urls", input_summary={"job_count": len(jobs)})
        valid_jobs, valid_evaluations = hunter._filter_live_urls(jobs, evaluations)
        valid_titles = [job.get("title") for job in valid_jobs]
        recorder.record("workflow_step", name="generate_report", input_summary={"job_count": len(valid_jobs)})
        report_path = Path(hunter.generate_report(valid_jobs, case.get("profile", {}), valid_evaluations))
        recorder.record("workflow_step", name="generate_application_package")
        package_path = Path(hunter.generate_application_package(valid_jobs, case.get("profile", {}), valid_evaluations))
        memory_path = hunter.memory_dir / "seen_jobs.md"
        recorder.record("workflow_step", name="update_memory", input_summary={"job_count": len(valid_jobs)})
        filters.update_memory(valid_jobs, valid_evaluations, str(memory_path))

        report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
        memory_text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        cover_letters = sorted(package_path.glob("cover_letter_*.md")) if package_path.exists() else []
        excluded_present = [title for title in expected.get("excluded_titles", []) if title in report_text]
        memory_found = [text for text in expected.get("memory_contains", []) if text in memory_text]
        daily_parent = report_path.parent.name

        graders = [
            code_grader("report_exists", report_path.exists() == bool(expected.get("report_exists", True)), expected=True, actual=report_path.exists()),
            code_grader("package_top_n", len(cover_letters) == int(expected.get("package_top_n", 0)), expected=expected.get("package_top_n", 0), actual=len(cover_letters)),
            code_grader("excluded_titles_absent", not excluded_present, expected=[], actual=excluded_present),
            code_grader("memory_contains", len(memory_found) == len(expected.get("memory_contains", [])), expected=expected.get("memory_contains", []), actual=memory_found),
            code_grader("evaluation_alignment", len(valid_jobs) == len(valid_evaluations), expected=len(valid_jobs), actual=len(valid_evaluations)),
            code_grader("date_archive_path", len(daily_parent) == 10 and daily_parent.count("-") == 2, expected="YYYY-MM-DD", actual=daily_parent),
        ]
        graders.extend(declared_graders(case))
        _record_graders(recorder, graders)
        details = {
            "report_path": str(report_path),
            "package_path": str(package_path),
            "memory_path": str(memory_path),
            "valid_titles": valid_titles,
        }
        recorder.record("workflow_result", **details)
        return _case_result(case, passed_all(graders), details, graders=graders)


def _run_instruction_alignment_case(
    case: Dict[str, Any],
    recorder: TranscriptRecorder,
    run_dir: Path | None = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    file_texts = {}
    for relative_path in case.get("files", []):
        path = ROOT / relative_path
        file_texts[relative_path] = path.read_text(encoding="utf-8") if path.exists() else ""

    required_text = expected.get("required_text", [])
    forbidden_text = expected.get("forbidden_text", [])
    missing_required = {
        relative_path: [text for text in required_text if text not in content]
        for relative_path, content in file_texts.items()
    }
    forbidden_present = {
        relative_path: [text for text in forbidden_text if text in content]
        for relative_path, content in file_texts.items()
    }
    recorder.record("function_called", name="instruction_alignment", input_summary={"files": case.get("files", [])})
    graders = [
        code_grader(
            "required_text",
            all(not values for values in missing_required.values()),
            expected=required_text,
            actual={k: v for k, v in missing_required.items() if v},
        ),
        code_grader(
            "forbidden_text",
            all(not values for values in forbidden_present.values()),
            expected=[],
            actual={k: v for k, v in forbidden_present.items() if v},
        ),
    ]
    graders.extend(declared_graders(case))
    _record_graders(recorder, graders)

    return _case_result(case, passed_all(graders), {
        "missing_required": {k: v for k, v in missing_required.items() if v},
        "forbidden_present": {k: v for k, v in forbidden_present.items() if v},
    }, graders=graders)


def _record_graders(recorder: TranscriptRecorder, graders: List[Dict[str, Any]]) -> None:
    for grader in graders:
        recorder.record(
            "grader_result",
            name=grader.get("name"),
            type=grader.get("type"),
            passed=grader.get("passed"),
            skipped=grader.get("skipped", False),
            expected=grader.get("expected"),
            actual=grader.get("actual"),
            message=grader.get("message", ""),
        )


def _safe_artifact_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value) or "case"


def _case_result(
    case: Dict[str, Any],
    passed: bool,
    details: Dict[str, Any],
    graders: List[Dict[str, Any]] | None = None,
    transcript_path: str | None = None,
) -> Dict[str, Any]:
    case_type = case.get("type", "unknown")
    return {
        "id": case.get("id"),
        "type": case_type,
        "metric_group": CASE_TYPE_TO_METRIC.get(case_type, case_type),
        "attribution": case.get("attribution") or CASE_TYPE_TO_METRIC.get(case_type, case_type),
        "goal": case.get("goal"),
        "source": case.get("source"),
        "passed": bool(passed),
        "graders": graders or [],
        "transcript_path": transcript_path,
        "details": details,
    }


def _matching_confusion(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    for result in results:
        if result.get("type") != "matching_intent":
            continue
        actual = result.get("details", {}).get("actual", {})
        expected_keep = _case_expected_keep(result)
        predicted_keep = bool(actual.get("should_keep"))
        if expected_keep and predicted_keep:
            tp += 1
        elif not expected_keep and predicted_keep:
            fp += 1
        elif not expected_keep and not predicted_keep:
            tn += 1
        elif expected_keep and not predicted_keep:
            fn += 1

    precision = _safe_rate(tp, tp + fp)
    recall = _safe_rate(tp, tp + fn)
    f1 = _safe_rate(2 * precision * recall, precision + recall)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _case_expected_keep(result: Dict[str, Any]) -> bool:
    return bool(result.get("details", {}).get("expected_should_keep"))


def _case_rate(results: Iterable[Dict[str, Any]], case_type: str) -> float:
    selected = [result for result in results if result.get("type") == case_type]
    if not selected:
        return 0.0
    return _safe_rate(sum(1 for result in selected if result["passed"]), len(selected))


def _safe_rate(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SmartJobHunter agent evaluation")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Evaluation dataset YAML")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Evaluation report root")
    parser.add_argument("--fail-under", type=float, default=None, help="Fail when task completion is below this rate")
    parser.add_argument("--trials", type=int, default=1, help="Run each case this many times")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args(argv)

    report = run_dataset(load_dataset(args.dataset), output_root=args.output_dir, trials=args.trials)
    metrics = report["metrics"]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[Eval] Cases: {metrics['passed_cases']}/{metrics['total_cases']} passed")
        print(f"[Eval] Trials per case: {metrics['trial_count']}")
        print(f"[Eval] Task completion: {_pct(metrics['task_completion_rate'])}")
        print(f"[Eval] pass@k: {_pct(metrics['pass_at_k'])}")
        print(f"[Eval] pass^k: {_pct(metrics['pass_all_k'])}")
        print(f"[Eval] Tool/action accuracy: {_pct(metrics['tool_call_accuracy'])}")
        print(f"[Eval] Matching F1: {_pct(metrics['matching']['f1'])}")
        print(f"[Eval] Report: {report.get('markdown_report')}")

    if args.fail_under is not None and metrics["task_completion_rate"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
