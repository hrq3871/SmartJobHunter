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
FILTERED_STAGE_PREFIXES = (
    "filtered_out",
    "time_filtered",
    "deduplicated",
    "semantic_rejected",
)
DEFAULT_RECOMMENDATION_THRESHOLD = 70
HUMAN_SCORE_FIELDS = {
    "role_fit": "岗位方向分",
    "skill_match": "技能匹配分",
    "seniority_fit": "职级匹配分",
    "jd_quality": "JD质量分",
    "risk_level": "风险等级分",
    "apply_priority": "投递优先级分",
}
METRIC_DEFINITIONS = {
    "total_records": ("全量岗位数", "本次报告全量审计记录中的岗位数量。"),
    "recommended_records": ("推荐岗位数", "系统进入推荐区的岗位数量。"),
    "agent_reviewed_recommendation_rate": (
        "推荐区Agent复核率",
        "推荐岗位中判断来源为 agent 的比例；正式推荐应由 Agent 语义评分产生。",
    ),
    "filtered_records": ("过滤岗位数", "系统在推荐前过滤掉的岗位数量。"),
    "label_required_count": ("需标注数", "推荐岗位和高置信被过滤岗位中需要人工语义复核的数量。"),
    "label_completed_count": ("已标注数", "已经填写人工标签的需标注样本数。"),
    "label_completion_rate": ("标注完成率", "已标注数 / 需标注数。"),
    "recommendation_precision": ("推荐精确率", "已标推荐岗位中，人工认为 should_apply 或 maybe 的比例。"),
    "strict_recommendation_precision": ("严格推荐精确率", "系统 strong_apply 强推荐中，人工认为 should_apply 的比例。"),
    "reviewed_recall": ("人工复核召回率", "人工标为 should_apply 或 maybe 的样本中，系统成功推荐或进入 maybe 观察的比例。"),
    "reviewed_false_negative_rate": (
        "误杀率",
        "人工标为 should_apply 或 maybe、且不是候选池/报告上限截断的样本中，系统没有推荐或 maybe 观察的比例。",
    ),
    "candidate_limit_omission_rate": (
        "候选池截断率",
        "人工标为 should_apply 或 maybe 的样本中，仅因 Agent 复核池或最终报告数量上限未展示的比例。",
    ),
    "invalid_url_rate": ("全量无效链接率", "全量岗位里 URL 为空、格式非法或明显截断的比例。"),
    "recommended_invalid_url_rate": ("推荐区无效链接率", "推荐岗位里 URL 为空、格式非法或明显截断的比例。"),
    "report_exists": ("报告落盘", "真实巡检报告是否存在。"),
    "full_audit_present": ("全量审计存在", "报告是否包含全量抓取与判断记录。"),
    "application_package_exists": ("投递包落盘", "同日期投递包目录是否存在。"),
    "maybe_rate": ("模糊推荐率", "已标注样本中 maybe 的比例。"),
    "unclear_rate": ("证据不足率", "已标注样本中 unclear 的比例。"),
    "recommendation_volume": ("推荐收敛率", "推荐岗位数 / 全量岗位数，用来观察报告是否过宽或过窄。"),
}
BADCASE_TYPE_DEFINITIONS = {
    "recommendation_false_positive": {
        "zh": "推荐误报",
        "attribution": "recommendation_quality",
        "affected_metrics": ["recommendation_precision", "strict_recommendation_precision"],
        "suggested_action": "复核评分拆解、负向风险和标题党降权；修复后沉淀为推荐质量回归 case。",
    },
    "agent_review_missing": {
        "zh": "缺少Agent语义复核",
        "attribution": "recommendation_quality",
        "affected_metrics": ["agent_reviewed_recommendation_rate"],
        "suggested_action": "正式推荐必须由 Agent 输出语义评分；Python fallback 只能进入待复核候选队列。",
    },
    "filtered_false_negative": {
        "zh": "过滤误杀",
        "attribution": "matching_filtering",
        "affected_metrics": ["reviewed_recall", "reviewed_false_negative_rate"],
        "suggested_action": "复核语义过滤和阈值；修复后沉淀为语义过滤或召回 case。",
    },
    "candidate_limit_omitted": {
        "zh": "候选池截断",
        "attribution": "candidate_routing",
        "affected_metrics": ["candidate_limit_omission_rate"],
        "suggested_action": "复核 agent_review.max_candidates 与 output.max_jobs_per_report；必要时扩大 Agent 复核池，不按误杀处理。",
    },
    "recommended_invalid_url": {
        "zh": "推荐区坏链接",
        "attribution": "output_quality",
        "affected_metrics": ["recommended_invalid_url_rate", "invalid_url_rate"],
        "suggested_action": "复核 URL 校验、报告过滤和原始链接保真规则。",
    },
    "manual_invalid_link": {
        "zh": "人工确认坏链接",
        "attribution": "output_quality",
        "affected_metrics": ["recommended_invalid_url_rate", "invalid_url_rate"],
        "suggested_action": "补充真实访问校验或招聘系统过期链接规则。",
    },
    "evidence_unclear": {
        "zh": "证据不足",
        "attribution": "recommendation_quality",
        "affected_metrics": ["unclear_rate"],
        "suggested_action": "补充 JD 证据、简历证据或降低强推荐等级。",
    },
}


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
                "source_report": parsed_report.get("report_path"),
                "system_decision": record.get("system_decision"),
                "final_decision": record.get("final_decision"),
                "score": record.get("score"),
                "review_reason": reason,
                "evidence_summary": _label_evidence_summary(record),
                "scoring_breakdown": record.get("scoring_breakdown") or {},
                "human_label": None,
                "human_scores": {field: None for field in HUMAN_SCORE_FIELDS},
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
    agent_reviewed_recommended = [
        record for record in recommended_records
        if _is_agent_reviewed(record)
    ]
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
    reviewed_strong_apply_recommended = [
        item for item in reviewed_recommended
        if _is_strong_apply_recommendation(record_by_id[item["record_id"]])
    ]
    strict_positive_recommended = [
        item for item in reviewed_strong_apply_recommended
        if item["human_label"] in STRICT_POSITIVE_LABELS
    ]
    reviewed_positive = [
        item for item in completed_required
        if item["human_label"] in POSITIVE_LABELS
    ]
    reviewed_positive_for_recall = [
        item for item in reviewed_positive
        if not _is_candidate_limit_omission(record_by_id[item["record_id"]])
    ]
    reviewed_covered_positive = [
        item for item in reviewed_positive_for_recall
        if _is_recommendation_or_maybe_observation(record_by_id[item["record_id"]])
    ]
    reviewed_false_negative = [
        item for item in reviewed_positive_for_recall
        if not _is_recommendation_or_maybe_observation(record_by_id[item["record_id"]])
    ]
    candidate_limit_omitted = [
        item for item in reviewed_positive
        if _is_candidate_limit_omission(record_by_id[item["record_id"]])
        and not record_by_id[item["record_id"]].get("is_recommended")
    ]

    completed_labels = [item for item in completed_required if item.get("human_label")]
    human_score_metrics = _score_human_dimensions(completed_labels)
    bad_cases = _detect_bad_cases(records, completed_required, recommended_invalid, record_by_id)
    metrics = {
        "total_records": total_records,
        "recommended_records": len(recommended_records),
        "agent_reviewed_recommendation_rate": _safe_rate(
            len(agent_reviewed_recommended),
            len(recommended_records),
        ),
        "filtered_records": sum(
            1 for record in records
            if record.get("is_filtered") and not _is_candidate_limit_omission(record)
        ),
        "label_required_count": len(required_ids),
        "label_completed_count": len(completed_required),
        "label_completion_rate": _safe_rate(len(completed_required), len(required_ids)),
        "recommendation_precision": _safe_rate(len(positive_recommended), len(reviewed_recommended)),
        "strict_recommendation_precision": _safe_rate(
            len(strict_positive_recommended),
            len(reviewed_strong_apply_recommended),
        ),
        "reviewed_recall": _safe_rate(
            len(reviewed_covered_positive),
            len(reviewed_positive_for_recall),
        ),
        "reviewed_false_negative_rate": _safe_rate(
            len(reviewed_false_negative),
            len(reviewed_positive_for_recall),
        ),
        "candidate_limit_omission_rate": _safe_rate(
            len(candidate_limit_omitted),
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
        "human_score_metrics": human_score_metrics,
        "bad_cases": bad_cases,
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
    badcase_out = run_dir / "bad_cases.md"

    samples_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    labels_out.write_text(yaml.safe_dump(labels_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report_payload = {
        **scored,
        "artifact_dir": str(run_dir),
        "samples_path": str(samples_path),
        "labels_path": str(labels_out),
        "json_report": str(results_path),
        "markdown_report": str(report_out),
        "badcase_report": str(badcase_out),
    }
    results_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out.write_text(render_real_run_markdown(report_payload), encoding="utf-8")
    badcase_out.write_text(render_badcase_markdown(report_payload), encoding="utf-8")
    return report_payload


def render_real_run_markdown(result: Dict[str, Any]) -> str:
    """Render a concise real-run evaluation report."""
    metrics = result.get("metrics", {})
    report = result.get("report", {})
    lines = [
        "# SmartJobHunter Real Run Evaluation Report",
        "",
        f"- Status: {result.get('status')}",
        f"- Source report / 源报告: `{report.get('path')}`",
        f"- Profile ID: {report.get('profile_id') or 'N/A'}",
        f"- Generated / 生成时间: {report.get('generated') or 'N/A'}",
        f"- Full audit present / 全量审计存在: {bool(report.get('has_full_audit'))}",
        f"- Label completion rate / 标注完成率: {_pct(metrics.get('label_completion_rate', 0.0))}",
        "",
        "## Metrics / 指标",
        "",
        "| 中文指标 | 英文键 | 数值 | 说明 |",
        "|:--|:--|--:|:--|",
    ]
    metric_order = [
        "total_records",
        "recommended_records",
        "agent_reviewed_recommendation_rate",
        "filtered_records",
        "label_required_count",
        "label_completed_count",
        "recommendation_precision",
        "strict_recommendation_precision",
        "reviewed_recall",
        "reviewed_false_negative_rate",
        "candidate_limit_omission_rate",
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
        zh, desc = METRIC_DEFINITIONS.get(name, (name, ""))
        lines.append(f"| {zh} | `{name}` | {_format_metric(value)} | {desc} |")

    score_metrics = result.get("human_score_metrics") or {}
    if score_metrics:
        lines.extend(["", "## Human Score Metrics / 人工维度分", ""])
        lines.extend(["| 中文维度 | 英文键 | 平均分 | 样本数 |", "|:--|:--|--:|--:|"])
        for key, zh in HUMAN_SCORE_FIELDS.items():
            avg_key = f"{key}_avg"
            count_key = f"{key}_count"
            if avg_key not in score_metrics:
                continue
            lines.append(
                f"| {zh} | `{key}` | {score_metrics.get(avg_key)} | {score_metrics.get(count_key, 0)} |"
            )

    lines.extend(["", "## Bad Cases / 坏案例", ""])
    bad_cases = result.get("bad_cases") or []
    if bad_cases:
        lines.extend([
            "| 类型 | Record ID | 公司 | 岗位 | 系统判断 | 人工标签 | 归因 | 影响指标 | 处理建议 |",
            "|:--|:--|:--|:--|:--|:--|:--|:--|:--|",
        ])
        for case in bad_cases:
            affected = ", ".join(case.get("affected_metrics") or [])
            lines.append(
                "| {type_zh} | `{record_id}` | {company} | {title} | {system_decision} | "
                "{human_label} | `{attribution}` | {affected} | {suggested_action} |".format(
                    type_zh=case.get("badcase_type_zh"),
                    record_id=case.get("record_id"),
                    company=_md_cell(case.get("company")),
                    title=_md_cell(case.get("title")),
                    system_decision=_md_cell(case.get("system_decision")),
                    human_label=_md_cell(case.get("human_label") or "auto"),
                    attribution=case.get("attribution"),
                    affected=_md_cell(affected),
                    suggested_action=_md_cell(case.get("suggested_action")),
                )
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Missing Human Labels / 待标注样本", ""])
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
        "## Human Label Instructions / 人工标注说明",
        "",
        "- Only edit `human_labels.yaml`.",
        "- Fill `human_label` with one of: `should_apply`, `maybe`, `should_reject`, `invalid_link`, `unclear`.",
        "- Optional human dimension scores use 1-5: role_fit, skill_match, seniority_fit, jd_quality, risk_level, apply_priority.",
        "- Objective checks such as URL format, report existence, and recommendation inclusion are computed automatically.",
        "",
        "## Bad Case 处理方法",
        "",
        "1. 先看 `Bad Cases / 坏案例` 表，定位 record_id。",
        "2. 回到源报告的全量审计记录，核对 JD 证据、简历证据、评分拆解和人工标注理由。",
        "3. 按 attribution 修复：matching_filtering 修过滤，recommendation_quality 修评分和风险，output_quality 修链接/报告/投递包。",
        "4. 修复后把稳定坏例沉淀到 `evals/candidates/`，必要时晋升到 regression 或 capability eval。",
    ])
    return "\n".join(lines) + "\n"


def render_badcase_markdown(result: Dict[str, Any]) -> str:
    """Render a standalone badcase analysis document for local and Feishu sync."""
    report = result.get("report", {})
    bad_cases = result.get("bad_cases") or []
    lines = [
        "# SmartJobHunter Bad Cases",
        "",
        f"- 源报告：`{report.get('path')}`",
        f"- Profile ID：{report.get('profile_id') or 'N/A'}",
        f"- 生成时间：{report.get('generated') or 'N/A'}",
        f"- Badcase 数量：{len(bad_cases)}",
        "",
        "## 汇总",
        "",
    ]
    if not bad_cases:
        lines.append("- 本次没有发现 badcase。")
    else:
        lines.extend([
            "| 类型 | Record ID | 公司 | 岗位 | 归因 | 影响指标 | 处理建议 |",
            "|:--|:--|:--|:--|:--|:--|:--|",
        ])
        for case in bad_cases:
            lines.append(
                "| {type_zh} | `{record_id}` | {company} | {title} | `{attribution}` | {affected} | {action} |".format(
                    type_zh=case.get("badcase_type_zh"),
                    record_id=case.get("record_id"),
                    company=_md_cell(case.get("company")),
                    title=_md_cell(case.get("title")),
                    attribution=case.get("attribution"),
                    affected=_md_cell(", ".join(case.get("affected_metrics") or [])),
                    action=_md_cell(case.get("suggested_action")),
                )
            )

    lines.extend([
        "",
        "## 分析步骤",
        "",
        "1. 打开源报告，搜索对应 `record_id` 或公司岗位标题。",
        "2. 核对完整职责、完整任职要求、系统推荐理由、评分拆解、风险和人工备注。",
        "3. 判断问题属于抓取数据、语义过滤、推荐评分、输出质量还是文档漂移。",
        "4. 修复后重跑 `python -m src.evaluation --fail-under 1.0` 和真实巡检评估。",
        "5. 真实坏例稳定后，按 `evals/eval-case-feedback-loop.md` 回流到候选 case。",
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
        scoring_breakdown = _extract_score_breakdown(fields)
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
        is_filtered = _is_filtered_stage(processing_stage)
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
                "scoring_breakdown": scoring_breakdown,
                "system_reason": _extract_bullet_value(body, "判断理由"),
                "resume_evidence": _extract_bullet_value(body, "简历证据"),
                "risks": _extract_bullets(body, "风险"),
            }
        )
    return records


def _is_filtered_stage(processing_stage: str) -> bool:
    normalized = processing_stage.strip()
    return any(normalized.startswith(prefix) for prefix in FILTERED_STAGE_PREFIXES)


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
    if _is_system_maybe_observation(record):
        return "maybe_observation"
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
    if reason == "maybe_observation":
        return "medium"
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
        normalized.append({
            **item,
            "record_id": record_id,
            "human_scores": _normalize_human_scores(item.get("human_scores") or {}),
        })
    return normalized


def _label_evidence_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "system_reason": record.get("system_reason") or "",
        "resume_evidence": record.get("resume_evidence") or "",
        "risks": record.get("risks") or [],
    }


def _extract_score_breakdown(fields: Dict[str, str]) -> Dict[str, int | float | str]:
    metadata_keys = {
        "公司", "岗位名称", "地点", "类别", "完整职责", "完整任职要求", "发布时间",
        "工作年限", "原始链接", "处理状态", "判断来源", "最终结论", "总分与最终结论",
    }
    breakdown: Dict[str, int | float | str] = {}
    for key, value in fields.items():
        if key in metadata_keys:
            continue
        number = _to_number(value)
        breakdown[key] = number if number is not None else value
    return breakdown


def _extract_bullet_value(text: str, label: str) -> str:
    match = re.search(rf"(?m)^-\s*{re.escape(label)}：\s*(.*)$", text)
    return _clean_inline(match.group(1)) if match else ""


def _extract_bullets(text: str, label: str) -> List[str]:
    values = []
    for match in re.finditer(rf"(?m)^-\s*{re.escape(label)}：\s*(.*)$", text):
        values.append(_clean_inline(match.group(1)))
    return values


def _clean_inline(value: Any) -> str:
    return str(value or "").replace("<br>", "\n").strip()


def _normalize_human_scores(value: Dict[str, Any]) -> Dict[str, int | None]:
    scores: Dict[str, int | None] = {}
    for key in HUMAN_SCORE_FIELDS:
        raw = value.get(key)
        if raw in {"", None}:
            scores[key] = None
            continue
        try:
            score = int(float(raw))
        except (TypeError, ValueError):
            scores[key] = None
            continue
        scores[key] = score if 1 <= score <= 5 else None
    return scores


def _score_human_dimensions(labels: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    for key in HUMAN_SCORE_FIELDS:
        values = []
        for item in labels:
            score = (item.get("human_scores") or {}).get(key)
            if isinstance(score, (int, float)):
                values.append(float(score))
        if values:
            metrics[f"{key}_avg"] = round(sum(values) / len(values), 2)
            metrics[f"{key}_count"] = len(values)
    return metrics


def _is_agent_reviewed(record: Dict[str, Any]) -> bool:
    return str(record.get("judgment_source") or "").strip().lower() == "agent"


def _needs_agent_review_badcase(record: Dict[str, Any]) -> bool:
    return (
        bool(record.get("is_recommended"))
        and bool(record.get("url_valid"))
        and not _is_agent_reviewed(record)
    )


def _is_strong_apply_recommendation(record: Dict[str, Any]) -> bool:
    final_decision = str(record.get("final_decision") or "").strip()
    return bool(record.get("is_recommended")) and final_decision == "strong_apply"


def _is_system_maybe_observation(record: Dict[str, Any]) -> bool:
    final_decision = str(record.get("final_decision") or "").strip()
    stage = str(record.get("processing_stage") or record.get("system_decision") or "").strip()
    return final_decision == "maybe" or stage.startswith("agent_maybe")


def _is_recommendation_or_maybe_observation(record: Dict[str, Any]) -> bool:
    return bool(record.get("is_recommended")) or _is_system_maybe_observation(record)


def _is_candidate_limit_omission(record: Dict[str, Any]) -> bool:
    stage = str(record.get("processing_stage") or record.get("system_decision") or "").strip()
    score = record.get("score")
    if stage.startswith(("candidate_limit_omitted", "report_limit_omitted")):
        return True
    if "agent_review_queue_limit" in stage or "final_report_limit" in stage:
        return True
    if "score_below_threshold_or_report_limit" in stage:
        return isinstance(score, (int, float)) and score >= DEFAULT_RECOMMENDATION_THRESHOLD
    return False


def _detect_bad_cases(
    records: List[Dict[str, Any]],
    completed_labels: List[Dict[str, Any]],
    recommended_invalid: List[Dict[str, Any]],
    record_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in completed_labels:
        label = item.get("human_label")
        if not label:
            continue
        record = record_by_id.get(item["record_id"])
        if not record:
            continue
        if record.get("is_recommended") and label == "should_reject":
            cases.append(_badcase_entry("recommendation_false_positive", record, item))
            seen.add((record["record_id"], "recommendation_false_positive"))
        if _needs_agent_review_badcase(record):
            key = (record["record_id"], "agent_review_missing")
            if key not in seen:
                cases.append(_badcase_entry("agent_review_missing", record, item))
                seen.add(key)
        if (
            not record.get("is_recommended")
            and label == "maybe"
            and _is_system_maybe_observation(record)
        ):
            continue
        if not record.get("is_recommended") and label in POSITIVE_LABELS:
            badcase_type = (
                "candidate_limit_omitted"
                if _is_candidate_limit_omission(record)
                else "filtered_false_negative"
            )
            cases.append(_badcase_entry(badcase_type, record, item))
            seen.add((record["record_id"], badcase_type))
        if record.get("is_recommended") and label == "invalid_link":
            cases.append(_badcase_entry("manual_invalid_link", record, item))
            seen.add((record["record_id"], "manual_invalid_link"))
        if label == "unclear":
            cases.append(_badcase_entry("evidence_unclear", record, item))
            seen.add((record["record_id"], "evidence_unclear"))

    for record in recommended_invalid:
        key = (record["record_id"], "recommended_invalid_url")
        if key in seen:
            continue
        cases.append(_badcase_entry("recommended_invalid_url", record, None))
    for record in records:
        if not _needs_agent_review_badcase(record):
            continue
        key = (record["record_id"], "agent_review_missing")
        if key in seen:
            continue
        cases.append(_badcase_entry("agent_review_missing", record, None))
        seen.add(key)
    return cases


def _badcase_entry(
    badcase_type: str,
    record: Dict[str, Any],
    label_item: Dict[str, Any] | None,
) -> Dict[str, Any]:
    definition = BADCASE_TYPE_DEFINITIONS[badcase_type]
    affected_metrics = list(definition["affected_metrics"])
    if badcase_type == "recommendation_false_positive" and not _is_strong_apply_recommendation(record):
        affected_metrics = [
            metric for metric in affected_metrics
            if metric != "strict_recommendation_precision"
        ]
    return {
        "badcase_type": badcase_type,
        "badcase_type_zh": definition["zh"],
        "record_id": record.get("record_id"),
        "company": record.get("company"),
        "title": record.get("title"),
        "url": record.get("url"),
        "system_decision": record.get("system_decision"),
        "final_decision": record.get("final_decision"),
        "score": record.get("score"),
        "human_label": (label_item or {}).get("human_label"),
        "human_scores": (label_item or {}).get("human_scores") or {},
        "human_reason": (label_item or {}).get("review_notes") or "",
        "attribution": definition["attribution"],
        "affected_metrics": affected_metrics,
        "suggested_action": definition["suggested_action"],
    }


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


def _to_number(value: Any) -> int | float | None:
    if value is None:
        return None
    text = str(value).strip()
    match = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


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


def _md_cell(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


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
