#!/usr/bin/env python
# -*- coding: utf-8 -*-

from src.resume_intents import SUPPORTED_RESUME_EXTENSIONS
from src.resume_parser import list_resumes, parse_resume


def test_resume_parser_supports_only_pdf_markdown_and_text(tmp_path):
    assert SUPPORTED_RESUME_EXTENSIONS == {".pdf", ".md", ".txt"}
    (tmp_path / "resume.md").write_text("产品经历", encoding="utf-8")
    (tmp_path / "resume.txt").write_text("开发经历", encoding="utf-8")
    (tmp_path / "resume.pdf").write_bytes(b"not parsed by listing")
    for filename in ("resume.docx", "resume.png", "resume.jpg", "resume.jpeg"):
        (tmp_path / filename).write_bytes(b"unsupported")

    listed = list_resumes(str(tmp_path))

    assert {item["format"] for item in listed} == {".pdf", ".md", ".txt"}


def test_resume_parser_rejects_docx_and_images_with_clear_error(tmp_path):
    for filename in ("resume.docx", "resume.png", "resume.jpg", "resume.jpeg"):
        path = tmp_path / filename
        path.write_bytes(b"unsupported")

        result = parse_resume(str(path))

        assert result["content"].startswith("[错误] 不支持的文件格式")
        assert result["hash"] is None
