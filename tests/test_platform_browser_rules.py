#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path


def test_web_access_is_claude_code_only_and_install_command_is_documented():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    claude = Path("CLAUDE.md").read_text(encoding="utf-8")
    inspector = Path(".claude/agents/crawler-strategy-inspector.md").read_text(encoding="utf-8")
    readme = Path("README_CN.md").read_text(encoding="utf-8")

    assert agents == claude
    for content in (agents, inspector, readme):
        assert "web-access 仅限 Claude Code" in content
        assert "npx skills add eze-is/web-access" in content
        assert "Codex 不加载" in content


def test_codex_browser_path_does_not_depend_on_web_access():
    inspector = Path(".claude/agents/crawler-strategy-inspector.md").read_text(encoding="utf-8")

    assert "Codex 内置 Browser" in inspector
    assert "用户明确授权" in inspector
