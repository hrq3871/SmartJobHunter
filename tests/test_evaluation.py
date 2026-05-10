#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import DEFAULT_DATASET, load_dataset, render_markdown_report, run_dataset


def test_default_eval_dataset_passes_offline(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path)

    assert report["metrics"]["task_completion_rate"] == 1.0
    assert report["metrics"]["tool_call_accuracy"] == 1.0
    assert report["metrics"]["matching"]["f1"] == 1.0
    assert Path(report["markdown_report"]).exists()
    assert "evals/regression/jobhunter_core.yaml" in str(DEFAULT_DATASET).replace("\\", "/")


def test_eval_report_contains_attribution_and_metric_groups(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path, write_artifacts=False)
    markdown = render_markdown_report(report)

    assert "Task completion rate" in markdown
    assert "crawler_strategy" in markdown
    assert "No failed cases" in markdown


def test_eval_results_include_graders_and_transcripts(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path)
    first_result = report["results"][0]

    assert first_result["graders"]
    assert first_result["graders"][0]["type"] == "code"
    assert Path(first_result["transcript_path"]).exists()

    transcript_text = Path(first_result["transcript_path"]).read_text(encoding="utf-8")
    assert "case_started" in transcript_text
    assert "grader_result" in transcript_text


def test_eval_supports_multi_trial_metrics(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path, trials=3)

    assert report["metrics"]["trial_count"] == 3
    assert report["metrics"]["pass_at_k"] == 1.0
    assert report["metrics"]["pass_all_k"] == 1.0
    assert report["results"][0]["trial_count"] == 3
    assert len(report["results"][0]["trials"]) == 3


def test_workflow_outcome_case_generates_report_package_and_memory(tmp_path):
    dataset = {
        "name": "Workflow Outcome Eval",
        "version": 1,
        "cases": [
            {
                "id": "workflow_should_generate_report_package_and_memory",
                "type": "workflow_outcome",
                "attribution": "output_quality",
                "profile": {
                    "name": "AI产品经理",
                    "_profile_id": "eval_ai_pm",
                    "_resume_content": "5年 ToB SaaS 产品经验，主导 AI 助手从0到1上线。",
                },
                "jobs": [
                    {
                        "title": "AI产品经理",
                        "company": "A公司",
                        "url": "https://example.com/a",
                        "hash": "validhash001",
                        "duty": "负责 AI 产品规划。",
                        "requirement": "需要 ToB 产品经验。",
                        "mock_available": True,
                    },
                    {
                        "title": "失效岗位",
                        "company": "B公司",
                        "url": "https://example.com/404",
                        "hash": "invalidhash001",
                        "mock_available": False,
                    },
                ],
                "evaluations": [
                    {
                        "score": 95,
                        "recommendation": "strong_apply",
                        "match_reasons": ["AI 产品方向匹配"],
                    },
                    {
                        "score": 88,
                        "recommendation": "apply",
                        "match_reasons": ["一般匹配"],
                    },
                ],
                "expected": {
                    "report_exists": True,
                    "package_top_n": 1,
                    "excluded_titles": ["失效岗位"],
                    "memory_contains": ["AI产品经理"],
                },
            }
        ],
    }

    report = run_dataset(dataset, output_root=tmp_path)
    result = report["results"][0]

    assert result["passed"] is True
    assert Path(result["details"]["report_path"]).exists()
    assert Path(result["details"]["package_path"]).exists()
    assert Path(result["details"]["memory_path"]).read_text(encoding="utf-8")
