#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from src.eval_real_runs import (
    build_human_label_template,
    parse_report,
    run_real_run_evaluation,
    score_real_run,
)


def _sample_real_report() -> str:
    return """# Job Hunting Report

## Basic Info
- **Profile**: 胡睿琪
- **Profile ID**: eval_profile
- **Generated**: 2026-07-08 20:00
- **Jobs Found**: 2

## Recommended Jobs

### 1. 支付平台AI智能产品经理 [🟢] Score: 82

**Link**: [https://jobs.example/a](https://jobs.example/a)

---

## 全量抓取与判断记录

### 1. 美团－支付平台AI智能产品经理

| 字段 | 内容 |
|---|---|
| 公司 | 美团 |
| 岗位名称 | 支付平台AI智能产品经理 |
| 原始链接 | [https://jobs.example/a](https://jobs.example/a) |
| 处理状态 | recommended |
| 判断来源 | python_fallback |
| 最终结论 | apply |

#### 语义判断及引用证据
- 是否保留：True
- 判断理由：AI Agent 支付平台产品匹配

#### 评分拆解

| 维度 | 分数 |
|---|---:|
| 总分与最终结论 | 82 / apply |

---

### 2. 腾讯－腾讯会议-AI产品经理-ASR方向

| 字段 | 内容 |
|---|---|
| 公司 | 腾讯 |
| 岗位名称 | 腾讯会议-AI产品经理-ASR方向 |
| 原始链接 | [https://jobs.example/b](https://jobs.example/b) |
| 处理状态 | filtered_out: score_below_threshold_or_report_limit |
| 判断来源 | python_fallback |
| 最终结论 | apply |

#### 语义判断及引用证据
- 是否保留：True
- 判断理由：AI 产品方向相关

#### 评分拆解

| 维度 | 分数 |
|---|---:|
| 总分与最终结论 | 76 / apply |

---

### 3. 字节－失效AI产品经理

| 字段 | 内容 |
|---|---|
| 公司 | 字节 |
| 岗位名称 | 失效AI产品经理 |
| 原始链接 | N/A（empty_url） |
| 处理状态 | recommended |
| 判断来源 | python_fallback |
| 最终结论 | apply |

#### 评分拆解

| 维度 | 分数 |
|---|---:|
| 总分与最终结论 | 80 / apply |

---

### 4. 锐捷网络－27实习-AI算法工程师

| 字段 | 内容 |
|---|---|
| 公司 | 锐捷网络 |
| 岗位名称 | 27实习-AI算法工程师 |
| 原始链接 | [https://jobs.example/d](https://jobs.example/d) |
| 处理状态 | filtered_out: filtered_before_recommendation |
| 判断来源 | python_fallback |
| 最终结论 | skip |

#### 评分拆解

| 维度 | 分数 |
|---|---:|
| 总分与最终结论 | 31 / skip |
"""


def test_parse_report_extracts_audit_records_and_auto_url_state(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    package_dir = tmp_path / "application_packages" / report_path.stem
    package_dir.mkdir(parents=True)

    parsed = parse_report(report_path)

    assert parsed["profile_id"] == "eval_profile"
    assert parsed["report_path"] == str(report_path)
    assert parsed["report_exists"] is True
    assert parsed["application_package_exists"] is True
    assert parsed["application_package_path"] == str(package_dir)
    assert len(parsed["records"]) == 4
    assert parsed["records"][0]["record_id"] == "001"
    assert parsed["records"][0]["company"] == "美团"
    assert parsed["records"][0]["is_recommended"] is True
    assert parsed["records"][0]["score"] == 82
    assert parsed["records"][0]["url_valid"] is True
    assert parsed["records"][2]["url_valid"] is False
    assert parsed["records"][2]["url_failure_reason"] == "empty_url"


def test_human_template_excludes_objective_invalid_and_low_confidence_rejects(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)

    labels = build_human_label_template(parsed)

    assert [item["record_id"] for item in labels["labels"]] == ["001", "002"]
    assert labels["labels"][0]["review_reason"] == "recommended"
    assert labels["labels"][1]["review_reason"] == "high_confidence_filtered"
    assert all(item["human_label"] is None for item in labels["labels"])


def test_score_real_run_combines_human_labels_with_auto_metrics(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)
    labels = build_human_label_template(parsed)
    labels["labels"][0]["human_label"] = "should_apply"
    labels["labels"][1]["human_label"] = "should_apply"

    scored = score_real_run(parsed, labels)
    metrics = scored["metrics"]

    assert scored["status"] == "complete"
    assert metrics["label_completion_rate"] == 1.0
    assert metrics["recommendation_precision"] == 1.0
    assert metrics["strict_recommendation_precision"] == 1.0
    assert metrics["reviewed_recall"] == 0.5
    assert metrics["reviewed_false_negative_rate"] == 0.5
    assert metrics["invalid_url_rate"] == 0.25
    assert metrics["recommended_invalid_url_rate"] == 0.5
    assert metrics["report_exists"] == 1.0
    assert metrics["full_audit_present"] == 1.0


def test_run_real_run_evaluation_writes_template_and_report(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")

    result = run_real_run_evaluation(report_path, output_root=tmp_path / "evals")

    output_dir = Path(result["artifact_dir"])
    assert (output_dir / "real_run_samples.json").exists()
    assert (output_dir / "human_labels.yaml").exists()
    assert (output_dir / "real_run_eval_results.json").exists()
    assert (output_dir / "real_run_eval_report.md").exists()

    labels = yaml.safe_load((output_dir / "human_labels.yaml").read_text(encoding="utf-8"))
    assert [item["record_id"] for item in labels["labels"]] == ["001", "002"]
    report_text = (output_dir / "real_run_eval_report.md").read_text(encoding="utf-8")
    assert "Label completion rate" in report_text
    assert "Missing Human Labels" in report_text
