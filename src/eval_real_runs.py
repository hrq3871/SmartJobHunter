#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Evaluate real SmartJobHunter run reports with lightweight human labels."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from .reporting import validate_original_url


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "evals" / "real_runs"
ALLOWED_HUMAN_LABELS = ["should_apply", "maybe", "should_reject", "invalid_link", "unclear"]
POSITIVE_LABELS = {"should_apply", "maybe"}
STRICT_POSITIVE_LABELS = {"should_apply"}
UNCLEAR_LABELS = {"unclear"}


def parse_report(report_path: str | Path) -> Dict[str, Any]:
    """Parse one generated SmartJobHunter report into auditable records."""
    path = Path(report_path)
    text = path.read_text(encoding="utf-8")
    metadata = _parse_basic_info(text)
    records = _parse_audit_records(text)
    package_path = _find_application_package(path)
    return {
        "report_path": str(path),
        "report_name": path.name,
        "report_exists": path.exists(),
        "profile": metadata.get("Profile") or metadata.get("意向"),
        "profile_id": metadata.get("Profile ID") or metadata.get("Profile") or path.stem,
        "generated": metadata.get("Generated") or metadata.get("生成时间"),
        "jobs_found": _to_int(metadata.get("Jobs Found") or metadata.get("岗位数")),
        "has_full_audit": "## 全量抓取与判断记录" in text,
        "application_package_exists": package_path is not None,
        "application_package_path": str(package_path) if package_path else None,
        "records": records,
    }


def build_human_label_template(parsed_report: Dict[str, Any]) -> Dict[str, Any]:
    """Build the small human-label file for records that need semantic review."""
    labels = []
    for record in parsed_report.get("records", []):
        reason = _review_reason(record)
        if not reason:
            continue
        labels.append(
            {
                "record_id": record["record_id"],
                "company": record.get("company"),
                "title": record.get("title"),
                "url": record.get("url"),
                "system_decision": record.get("system_decision"),
                "final_decision": record.get("final_decision"),
                "score": record.get("score"),
                "review_reason": reason,
                "human_label": None,
                "severity": _default_severity(reason),
                "review_notes": "",
            }
        )

    return {
        "version": 1,
        "report_path": parsed_report.get("report_path"),
        "profile_id": parsed_report.get("profile_id"),
        "generated": parsed_report.get("generated"),
        "instructions": (
            "Only fill human_label and optional review_notes. "
            "Allowed labels: should_apply, maybe, should_reject, invalid_link, unclear."
        ),
        "allowed_labels": ALLOWED_HUMAN_LABELS,
        "labels": labels,
    }


def score_real_run(parsed_report: Dict[str, Any], labels_doc: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Combine automatic checks and human labels into real-run metrics."""
    labels_doc = labels_doc or build_human_label_template(parsed_report)
    records = parsed_report.get("records", [])
    record_by_id = {record["record_id"]: record for record in records}
    required_ids = {item["record_id"] for item in build_human_label_template(parsed_report)["labels"]}
    labels = _normalize_labels(labels_doc.get("labels", []), record_by_id)

    completed_required = [
        item for item in labels
        if item["record_id"] in required_ids and item.get("human_label")
    ]
    missing_labels = [
        item for item in labels_doc.get("labels", [])
        if item.get("record_id") in required_ids and not item.get("human_label")
    ]

    total_records = len(records)
    recommended_records = [record for record in records if record.get("is_recommended")]
    invalid_url_records = [record for record in records if not record.get("url_valid")]
    recommended_invalid = [
        record for record in recommended_records
        if not record.get("url_valid")
    ]

    reviewed_recommended = [
        item for item in completed_required
        if record_by_id[item["record_id"]].get("is_recommended")
        and item["human_label"] not in UNCLEAR_LABELS
    ]
    positive_recommended = [
        item for item in reviewed_recommended
        if item["human_label"] in POSITIVE_LABELS
    ]
    strict_positive_recommended = [
        item for item in reviewed_recommended
        if item["human_label"] in STRICT_POSITIVE_LABELS
    ]
    reviewed_positive = [
        item for item in completed_required
        if item["human_label"] in POSITIVE_LABELS
    ]
    reviewed_positive_recommended = [
        item for item in reviewed_positive
        if record_by_id[item["record_id"]].get("is_recommended")
    ]
    reviewed_false_negative = [
        item for item in reviewed_positive
        if not record_by_id[item["record_id"]].get("is_recommended")
    ]

    completed_labels = [item for item in completed_required if item.get("human_label")]
    metrics = {
        "total_records": total_records,
        "recommended_records": len(recommended_records),
        "filtered_records": sum(1 for record in records if record.get("is_filtered")),
        "label_required_count": len(required_ids),
        "label_completed_count": len(completed_required),
        "label_completion_rate": _safe_rate(len(completed_required), len(required_ids)),
        "recommendation_precision": _safe_rate(len(positive_recommended), len(reviewed_recommended)),
        "strict_recommendation_precision": _safe_rate(
            len(strict_positive_recommended),
            len(reviewed_recommended),
        ),
        "reviewed_recall": _safe_rate(
            len(reviewed_positive_recommended),
            len(reviewed_positive),
        ),
        "reviewed_false_negative_rate": _safe_rate(
            len(reviewed_false_negative),
            len(reviewed_positive),
        ),
        "invalid_url_rate": _safe_rate(len(invalid_url_records), total_records),
        "recommended_invalid_url_rate": _safe_rate(len(recommended_invalid), len(recommended_records)),
        "report_exists": 1.0 if parsed_report.get("report_exists") else 0.0,
        "full_audit_present": 1.0 if parsed_report.get("has_full_audit") else 0.0,
        "application_package_exists": 1.0 if parsed_report.get("application_package_exists") else 0.0,
        "maybe_rate": _safe_rate(
            sum(1 for item in completed_labels if item["human_label"] == "maybe"),
            len(completed_labels),
        ),
        "unclear_rate": _safe_rate(
            sum(1 for item in completed_labels if item["human_label"] == "unclear"),
            len(completed_labels),
        ),
        "recommendation_volume": _safe_rate(len(recommended_records), total_records),
    }

    status = "complete" if not missing_labels else "needs_human_labels"
    return {
        "status": status,
        "report": {
            "path": parsed_report.get("report_path"),
            "profile_id": parsed_report.get("profile_id"),
            "generated": parsed_report.get("generated"),
            "has_full_audit": parsed_report.get("has_full_audit"),
            "application_package_path": parsed_report.get("application_package_path"),
        },
        "metrics": metrics,
        "missing_labels": [
            {
                "record_id": item.get("record_id"),
                "company": item.get("company"),
                "title": item.get("title"),
                "review_reason": item.get("review_reason"),
            }
            for item in missing_labels
        ],
        "labels": labels_doc,
    }


def run_real_run_evaluation(
    report_path: str | Path,
    labels_path: str | Path | None = None,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> Dict[str, Any]:
    """Parse, score, and write a real-run evaluation artifact bundle."""
    parsed = parse_report(report_path)
    if labels_path:
        labels_doc = yaml.safe_load(Path(labels_path).read_text(encoding="utf-8")) or {}
    else:
        labels_doc = build_human_label_template(parsed)

    scored = score_real_run(parsed, labels_doc)
    run_dir = _real_run_dir(Path(output_root), Path(report_path), parsed)
    run_dir.mkdir(parents=True, exist_ok=True)

    samples_path = run_dir / "real_run_samples.json"
    labels_out = run_dir / "human_labels.yaml"
    results_path = run_dir / "real_run_eval_results.json"
    report_out = run_dir / "real_run_eval_report.md"

    samples_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    labels_out.write_text(yaml.safe_dump(labels_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report_payload = {
        **scored,
        "artifact_dir": str(run_dir),
        "samples_path": str(samples_path),
        "labels_path": str(labels_out),
        "json_report": str(results_path),
        "markdown_report": str(report_out),
    }
    results_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out.write_text(render_real_run_markdown(report_payload), encoding="utf-8")
    return report_payload


def render_real_run_markdown(result: Dict[str, Any]) -> str:
    """Render a concise real-run evaluation report."""
    metrics = result.get("metrics", {})
    report = result.get("report", {})
    lines = [
        "# SmartJobHunter Real Run Evaluation Report",
        "",
        f"- Status: {result.get('status')}",
        f"- Source report: `{report.get('path')}`",
        f"- Profile ID: {report.get('profile_id') or 'N/A'}",
        f"- Generated: {report.get('generated') or 'N/A'}",
        f"- Full audit present: {bool(report.get('has_full_audit'))}",
        f"- Label completion rate: {_pct(metrics.get('label_completion_rate', 0.0))}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|:--|--:|",
    ]
    metric_order = [
        "total_records",
        "recommended_records",
        "filtered_records",
        "label_required_count",
        "label_completed_count",
        "recommendation_precision",
        "strict_recommendation_precision",
        "reviewed_recall",
        "reviewed_false_negative_rate",
        "invalid_url_rate",
        "recommended_invalid_url_rate",
        "report_exists",
        "full_audit_present",
        "application_package_exists",
        "maybe_rate",
        "unclear_rate",
        "recommendation_volume",
    ]
    for name in metric_order:
        value = metrics.get(name)
        lines.append(f"| {name} | {_format_metric(value)} |")

    lines.extend(["", "## Missing Human Labels", ""])
    missing = result.get("missing_labels") or []
    if missing:
        for item in missing:
            lines.append(
                f"- `{item.get('record_id')}` {item.get('company')} - "
                f"{item.get('title')} ({item.get('review_reason')})"
            )
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Human Label Instructions",
        "",
        "- Only edit `human_labels.yaml`.",
        "- Fill `human_label` with one of: `should_apply`, `maybe`, `should_reject`, `invalid_link`, `unclear`.",
        "- Objective checks such as URL format, report existence, and recommendation inclusion are computed automatically.",
    ])
    return "\n".join(lines) + "\n"


def _parse_basic_info(text: str) -> Dict[str, str]:
    info: Dict[str, str] = {}
    in_basic = False
    for line in text.splitlines():
        if line.startswith("## "):
            if in_basic:
                break
            in_basic = line.strip() in {"## Basic Info", "## 基本信息"}
            continue
        if not in_basic:
            continue
        match = re.match(r"- \*\*(.+?)\*\*:\s*(.*)", line)
        if match:
            info[match.group(1).strip()] = match.group(2).strip()
    return info


def _parse_audit_records(text: str) -> List[Dict[str, Any]]:
    marker = "## 全量抓取与判断记录"
    if marker not in text:
        return []
    audit_text = text.split(marker, 1)[1]
    parts = re.split(r"(?m)^###\s+(\d+)\.\s+(.+?)\s*$", audit_text)
    records: List[Dict[str, Any]] = []
    for index in range(1, len(parts), 3):
        number = _to_int(parts[index])
        heading = parts[index + 1].strip()
        body = parts[index + 2]
        fields = _parse_markdown_tables(body)
        company, title = _split_heading(heading)
        company = fields.get("公司") or company
        title = fields.get("岗位名称") or title
        url_text = fields.get("原始链接", "")
        url = _extract_markdown_url(url_text)
        url_valid, url_reason = validate_original_url(url)
        if not url and "empty_url" in url_text:
            url_reason = "empty_url"
        score, score_decision = _parse_score_and_decision(fields.get("总分与最终结论"))
        final_decision = fields.get("最终结论") or score_decision
        processing_stage = fields.get("处理状态", "")
        is_recommended = processing_stage.strip().startswith("recommended")
        is_filtered = processing_stage.strip().startswith("filtered_out")
        records.append(
            {
                "record_id": f"{number:03d}" if number is not None else f"{len(records) + 1:03d}",
                "company": company,
                "title": title,
                "url": url,
                "url_valid": bool(url_valid),
                "url_failure_reason": None if url_valid else url_reason,
                "processing_stage": processing_stage,
                "system_decision": "recommended" if is_recommended else "filtered_out" if is_filtered else processing_stage,
                "is_recommended": is_recommended,
                "is_filtered": is_filtered,
                "judgment_source": fields.get("判断来源"),
                "final_decision": final_decision,
                "score": score,
            }
        )
    return records


def _find_application_package(report_path: Path) -> Path | None:
    package_root = report_path.parent / "application_packages"
    exact = package_root / report_path.stem
    if exact.exists() and exact.is_dir():
        return exact
    if not package_root.exists():
        return None
    candidates = sorted(
        [path for path in package_root.iterdir() if path.is_dir() and path.name.startswith(report_path.stem)],
        key=lambda path: path.name,
    )
    return candidates[0] if candidates else None


def _parse_markdown_tables(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _split_markdown_row(line)
        if len(cells) < 2:
            continue
        key = cells[0].strip()
        value = cells[1].strip()
        if not key or set(key) <= {"-", ":"}:
            continue
        if key in {"字段", "维度"}:
            continue
        fields[key] = value
    return fields


def _split_markdown_row(line: str) -> List[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    cells: List[str] = []
    current: List[str] = []
    escaped = False
    for char in value:
        if char == "\\" and not escaped:
            escaped = True
            current.append(char)
            continue
        if char == "|" and not escaped:
            cells.append("".join(current).replace("\\|", "|").strip())
            current = []
            continue
        current.append(char)
        escaped = False
    cells.append("".join(current).replace("\\|", "|").strip())
    return cells


def _split_heading(heading: str) -> tuple[str | None, str]:
    for separator in ("－", " - ", "-"):
        if separator in heading:
            company, title = heading.split(separator, 1)
            return company.strip(), title.strip()
    return None, heading.strip()


def _extract_markdown_url(value: str) -> str:
    match = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", value or "")
    if match:
        return match.group(1).strip()
    if value and value.startswith("http"):
        return value.split("（", 1)[0].strip()
    return ""


def _parse_score_and_decision(value: str | None) -> tuple[int | None, str | None]:
    if not value:
        return None, None
    match = re.search(r"(-?\d+)\s*/\s*([^|]+)", value)
    if not match:
        return None, None
    return int(match.group(1)), match.group(2).strip()


def _review_reason(record: Dict[str, Any]) -> str | None:
    if not record.get("url_valid"):
        return None
    final_decision = str(record.get("final_decision") or "").strip()
    score = record.get("score")
    if record.get("is_recommended"):
        return "recommended"
    if final_decision in {"strong_apply", "apply"}:
        return "high_confidence_filtered"
    if isinstance(score, int) and score >= 70:
        return "high_confidence_filtered"
    return None


def _default_severity(reason: str) -> str:
    if reason == "recommended":
        return "medium"
    if reason == "high_confidence_filtered":
        return "high"
    return "low"


def _normalize_labels(labels: Iterable[Dict[str, Any]], record_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in labels:
        record_id = str(item.get("record_id") or "")
        if record_id not in record_by_id:
            continue
        label = item.get("human_label")
        if label is not None and label not in ALLOWED_HUMAN_LABELS:
            raise ValueError(f"Unsupported human_label for {record_id}: {label}")
        normalized.append({**item, "record_id": record_id})
    return normalized


def _real_run_dir(output_root: Path, report_path: Path, parsed: Dict[str, Any]) -> Path:
    generated = str(parsed.get("generated") or "")
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", generated)
    date_part = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
    suffix = datetime.now().strftime("%H%M%S")
    return output_root / date_part / f"{_safe_name(report_path.stem)}_{suffix}"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "real_run"


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else None


def _safe_rate(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _pct(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return _pct(value)
    if value is None:
        return "N/A"
    return str(value)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a real SmartJobHunter run report")
    parser.add_argument("--report", required=True, help="Path to output/YYYY-MM-DD/<report>.md")
    parser.add_argument("--labels", default=None, help="Optional human_labels.yaml to score")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Artifact output root")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args(argv)

    result = run_real_run_evaluation(args.report, labels_path=args.labels, output_root=args.output_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[Real Eval] Status: {result['status']}")
        print(f"[Real Eval] Label completion: {_pct(result['metrics']['label_completion_rate'])}")
        print(f"[Real Eval] Recommendation precision: {_pct(result['metrics']['recommendation_precision'])}")
        print(f"[Real Eval] Report: {result['markdown_report']}")
        print(f"[Real Eval] Labels: {result['labels_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
