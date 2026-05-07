#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import load_dataset, render_markdown_report, run_dataset


def test_default_eval_dataset_passes_offline(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path)

    assert report["metrics"]["task_completion_rate"] == 1.0
    assert report["metrics"]["tool_call_accuracy"] == 1.0
    assert report["metrics"]["matching"]["f1"] == 1.0
    assert Path(report["markdown_report"]).exists()


def test_eval_report_contains_attribution_and_metric_groups(tmp_path):
    report = run_dataset(load_dataset(), output_root=tmp_path, write_artifacts=False)
    markdown = render_markdown_report(report)

    assert "Task completion rate" in markdown
    assert "crawler_strategy" in markdown
    assert "No failed cases" in markdown
