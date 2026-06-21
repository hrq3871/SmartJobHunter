#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path


INSPECTOR_PATH = Path(".claude/agents/crawler-strategy-inspector.md")


def test_inspector_requires_fixed_chinese_summary_template():
    content = INSPECTOR_PATH.read_text(encoding="utf-8")

    required_labels = [
        "# 招聘站巡检结果",
        "## 本次概况",
        "巡检批次",
        "关键词",
        "岗位类型",
        "公司总数",
        "已验证",
        "已修复",
        "阻塞",
        "失败",
        "总耗时",
        "## 公司明细",
        "原始链接",
        "岗位数",
        "有效岗位率",
        "URL 有效率",
        "验证结果",
        "证据目录",
        "Fingerprint",
        "已尝试动作",
        "后续需要",
    ]

    for label in required_labels:
        assert label in content


def test_inspector_chinese_summary_forbids_missing_or_invented_values():
    content = INSPECTOR_PATH.read_text(encoding="utf-8")

    assert "未获得" in content
    assert "禁止留空" in content
    assert "禁止猜测或伪造" in content
    assert "已验证（verified_existing）" in content
    assert "已修复（repaired）" in content
    assert "阻塞（blocked）" in content
    assert "失败（failed）" in content
