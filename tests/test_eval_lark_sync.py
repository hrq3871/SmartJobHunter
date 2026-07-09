from pathlib import Path

import yaml

from src.eval_lark_sync import (
    ANNOTATION_TABLE_NAME,
    BADCASE_DOC_TITLE,
    EVAL_REPORT_DOC_TITLE,
    build_annotation_rows,
    build_labels_doc_from_lark_records,
    format_lark_error,
    lark_field_definitions,
    make_lark_json_arg,
    setup_feishu_eval_resources,
    sync_badcases_to_lark_doc,
    sync_report_to_lark_doc,
    _extract_records,
)
from src.eval_real_runs import build_human_label_template, parse_report
from tests.test_eval_real_runs import _sample_real_report


def test_lark_field_definitions_include_context_and_editable_fields():
    fields = lark_field_definitions()
    names = [field["name"] for field in fields]

    assert ANNOTATION_TABLE_NAME == "SmartHunter真实评估标注"
    assert names[:4] == ["标注ID", "评估运行ID", "源报告", "记录ID"]
    assert BADCASE_DOC_TITLE == "SmartHunter真实评估BadCases"
    assert EVAL_REPORT_DOC_TITLE == "SmartHunter真实评估报告"
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


def test_build_labels_doc_accepts_lark_cli_field_row_shape(tmp_path):
    report_path = tmp_path / "eval_profile_20260708_2000.md"
    report_path.write_text(_sample_real_report(), encoding="utf-8")
    parsed = parse_report(report_path)
    template = build_human_label_template(parsed)
    lark_response = {
        "fields": ["评估运行ID", "记录ID", "人工标签", "岗位方向分", "人工备注"],
        "data": [["run_001", "001", ["maybe"], 4, "飞书回拉"]],
    }

    labels_doc = build_labels_doc_from_lark_records(
        template,
        _extract_records(lark_response),
        run_id="run_001",
    )

    assert labels_doc["labels"][0]["human_label"] == "maybe"
    assert labels_doc["labels"][0]["human_scores"]["role_fit"] == 4
    assert labels_doc["labels"][0]["review_notes"] == "飞书回拉"


def test_format_lark_error_suggests_base_auth_and_cli_update():
    error = RuntimeError(
        '{"ok": false, "error": {"message": "API call failed: need_user_authorization"}, '
        '"_notice": {"update": {"current": "1.0.14", "latest": "1.0.56"}}}'
    )

    message = format_lark_error(error)

    assert "lark-cli auth login --domain base" in message
    assert "lark-cli 1.0.56 available" in message


def test_make_lark_json_arg_uses_relative_workspace_file():
    arg = make_lark_json_arg({"fields": ["标题"], "rows": [["任务"]]})

    assert arg.startswith("@.lark_tmp/")
    assert ":" not in arg


def test_sync_badcases_appends_to_managed_lark_doc(tmp_path, monkeypatch):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        "feishu:\n"
        "  eval_badcase_doc_id: badcase_doc_001\n",
        encoding="utf-8",
    )
    calls = []

    def fake_run(cmd, input_text=None):
        calls.append((cmd, input_text))
        return {"success": True}

    monkeypatch.setattr("src.eval_lark_sync._run_lark_json", fake_run)

    result = sync_badcases_to_lark_doc("# Badcase\n\n旧原因不能被覆盖", config_path)

    assert result["success"] is True
    assert calls[0][0][1:5] == ["docs", "+update", "--doc", "badcase_doc_001"]
    assert "--mode" in calls[0][0]
    assert calls[0][0][calls[0][0].index("--mode") + 1] == "append"
    assert "旧原因不能被覆盖" in calls[0][1]


def test_sync_report_appends_to_managed_lark_doc(tmp_path, monkeypatch):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        "feishu:\n"
        "  eval_report_doc_id: report_doc_001\n",
        encoding="utf-8",
    )
    calls = []

    def fake_run(cmd, input_text=None):
        calls.append((cmd, input_text))
        return {"success": True}

    monkeypatch.setattr("src.eval_lark_sync._run_lark_json", fake_run)

    result = sync_report_to_lark_doc("# Real Run Evaluation\n\n推荐精确率：100%", config_path)

    assert result["success"] is True
    assert calls[0][0][1:5] == ["docs", "+update", "--doc", "report_doc_001"]
    assert calls[0][0][calls[0][0].index("--mode") + 1] == "append"
    assert "推荐精确率" in calls[0][1]


def test_setup_creates_annotation_badcase_and_report_resources(tmp_path, monkeypatch):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        "feishu:\n"
        "  bitable_token: base_001\n"
        "  wiki_space_id: wiki_001\n",
        encoding="utf-8",
    )

    def fake_run(cmd, input_text=None):
        joined = " ".join(cmd)
        if "base +table-list" in joined:
            return {"items": []}
        if "base +table-create" in joined:
            return {"table": {"table_id": "tbl_eval"}}
        if "docs +create" in joined and BADCASE_DOC_TITLE in cmd:
            return {"doc_id": "badcase_doc_001", "doc_url": "https://feishu/badcase"}
        if "docs +create" in joined and EVAL_REPORT_DOC_TITLE in cmd:
            return {"doc_id": "report_doc_001", "doc_url": "https://feishu/report"}
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("src.eval_lark_sync._run_lark_json", fake_run)

    result = setup_feishu_eval_resources(config_path)
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert result["annotation_table_id"] == "tbl_eval"
    assert result["badcase_doc_id"] == "badcase_doc_001"
    assert result["report_doc_id"] == "report_doc_001"
    assert saved["feishu"]["eval_report_doc_url"] == "https://feishu/report"
