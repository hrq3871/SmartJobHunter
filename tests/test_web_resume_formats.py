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
