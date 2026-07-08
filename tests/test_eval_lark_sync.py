from pathlib import Path

import yaml

from src.eval_lark_sync import (
    ANNOTATION_TABLE_NAME,
    build_annotation_rows,
    build_labels_doc_from_lark_records,
    format_lark_error,
    lark_field_definitions,
)
from src.eval_real_runs import build_human_label_template, parse_report
from tests.test_eval_real_runs import _sample_real_report


def test_lark_field_definitions_include_context_and_editable_fields():
    fields = lark_field_definitions()
    names = [field["name"] for field in fields]

    assert ANNOTATION_TABLE_NAME == "SmartHunter真实评估标注"
    assert names[:4] == ["标注ID", "评估运行ID", "源报告", "记录ID"]
    assert "系统推荐理由" in names
    assert "评分拆解摘要" in names
    assert "人工标签" in names
    assert "岗位方向分" in names
    assert "投递优先级分" in names
    assert "人工备注" in names


def test_build_annotation_rows_keeps_context_but_not_full_jd(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)
    labels = build_human_label_template(parsed)

    rows = build_annotation_rows(labels, run_id="run_001")
    first = rows[0]

    assert first["标注ID"] == "run_001:001"
    assert first["评估运行ID"] == "run_001"
    assert first["记录ID"] == "001"
    assert first["系统推荐理由"] == "AI Agent 支付平台产品匹配"
    assert "目标岗位匹配=22" in first["评分拆解摘要"]
    assert first["人工标签"] == ""
    assert first["岗位方向分"] is None
    assert "完整职责" not in first
    assert "完整任职要求" not in first


def test_build_labels_doc_from_lark_records_maps_labels_and_scores(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)
    template = build_human_label_template(parsed)
    records = [
        {
            "fields": {
                "评估运行ID": "run_001",
                "记录ID": "001",
                "人工标签": "should_apply",
                "岗位方向分": 5,
                "技能匹配分": "4",
                "职级匹配分": "",
                "JD质量分": 4,
                "风险等级分": 2,
                "投递优先级分": 5,
                "人工备注": "值得投",
            }
        },
        {
            "fields": {
                "评估运行ID": "other_run",
                "记录ID": "002",
                "人工标签": "should_reject",
            }
        },
    ]

    labels_doc = build_labels_doc_from_lark_records(template, records, run_id="run_001")

    assert labels_doc["labels"][0]["human_label"] == "should_apply"
    assert labels_doc["labels"][0]["human_scores"]["role_fit"] == 5
    assert labels_doc["labels"][0]["human_scores"]["skill_match"] == 4
    assert labels_doc["labels"][0]["human_scores"]["seniority_fit"] is None
    assert labels_doc["labels"][0]["review_notes"] == "值得投"
    assert labels_doc["labels"][1]["human_label"] is None


def test_labels_doc_from_lark_records_can_be_saved_as_yaml(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)
    template = build_human_label_template(parsed)
    labels_doc = build_labels_doc_from_lark_records(
        template,
        [{"记录ID": "001", "人工标签": "maybe", "岗位方向分": 4}],
    )

    out = tmp_path / "human_labels.from_feishu.yaml"
    out.write_text(yaml.safe_dump(labels_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    loaded = yaml.safe_load(out.read_text(encoding="utf-8"))

    assert loaded["labels"][0]["human_label"] == "maybe"
    assert loaded["labels"][0]["human_scores"]["role_fit"] == 4


def test_format_lark_error_suggests_base_auth_and_cli_update():
    error = RuntimeError(
        '{"ok": false, "error": {"message": "API call failed: need_user_authorization"}, '
        '"_notice": {"update": {"current": "1.0.14", "latest": "1.0.56"}}}'
    )

    message = format_lark_error(error)

    assert "lark-cli auth login --domain base" in message
    assert "lark-cli 1.0.56 available" in message
