"""Markdown rendering helpers for auditable SmartHunter reports."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse


def validate_original_url(url: str) -> tuple[bool, str | None]:
    """Accept only complete HTTP(S) URLs and reject visibly truncated values."""
    value = str(url or "")
    if not value:
        return False, "empty_url"
    if "..." in value or "…" in value:
        return False, "truncated_url"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "invalid_url"
    return True, None


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _bullet(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_full_crawl_audit(records: list[dict]) -> str:
    """Render every crawled record, including rejected and filtered jobs."""
    chunks = ["## 全量抓取与判断记录", ""]
    if not records:
        chunks.extend(["> 本次未抓取到岗位。", ""])
        return "\n".join(chunks)

    for index, record in enumerate(records, 1):
        job = record.get("raw_job") or {}
        processing = record.get("processing") or {}
        evaluation = record.get("evaluation") or {}
        semantic = evaluation.get("semantic_decision") or {}
        url = str(record.get("original_url") or "")
        valid_url, url_reason = validate_original_url(url)
        if valid_url:
            link_value = f"[{url}]({url})"
        else:
            link_value = f"{url or 'N/A'}（{url_reason}）"

        stage = processing.get("stage") or "crawled"
        if processing.get("reason"):
            stage = f"{stage}: {processing['reason']}"
        final_decision = evaluation.get("final_decision") or "N/A"
        title = job.get("title") or "Unknown"
        company = job.get("company") or "Unknown"
        chunks.extend(
            [
                f"### {index}. {company}－{title}",
                "",
                "| 字段 | 内容 |",
                "|---|---|",
                f"| 公司 | {_cell(company)} |",
                f"| 岗位名称 | {_cell(title)} |",
                f"| 地点 | {_cell(job.get('location'))} |",
                f"| 类别 | {_cell(job.get('category'))} |",
                f"| 完整职责 | {_cell(job.get('duty'))} |",
                f"| 完整任职要求 | {_cell(job.get('requirement'))} |",
                f"| 发布时间 | {_cell(job.get('publish_time'))} |",
                f"| 工作年限 | {_cell(job.get('work_years'))} |",
                f"| 原始链接 | {link_value} |",
                f"| 处理状态 | {_cell(stage)} |",
                f"| 判断来源 | {_cell(evaluation.get('source') or 'python_fallback')} |",
                f"| 最终结论 | {_cell(final_decision)} |",
                "",
                "#### 语义判断及引用证据",
                f"- 是否保留：{_cell(semantic.get('should_keep'))}",
            ]
        )
        reasons = semantic.get("match_reasons") or semantic.get("match_reason") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        chunks.append(f"- 判断理由：{_cell('；'.join(map(str, reasons)))}")
        evidence = semantic.get("evidence") or {}
        if evidence:
            _EVI_LABELS = {
                "target_role": "目标岗位命中", "must_have": "关键要求命中",
                "target_domains": "目标领域命中", "nice_to_have": "加分项命中",
                "keywords": "关键词命中", "excluded_terms": "排除词命中",
                "negative_role": "疑似噪声角色",
            }
            for k, v in evidence.items():
                label = _EVI_LABELS.get(k, k)
                val = "、".join(map(str, (v or [])[:8]))
                chunks.append(f"- {label}：{_cell(val) if val else '无'}")
        matched = evaluation.get("matched_evidence") or []
        chunks.append(f"- 简历证据：{_cell(matched)}")
        gaps = evaluation.get("gaps") or []
        if gaps:
            for g in gaps:
                if isinstance(g, dict):
                    chunks.append(f"- 缺口：{_cell(g.get('requirement', '') + ' → ' + g.get('suggestion', ''))}")
                else:
                    chunks.append(f"- 缺口：{_cell(str(g))}")
        risks = evaluation.get("risks") or []
        for r in risks:
            chunks.append(f"- 风险：{_cell(str(r))}")
        _SCORE_LABELS = {
            "target_role_fit": "目标岗位匹配",
            "core_responsibility_fit": "核心职责匹配",
            "core_role_fit": "核心角色匹配",
            "domain_fit": "领域匹配",
            "resume_evidence": "简历证据",
            "preference_fit": "偏好匹配",
            "evidence_quality": "证据质量",
            "risk_penalty": "风险扣分",
            "fallback_quality": "评分类别",
            "domain_strengths": "领域强度",
        }
        chunks.extend(["", "#### 评分拆解", "", "| 维度 | 分数 |", "|---|---:|"])
        for key, value in (evaluation.get("scoring_breakdown") or {}).items():
            if isinstance(value, (dict, list)):
                continue
            label = _SCORE_LABELS.get(key, key)
            chunks.append(f"| {_cell(label)} | {_cell(value)} |")
        chunks.append(f"| 总分与最终结论 | {_cell(evaluation.get('score'))} / {_cell(final_decision)} |")
        chunks.extend(["", "---", ""])
    return "\n".join(chunks)

