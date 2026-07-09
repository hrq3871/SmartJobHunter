#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sync real-run evaluation labels and review docs with Feishu/Lark."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List
from uuid import uuid4

import yaml

from .eval_real_runs import (
    ALLOWED_HUMAN_LABELS,
    DEFAULT_OUTPUT_ROOT,
    HUMAN_SCORE_FIELDS,
    build_human_label_template,
    parse_report,
    run_real_run_evaluation,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "agent.yaml"
ANNOTATION_TABLE_NAME = "SmartHunter真实评估标注"
BADCASE_DOC_TITLE = "SmartHunter真实评估BadCases"
EVAL_REPORT_DOC_TITLE = "SmartHunter真实评估报告"
LABEL_FIELD = "人工标签"
NOTE_FIELD = "人工备注"
RUN_ID_FIELD = "评估运行ID"
RECORD_ID_FIELD = "记录ID"
ANNOTATION_FIELD_ORDER = [
    "标注ID",
    RUN_ID_FIELD,
    "源报告",
    RECORD_ID_FIELD,
    "公司",
    "岗位",
    "岗位链接",
    "系统判断",
    "最终结论",
    "AI总分",
    "复核原因",
    "系统推荐理由",
    "简历证据摘要",
    "风险摘要",
    "评分拆解摘要",
    LABEL_FIELD,
    "岗位方向分",
    "技能匹配分",
    "职级匹配分",
    "JD质量分",
    "风险等级分",
    "投递优先级分",
    NOTE_FIELD,
]
HUMAN_SCORE_TO_LARK = {
    "role_fit": "岗位方向分",
    "skill_match": "技能匹配分",
    "seniority_fit": "职级匹配分",
    "jd_quality": "JD质量分",
    "risk_level": "风险等级分",
    "apply_priority": "投递优先级分",
}
LARK_SCORE_TO_HUMAN = {value: key for key, value in HUMAN_SCORE_TO_LARK.items()}


def lark_field_definitions() -> List[Dict[str, Any]]:
    """Return the Feishu Base schema for the human annotation table."""
    label_options = [
        {"name": "should_apply", "hue": "Green", "lightness": "Light"},
        {"name": "maybe", "hue": "Yellow", "lightness": "Light"},
        {"name": "should_reject", "hue": "Red", "lightness": "Light"},
        {"name": "invalid_link", "hue": "Orange", "lightness": "Light"},
        {"name": "unclear", "hue": "Gray", "lightness": "Light"},
    ]
    fields: List[Dict[str, Any]] = [
        {"name": "标注ID", "type": "text", "description": "评估运行ID + 记录ID，作为人工标注的稳定键。"},
        {"name": RUN_ID_FIELD, "type": "text"},
        {"name": "源报告", "type": "text"},
        {"name": RECORD_ID_FIELD, "type": "text"},
        {"name": "公司", "type": "text"},
        {"name": "岗位", "type": "text"},
        {"name": "岗位链接", "type": "text", "style": {"type": "url"}},
        {"name": "系统判断", "type": "text"},
        {"name": "最终结论", "type": "text"},
        {"name": "AI总分", "type": "number", "style": {"type": "plain", "precision": 0}},
        {"name": "复核原因", "type": "text"},
        {"name": "系统推荐理由", "type": "text"},
        {"name": "简历证据摘要", "type": "text"},
        {"name": "风险摘要", "type": "text"},
        {"name": "评分拆解摘要", "type": "text"},
        {"name": LABEL_FIELD, "type": "select", "multiple": False, "options": label_options},
    ]
    for field_name in HUMAN_SCORE_TO_LARK.values():
        fields.append(
            {
                "name": field_name,
                "type": "number",
                "description": "人工 1-5 分；留空则不参与该维度指标。",
                "style": {"type": "rating", "icon": "star", "min": 1, "max": 5},
            }
        )
    fields.append({"name": NOTE_FIELD, "type": "text"})
    return fields


def build_annotation_rows(labels_doc: Dict[str, Any], run_id: str | None = None) -> List[Dict[str, Any]]:
    """Convert the local human-label template into lightweight Feishu rows."""
    run_id = run_id or _default_run_id(labels_doc)
    rows = []
    for item in labels_doc.get("labels", []):
        evidence = item.get("evidence_summary") or {}
        row = {
            "标注ID": f"{run_id}:{item.get('record_id')}",
            RUN_ID_FIELD: run_id,
            "源报告": item.get("source_report") or labels_doc.get("report_path") or "",
            RECORD_ID_FIELD: item.get("record_id"),
            "公司": item.get("company") or "",
            "岗位": item.get("title") or "",
            "岗位链接": item.get("url") or "",
            "系统判断": item.get("system_decision") or "",
            "最终结论": item.get("final_decision") or "",
            "AI总分": item.get("score"),
            "复核原因": item.get("review_reason") or "",
            "系统推荐理由": evidence.get("system_reason") or "",
            "简历证据摘要": evidence.get("resume_evidence") or "",
            "风险摘要": "；".join(map(str, evidence.get("risks") or [])),
            "评分拆解摘要": _score_summary(item.get("scoring_breakdown") or {}),
            LABEL_FIELD: item.get("human_label") or "",
            NOTE_FIELD: item.get("review_notes") or "",
        }
        for key, field_name in HUMAN_SCORE_TO_LARK.items():
            row[field_name] = (item.get("human_scores") or {}).get(key)
        rows.append(row)
    return rows


def build_labels_doc_from_lark_records(
    labels_template: Dict[str, Any],
    records: Iterable[Dict[str, Any]],
    run_id: str | None = None,
) -> Dict[str, Any]:
    """Merge Feishu-filled labels back into a local human_labels document."""
    labels_doc = copy.deepcopy(labels_template)
    by_record_id = {str(item.get("record_id")): item for item in labels_doc.get("labels", [])}
    for raw in records:
        fields = _record_fields(raw)
        if run_id and _to_text(fields.get(RUN_ID_FIELD)) != run_id:
            continue
        record_id = _to_text(fields.get(RECORD_ID_FIELD))
        if record_id not in by_record_id:
            continue
        label = _to_text(fields.get(LABEL_FIELD)).strip()
        if label and label not in ALLOWED_HUMAN_LABELS:
            raise ValueError(f"Unsupported Feishu human label for {record_id}: {label}")
        target = by_record_id[record_id]
        if label:
            target["human_label"] = label
        target["review_notes"] = _to_text(fields.get(NOTE_FIELD)) or str(target.get("review_notes") or "")
        scores = target.setdefault("human_scores", {field: None for field in HUMAN_SCORE_FIELDS})
        for lark_name, human_key in LARK_SCORE_TO_HUMAN.items():
            score = _to_score(fields.get(lark_name))
            if score is not None:
                scores[human_key] = score
    return labels_doc


def setup_feishu_eval_resources(config_path: str | Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Create the annotation table and badcase doc if they are missing."""
    config_path = Path(config_path)
    config = _load_config(config_path)
    feishu = config.setdefault("feishu", {})
    base_token = feishu.get("bitable_token")
    if not base_token:
        raise RuntimeError("Missing feishu.bitable_token in config/agent.yaml")

    annotation_table_id = feishu.get("eval_annotation_table_id") or _find_table(base_token, ANNOTATION_TABLE_NAME)
    created_table = False
    if not annotation_table_id:
        annotation_table_id = _create_annotation_table(base_token)
        created_table = True

    badcase_doc_id = feishu.get("eval_badcase_doc_id")
    badcase_doc_url = feishu.get("eval_badcase_doc_url")
    created_doc = False
    if not badcase_doc_id:
        created = _create_badcase_doc(feishu)
        badcase_doc_id = created.get("doc_id")
        badcase_doc_url = created.get("doc_url") or created.get("url")
        created_doc = True

    report_doc_id = feishu.get("eval_report_doc_id")
    report_doc_url = feishu.get("eval_report_doc_url")
    created_report_doc = False
    if not report_doc_id:
        created = _create_report_doc(feishu)
        report_doc_id = created.get("doc_id")
        report_doc_url = created.get("doc_url") or created.get("url")
        created_report_doc = True

    feishu["eval_annotation_table_id"] = annotation_table_id
    if badcase_doc_id:
        feishu["eval_badcase_doc_id"] = badcase_doc_id
    if badcase_doc_url:
        feishu["eval_badcase_doc_url"] = badcase_doc_url
    if report_doc_id:
        feishu["eval_report_doc_id"] = report_doc_id
    if report_doc_url:
        feishu["eval_report_doc_url"] = report_doc_url
    _save_config(config_path, config)
    return {
        "annotation_table_id": annotation_table_id,
        "badcase_doc_id": badcase_doc_id,
        "badcase_doc_url": badcase_doc_url,
        "report_doc_id": report_doc_id,
        "report_doc_url": report_doc_url,
        "created_table": created_table,
        "created_doc": created_doc,
        "created_report_doc": created_report_doc,
        "config_path": str(config_path),
    }


def export_labels_to_lark(
    labels_doc: Dict[str, Any],
    run_id: str | None = None,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Append the current label template into the Feishu annotation table."""
    config = _load_config(Path(config_path))
    feishu = config.get("feishu", {})
    base_token = feishu.get("bitable_token")
    table_id = feishu.get("eval_annotation_table_id")
    if not base_token or not table_id:
        raise RuntimeError("Missing feishu.bitable_token or feishu.eval_annotation_table_id")
    rows = build_annotation_rows(labels_doc, run_id=run_id)
    fields = ANNOTATION_FIELD_ORDER
    created = 0
    for index in range(0, len(rows), 200):
        batch = rows[index:index + 200]
        payload = {"fields": fields, "rows": [[row.get(field) for field in fields] for row in batch]}
        _run_lark_json([
            _lark_cli(), "base", "+record-batch-create",
            "--base-token", base_token,
            "--table-id", table_id,
            "--json", _json_arg(payload),
            "--as", "user",
        ])
        created += len(batch)
        time.sleep(0.5)
    return {"exported": created, "run_id": run_id or _default_run_id(labels_doc), "table_id": table_id}


def import_labels_from_lark(
    labels_template: Dict[str, Any],
    run_id: str | None = None,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Read Feishu annotation records and merge them into the local label doc."""
    config = _load_config(Path(config_path))
    feishu = config.get("feishu", {})
    base_token = feishu.get("bitable_token")
    table_id = feishu.get("eval_annotation_table_id")
    if not base_token or not table_id:
        raise RuntimeError("Missing feishu.bitable_token or feishu.eval_annotation_table_id")
    data = _run_lark_json([
        _lark_cli(), "base", "+record-list",
        "--base-token", base_token,
        "--table-id", table_id,
        "--limit", "200",
        "--as", "user",
    ])
    records = _extract_records(data)
    return build_labels_doc_from_lark_records(labels_template, records, run_id=run_id)


def sync_badcases_to_lark_doc(
    markdown: str,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Append manual badcase analysis to the managed Feishu badcase document."""
    return _append_markdown_to_lark_doc(
        markdown,
        config_path=config_path,
        doc_id_key="eval_badcase_doc_id",
        doc_url_key="eval_badcase_doc_url",
        missing_message="Missing feishu.eval_badcase_doc_id; run setup first",
    )


def sync_report_to_lark_doc(
    markdown: str,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Append one run's human-readable evaluation report to Feishu."""
    return _append_markdown_to_lark_doc(
        markdown,
        config_path=config_path,
        doc_id_key="eval_report_doc_id",
        doc_url_key="eval_report_doc_url",
        missing_message="Missing feishu.eval_report_doc_id; run setup first",
    )


def _append_markdown_to_lark_doc(
    markdown: str,
    *,
    config_path: str | Path,
    doc_id_key: str,
    doc_url_key: str,
    missing_message: str,
) -> Dict[str, Any]:
    """Append markdown to a configured Feishu doc without replacing historical runs."""
    config = _load_config(Path(config_path))
    feishu = config.get("feishu", {})
    doc_id = feishu.get(doc_id_key) or feishu.get(doc_url_key)
    if not doc_id:
        raise RuntimeError(missing_message)
    return _run_lark_json([
        _lark_cli(), "docs", "+update",
        "--doc", doc_id,
        "--mode", "append",
        "--markdown", "-",
        "--as", "user",
    ], input_text=_append_section(markdown))


def format_lark_error(error: Exception) -> str:
    """Return a user-actionable message for common lark-cli failures."""
    text = str(error).strip()
    parsed: Dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    message = text
    notice = None
    if parsed:
        error_obj = parsed.get("error") or {}
        message = str(error_obj.get("message") or parsed.get("message") or text)
        notice = (parsed.get("_notice") or {}).get("update") or {}

    hints = [f"[Feishu] {message}"]
    if "need_user_authorization" in message:
        hints.append("请先完成飞书 Base 用户授权：lark-cli auth login --domain base")
    if notice:
        current = notice.get("current")
        latest = notice.get("latest")
        if current and latest:
            hints.append(f"lark-cli {latest} available, current {current}; 当前任务完成后建议更新 CLI 和 skills。")
    return "\n".join(hints)


def _find_table(base_token: str, table_name: str) -> str | None:
    data = _run_lark_json([
        _lark_cli(), "base", "+table-list",
        "--base-token", base_token,
        "--limit", "100",
        "--as", "user",
    ])
    for item in _extract_items(data):
        if item.get("table_name") == table_name or item.get("name") == table_name:
            return item.get("table_id") or item.get("id")
    return None


def _create_annotation_table(base_token: str) -> str:
    data = _run_lark_json([
        _lark_cli(), "base", "+table-create",
        "--base-token", base_token,
        "--name", ANNOTATION_TABLE_NAME,
        "--fields", json.dumps(lark_field_definitions(), ensure_ascii=False),
        "--view", json.dumps([{"name": "待标注", "type": "grid"}], ensure_ascii=False),
        "--as", "user",
    ])
    table = data.get("table") or data.get("data", {}).get("table") or data.get("data", {})
    table_id = table.get("table_id") or table.get("id")
    if not table_id:
        raise RuntimeError(f"Unable to parse created table id: {data}")
    return table_id


def _create_badcase_doc(feishu_config: Dict[str, Any]) -> Dict[str, Any]:
    return _create_eval_doc(
        feishu_config,
        title=BADCASE_DOC_TITLE,
        initial_markdown=(
            "# SmartHunter真实评估BadCases\n\n"
            "这里不自动同步真实评估报告中的 badcase 列表；报告已经列出 badcase。\n\n"
            "本页只追加人工复盘、原因分析、处理方案和修复记录。需要更新时，由用户明确要求后再写入。\n"
        ),
    )


def _create_report_doc(feishu_config: Dict[str, Any]) -> Dict[str, Any]:
    return _create_eval_doc(
        feishu_config,
        title=EVAL_REPORT_DOC_TITLE,
        initial_markdown=(
            "# SmartHunter真实评估报告\n\n"
            "这里按运行时间追加人看的真实巡检评估报告，包含中文指标、人工维度分和 badcase 摘要。\n"
        ),
    )


def _create_eval_doc(feishu_config: Dict[str, Any], *, title: str, initial_markdown: str) -> Dict[str, Any]:
    cmd = [
        _lark_cli(), "docs", "+create",
        "--title", title,
        "--markdown", "-",
        "--as", "user",
    ]
    if feishu_config.get("wiki_space_id"):
        cmd.extend(["--wiki-space", str(feishu_config["wiki_space_id"])])
    elif feishu_config.get("wiki_node_token"):
        cmd.extend(["--wiki-node", str(feishu_config["wiki_node_token"])])
    data = _run_lark_json(cmd, input_text=initial_markdown)
    return data.get("data") or data


def _append_section(markdown: str) -> str:
    body = markdown.strip()
    return f"\n\n---\n\n{body}\n"


def _is_generated_badcase_report(markdown: str) -> bool:
    text = markdown.strip()
    return (
        text.startswith("# SmartJobHunter Bad Cases")
        and "## 汇总" in text
        and "## 分析步骤" in text
    )


def _manual_badcase_sync_skipped() -> Dict[str, Any]:
    return {
        "skipped": True,
        "reason": "manual_badcase_analysis_required",
        "message": (
            "Generated badcase lists are already included in real_run_eval_report.md. "
            "Only append user-requested analysis and handling notes to SmartHunter真实评估BadCases."
        ),
    }


def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    return payload.get("items") or payload.get("tables") or []


def _extract_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(payload, dict):
        return payload if isinstance(payload, list) else []
    rows = payload.get("items") or payload.get("records")
    if rows:
        return rows
    data_rows = payload.get("data")
    fields = payload.get("fields")
    if isinstance(data_rows, list) and isinstance(fields, list):
        records = []
        for row in data_rows:
            if isinstance(row, dict):
                records.append(row)
            elif isinstance(row, list):
                records.append(dict(zip(fields, row)))
        return records
    return data_rows if isinstance(data_rows, list) else []


def _record_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    if "fields" in record and isinstance(record["fields"], dict):
        return record["fields"]
    return record


def _default_run_id(labels_doc: Dict[str, Any]) -> str:
    report_path = Path(str(labels_doc.get("report_path") or "real_run.md"))
    generated = str(labels_doc.get("generated") or "").replace(" ", "_").replace(":", "")
    return f"{report_path.stem}_{generated}" if generated else report_path.stem


def _score_summary(scoring_breakdown: Dict[str, Any]) -> str:
    return "；".join(f"{key}={value}" for key, value in scoring_breakdown.items())


def _to_score(value: Any) -> int | None:
    if value in {"", None}:
        return None
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 5 else None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(_to_text(item) for item in value if _to_text(item))
    return str(value)


def _load_config(config_path: Path) -> Dict[str, Any]:
    if config_path.exists():
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return {}


def _save_config(config_path: Path, config: Dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _lark_cli() -> str:
    candidate = os.path.expandvars(r"%APPDATA%\npm\lark-cli.cmd")
    return candidate if os.path.exists(candidate) else "lark-cli"


def make_lark_json_arg(payload: Dict[str, Any]) -> str:
    # Avoid fragile shell quoting for larger unicode payloads.
    tmp_dir = Path(".lark_tmp")
    tmp_dir.mkdir(exist_ok=True)
    path = tmp_dir / f"payload_{uuid4().hex}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return f"@{path.as_posix()}"


def _json_arg(payload: Dict[str, Any]) -> str:
    return make_lark_json_arg(payload)


def _run_lark_json(cmd: List[str], input_text: str | None = None) -> Dict[str, Any]:
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        shell=True if os.name == "nt" else False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"lark-cli failed: {cmd[:3]}")
    stdout = (result.stdout or "").strip()
    if not stdout:
        return {}
    data = json.loads(stdout)
    if data.get("ok") is False:
        raise RuntimeError(json.dumps(data.get("error") or data, ensure_ascii=False))
    return data.get("data") if isinstance(data.get("data"), dict) else data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync SmartJobHunter real-run labels with Feishu")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Create or locate Feishu annotation resources")
    setup.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    export = sub.add_parser("export-labels", help="Export local human_labels.yaml to Feishu")
    export.add_argument("--labels", required=True)
    export.add_argument("--run-id", default=None)
    export.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    pull = sub.add_parser("import-labels", help="Import Feishu labels into local human_labels yaml")
    pull.add_argument("--report", required=True)
    pull.add_argument("--run-id", default=None)
    pull.add_argument("--output", default=None)
    pull.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    score = sub.add_parser("score-from-lark", help="Import Feishu labels, score report, and append Feishu docs")
    score.add_argument("--report", required=True)
    score.add_argument("--run-id", default=None)
    score.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    score.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    score.add_argument("--sync-badcases", action="store_true")
    score.add_argument("--sync-report", action="store_true")

    badcase = sub.add_parser("sync-badcases", help="Append manual badcase analysis markdown to Feishu doc")
    badcase.add_argument("--badcases", required=True, help="Path to a manual badcase analysis markdown file")
    badcase.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    report = sub.add_parser("sync-report", help="Append a local real_run_eval_report.md to Feishu doc")
    report.add_argument("--report", required=True)
    report.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    args = parser.parse_args(argv)

    try:
        if args.command == "setup":
            result = setup_feishu_eval_resources(args.config)
        elif args.command == "export-labels":
            labels_doc = yaml.safe_load(Path(args.labels).read_text(encoding="utf-8")) or {}
            result = export_labels_to_lark(labels_doc, run_id=args.run_id, config_path=args.config)
        elif args.command == "import-labels":
            parsed = parse_report(args.report)
            template = build_human_label_template(parsed)
            labels_doc = import_labels_from_lark(template, run_id=args.run_id, config_path=args.config)
            output = Path(args.output) if args.output else Path(args.report).with_suffix(".human_labels.from_feishu.yaml")
            output.write_text(yaml.safe_dump(labels_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = {"labels_path": str(output), "run_id": args.run_id}
        elif args.command == "score-from-lark":
            parsed = parse_report(args.report)
            template = build_human_label_template(parsed)
            labels_doc = import_labels_from_lark(template, run_id=args.run_id, config_path=args.config)
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".yaml") as handle:
                yaml.safe_dump(labels_doc, handle, allow_unicode=True, sort_keys=False)
                labels_path = handle.name
            result = run_real_run_evaluation(args.report, labels_path=labels_path, output_root=args.output_root)
            lark_sync: Dict[str, Any] = {}
            if args.sync_badcases:
                lark_sync["badcases"] = _manual_badcase_sync_skipped()
            if args.sync_report:
                report_markdown = Path(result["markdown_report"]).read_text(encoding="utf-8")
                lark_sync["report"] = sync_report_to_lark_doc(report_markdown, args.config)
            if lark_sync:
                result = {**result, "lark_sync": lark_sync}
        elif args.command == "sync-badcases":
            markdown = Path(args.badcases).read_text(encoding="utf-8")
            if _is_generated_badcase_report(markdown):
                raise RuntimeError(
                    "Generated bad_cases.md is already listed in real_run_eval_report.md; "
                    "write a manual analysis/handling note and sync that instead."
                )
            result = sync_badcases_to_lark_doc(markdown, args.config)
        else:
            markdown = Path(args.report).read_text(encoding="utf-8")
            result = sync_report_to_lark_doc(markdown, args.config)
    except RuntimeError as exc:
        print(format_lark_error(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
