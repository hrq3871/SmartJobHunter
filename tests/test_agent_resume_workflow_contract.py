#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_agent_instructions_distinguish_search_intent_from_formal_profile():
    claude = _read("CLAUDE.md")
    agents = _read("AGENTS.md")
    profile_skill = _read(".claude/skills/jobhunter/profile.md")
    profile_prompt = _read(".claude/skills/jobhunter/prompts/build_candidate_profile.md")

    assert claude == agents
    for content in (claude, profile_skill, profile_prompt):
        assert "search_intent" in content
        assert "profiles/<profile_id>.md" in content
        assert "简历证据" in content
    assert "上传简历时不得创建正式 profile" in claude


def test_agent_instructions_define_visible_claude_launch_and_format_policy():
    active_docs = [
        _read("CLAUDE.md"),
        _read("README_CN.md"),
        _read("docs/smartjobhunter-agent-design.md"),
    ]

    for content in active_docs:
        assert "--permission-mode auto" in content
        assert "PDF、Markdown、TXT" in content
        assert "DOCX" in content and "不支持" in content


def test_project_profile_skill_no_longer_routes_images_to_agent_vision():
    profile_skill = _read(".claude/skills/jobhunter/profile.md")

    assert "图片" not in profile_skill
    assert "视觉能力" not in profile_skill
