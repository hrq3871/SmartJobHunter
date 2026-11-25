#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from src.resume_intents import SUPPORTED_RESUME_EXTENSIONS
from src.web_ui import ALLOWED_RESUME_EXTENSIONS


def test_web_upload_uses_shared_pdf_markdown_text_policy():
    assert ALLOWED_RESUME_EXTENSIONS is SUPPORTED_RESUME_EXTENSIONS


def test_frontend_exposes_only_pdf_markdown_and_text():
    html = Path("templates/index.html").read_text(encoding="utf-8")

    assert 'accept=".pdf,.md,.txt"' in html
    assert "拖拽或点击 · .pdf .md .txt" in html
    assert "docx-preview" not in html.lower()
    assert "jszip" not in html.lower()
    assert "ext==='docx'" not in html
    assert "['png','jpg','jpeg'" not in html


def test_frontend_uses_search_intent_and_platform_neutral_launch_states():
    html = Path("templates/index.html").read_text(encoding="utf-8")

    assert "resumePayload.resumes" in html
    assert "resume_id" in html
    assert "/intent" in html
    assert "待补充关键词" in html
    assert "待 Agent 建档" in html
    assert "任务已启动" in html
    assert "Claude Code" not in html
    assert 'data-tab="health"' in html
    assert "查找岗位" in html


def test_web_module_main_stays_local_only():
    source = Path("src/web_ui.py").read_text(encoding="utf-8")

    assert 'host="127.0.0.1"' in source
    assert 'host="0.0.0.0"' not in source
