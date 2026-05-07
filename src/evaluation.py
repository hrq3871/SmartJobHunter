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
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from .cli import JobHunter
from .matching import evaluate_job_fit, match_job_intent, summarize_resume_ability
from .site_inspector import inspect_html_signals
from .strategy_planner import plan_strategy_action


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "evals" / "jobhunter_agent_eval.yaml"
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "evals"


CASE_TYPE_TO_METRIC = {
    "matching_intent": "matching_filtering",
    "job_fit": "recommendation_quality",
    "strategy_action": "crawler_strategy",
    "url_filter": "output_quality",
    "application_package": "output_quality",
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
) -> Dict[str, Any]:
    """Run all cases and return aggregate metrics plus per-case details."""
    output_root = Path(output_root)
    run_started = datetime.now()
    run_dir = output_root / run_started.strftime("%Y-%m-%d") / run_started.strftime("%Y%m%d_%H%M%S")
    if write_artifacts:
        run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for case in dataset.get("cases", []):
        results.append(run_case(case, run_dir if write_artifacts else None))

    metrics = compute_metrics(results)
    report = {
        "name": dataset.get("name", "SmartJobHunter Agent Evaluation"),
        "dataset": dataset.get("_dataset_path"),
        "version": dataset.get("version"),
        "run_started_at": run_started.isoformat(timespec="seconds"),
        "case_count": len(results),
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


def run_case(case: Dict[str, Any], run_dir: Path | None = None) -> Dict[str, Any]:
    """Dispatch one case by type."""
    case_type = case.get("type")
    handlers = {
        "matching_intent": _run_matching_intent_case,
        "job_fit": _run_job_fit_case,
        "strategy_action": _run_strategy_action_case,
        "url_filter": _run_url_filter_case,
        "application_package": lambda item: _run_application_package_case(item, run_dir),
        "instruction_alignment": _run_instruction_alignment_case,
    }
    handler = handlers.get(case_type)
    if handler is None:
        return _case_result(case, False, {"error": f"unsupported case type: {case_type}"})

    try:
        return handler(case)
    except Exception as exc:  # pragma: no cover - defensive reporting
        return _case_result(case, False, {"error": str(exc), "exception_type": type(exc).__name__})


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute product-level metrics from case results."""
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    by_type = defaultdict(lambda: {"passed": 0, "total": 0, "rate": 0.0})
    by_metric = defaultdict(lambda: {"passed": 0, "total": 0, "rate": 0.0})
    attribution = Counter()

    for result in results:
        case_type = result.get("type", "unknown")
        metric_name = result.get("metric_group") or CASE_TYPE_TO_METRIC.get(case_type, case_type)
        by_type[case_type]["total"] += 1
        by_metric[metric_name]["total"] += 1
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

    return {
        "task_completion_rate": _safe_rate(passed, total),
        "passed_cases": passed,
        "total_cases": total,
        "by_type": dict(sorted(by_type.items())),
        "by_metric": dict(sorted(by_metric.items())),
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
        f"- Task completion rate: {_pct(metrics['task_completion_rate'])}",
        f"- Tool/action accuracy: {_pct(metrics['tool_call_accuracy'])}",
        f"- Matching precision: {_pct(metrics['matching']['precision'])}",
        f"- Matching recall: {_pct(metrics['matching']['recall'])}",
        f"- Matching F1: {_pct(metrics['matching']['f1'])}",
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
        if not result["passed"]:
            lines.append(f"  - Details: {json.dumps(result.get('details', {}), ensure_ascii=False)}")

    return "\n".join(lines) + "\n"


def _run_matching_intent_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case.get("expected", {})
    actual = match_job_intent(
        case.get("job", {}),
        case.get("profile", {}),
        decision_level=case.get("decision_level", "moderate"),
    )

    checks = {
        "should_keep": actual.get("should_keep") == expected.get("should_keep"),
    }
    if "min_match_score" in expected:
        checks["min_match_score"] = actual.get("match_score", 0) >= float(expected["min_match_score"])
    if "max_match_score" in expected:
        checks["max_match_score"] = actual.get("match_score", 0) <= float(expected["max_match_score"])

    return _case_result(case, all(checks.values()), {
        "actual": actual,
        "expected_should_keep": expected.get("should_keep"),
        "checks": checks,
    })


def _run_job_fit_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case.get("expected", {})
    resume_text = case.get("resume", "")
    actual = evaluate_job_fit(
        case.get("job", {}),
        case.get("profile", {}),
        resume_text=resume_text,
        ability_profile=summarize_resume_ability(resume_text),
    )

    checks: Dict[str, bool] = {}
    if "min_score" in expected:
        checks["min_score"] = actual.get("score", 0) >= int(expected["min_score"])
    if "max_score" in expected:
        checks["max_score"] = actual.get("score", 0) <= int(expected["max_score"])
    if "recommendation_in" in expected:
        checks["recommendation_in"] = actual.get("recommendation") in expected["recommendation_in"]
    if "recommendation_not_in" in expected:
        checks["recommendation_not_in"] = actual.get("recommendation") not in expected["recommendation_not_in"]

    return _case_result(case, all(checks.values()), {"actual": actual, "checks": checks})


def _run_strategy_action_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case.get("expected", {})
    inspection = dict(case.get("inspection") or {})
    if case.get("html") is not None or case.get("text") is not None:
        signal_result = inspect_html_signals(case.get("html", ""), case.get("text", ""))
        inspection["signals"] = sorted(set(inspection.get("signals") or []) | set(signal_result["signals"]))

    actual = plan_strategy_action(case.get("company", {}), inspection)
    checks = {
        "action": actual.get("action") == expected.get("action"),
    }
    if "requires_agent" in expected:
        checks["requires_agent"] = actual.get("requires_agent") == expected["requires_agent"]
    if "block_type" in expected:
        checks["block_type"] = actual.get("block_type") == expected["block_type"]
    if "reason_contains" in expected:
        checks["reason_contains"] = expected["reason_contains"] in str(actual.get("reason", ""))
    if "signal_absent" in expected:
        checks["signal_absent"] = expected["signal_absent"] not in set(inspection.get("signals") or [])

    return _case_result(case, all(checks.values()), {
        "actual": actual,
        "inspection": inspection,
        "checks": checks,
    })


def _run_url_filter_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case.get("expected", {})
    jobs = case.get("jobs", [])
    evaluations = case.get("evaluations", [])
    availability = {job.get("url", ""): bool(job.get("mock_available")) for job in jobs}
    hunter = JobHunter()
    hunter._url_is_available = lambda url: availability.get(url, False)  # type: ignore[method-assign]
    valid_jobs, valid_evaluations = hunter._filter_live_urls(jobs, evaluations)

    actual_titles = [job.get("title") for job in valid_jobs]
    checks = {
        "kept_titles": actual_titles == expected.get("kept_titles", []),
        "evaluation_alignment": len(valid_jobs) == len(valid_evaluations),
    }
    return _case_result(case, all(checks.values()), {
        "actual_titles": actual_titles,
        "checks": checks,
    })


def _run_application_package_case(case: Dict[str, Any], run_dir: Path | None) -> Dict[str, Any]:
    expected = case.get("expected", {})
    with TemporaryDirectory() as tmp_dir:
        hunter = JobHunter()
        hunter.output_dir = Path(tmp_dir if run_dir is None else run_dir / "artifacts")
        package_path = Path(hunter.generate_application_package(
            case.get("jobs", []),
            case.get("profile", {}),
            case.get("evaluations", []),
        ))
        cover_letters = sorted(package_path.glob("cover_letter_*.md"))
        combined_text = "\n".join(path.read_text(encoding="utf-8") for path in cover_letters)
        checks = {
            "cover_letter_count": len(cover_letters) == int(expected.get("cover_letter_count", 0)),
            "index_exists": (package_path / "index.md").exists(),
            "required_text": all(text in combined_text for text in expected.get("required_text", [])),
        }
        details = {
            "package_path": str(package_path),
            "cover_letter_count": len(cover_letters),
            "checks": checks,
        }
        return _case_result(case, all(checks.values()), details)


def _run_instruction_alignment_case(case: Dict[str, Any]) -> Dict[str, Any]:
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
    checks = {
        "required_text": all(not values for values in missing_required.values()),
        "forbidden_text": all(not values for values in forbidden_present.values()),
    }

    return _case_result(case, all(checks.values()), {
        "missing_required": {k: v for k, v in missing_required.items() if v},
        "forbidden_present": {k: v for k, v in forbidden_present.items() if v},
        "checks": checks,
    })


def _case_result(case: Dict[str, Any], passed: bool, details: Dict[str, Any]) -> Dict[str, Any]:
    case_type = case.get("type", "unknown")
    return {
        "id": case.get("id"),
        "type": case_type,
        "metric_group": CASE_TYPE_TO_METRIC.get(case_type, case_type),
        "attribution": case.get("attribution") or CASE_TYPE_TO_METRIC.get(case_type, case_type),
        "passed": bool(passed),
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
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args(argv)

    report = run_dataset(load_dataset(args.dataset), output_root=args.output_dir)
    metrics = report["metrics"]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[Eval] Cases: {metrics['passed_cases']}/{metrics['total_cases']} passed")
        print(f"[Eval] Task completion: {_pct(metrics['task_completion_rate'])}")
        print(f"[Eval] Tool/action accuracy: {_pct(metrics['tool_call_accuracy'])}")
        print(f"[Eval] Matching F1: {_pct(metrics['matching']['f1'])}")
        print(f"[Eval] Report: {report.get('markdown_report')}")

    if args.fail_under is not None and metrics["task_completion_rate"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
