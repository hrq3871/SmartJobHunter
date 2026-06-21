#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Isolated Web console workflow tests; never mutate the real repository data."""

from __future__ import annotations

import asyncio
import io

import pytest
import yaml
from fastapi import HTTPException, UploadFile

from src import web_ui
from src.claude_launcher import ClaudeLaunchError
from src.resume_intents import sync_resume_directory, upsert_intent


@pytest.fixture
def isolated_web(tmp_path, monkeypatch):
    paths = {
        "ROOT": tmp_path,
        "RESUMES_DIR": tmp_path / "resumes",
        "PROFILES_DIR": tmp_path / "profiles",
        "CONFIG_DIR": tmp_path / "config",
        "OUTPUT_DIR": tmp_path / "output",
        "LOGS_DIR": tmp_path / "logs",
    }
    for path in paths.values():
        if path is not tmp_path:
            path.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        monkeypatch.setattr(web_ui, name, path)
    web_ui.app.state._pending_upload = {}
    return paths


def _upload(filename: str, content: bytes = b"resume") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


def test_resume_upload_rejects_docx_and_images(isolated_web):
    for filename in ("resume.docx", "resume.png", "resume.jpg", "resume.jpeg"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(web_ui.analyze_resume(_upload(filename)))
        assert exc.value.status_code == 400
        assert "Unsupported format" in str(exc.value.detail)


def test_confirm_resume_saves_intent_without_creating_profile(isolated_web):
    asyncio.run(web_ui.analyze_resume(_upload("candidate.pdf", b"pdf bytes")))

    result = asyncio.run(web_ui.confirm_resume({
        "filename": "candidate.pdf",
        "keywords": ["AI 产品经理", "ToB"],
        "job_types": ["校招", "实习"],
        "display_name": "AI 产品",
    }))

    assert result["profile_status"] == "pending_agent"
    assert (isolated_web["RESUMES_DIR"] / "candidate.pdf").exists()
    assert (isolated_web["CONFIG_DIR"] / "resume_intents.yaml").exists()
    assert not isolated_web["PROFILES_DIR"].exists() or not list(isolated_web["PROFILES_DIR"].glob("*.md"))


def test_list_resumes_auto_enables_manual_supported_file(isolated_web):
    (isolated_web["RESUMES_DIR"] / "manual.md").write_text("开发经历", encoding="utf-8")

    result = asyncio.run(web_ui.list_resumes())

    manual = next(item for item in result["resumes"] if item["filename"] == "manual.md")
    assert manual["enabled"] is True
    assert manual["profile_status"] == "pending_agent"
    assert manual["keywords"] == []


def test_manual_resume_intent_can_be_completed_without_uploading_again(isolated_web):
    (isolated_web["RESUMES_DIR"] / "manual.md").write_text("开发经历", encoding="utf-8")
    asyncio.run(web_ui.list_resumes())

    result = asyncio.run(web_ui.update_resume_intent("manual.md", {
        "keywords": ["后端工程师", "Python"],
        "job_types": ["社招"],
        "display_name": "后端方向",
        "enabled": True,
    }))

    assert result["keywords"] == ["后端工程师", "Python"]
    assert result["job_types"] == ["社招"]
    assert result["display_name"] == "后端方向"


def test_run_inspection_launches_claude_after_profile_generation_prompt(isolated_web, monkeypatch):
    resume = isolated_web["RESUMES_DIR"] / "candidate.pdf"
    resume.write_bytes(b"pdf")
    intent_path = isolated_web["CONFIG_DIR"] / "resume_intents.yaml"
    sync_resume_directory(isolated_web["RESUMES_DIR"], intent_path)
    entry = upsert_intent(
        intent_path,
        resume_dir=isolated_web["RESUMES_DIR"],
        filename="candidate.pdf",
        keywords=["AI 产品经理"],
        job_types=["校招"],
        display_name="AI 产品",
    )
    data = yaml.safe_load(intent_path.read_text(encoding="utf-8"))
    resume_id = next(iter(data["resumes"]))
    calls = []

    def fake_launch(**kwargs):
        calls.append(kwargs)
        return {"run_id": kwargs["run_dir"].name, "status": "launched", "pid": 1234}

    monkeypatch.setattr(web_ui, "launch_claude", fake_launch, raising=False)

    result = asyncio.run(web_ui.run_inspection({"resume_id": resume_id}))

    assert result["status"] == "launched"
    assert result["pid"] == 1234
    assert "生成或更新正式 profile" in calls[0]["prompt"]
    assert calls[0]["agent"] is None
    assert entry["filename"] in calls[0]["prompt"]


def test_run_inspection_rejects_missing_keywords(isolated_web):
    resume = isolated_web["RESUMES_DIR"] / "manual.txt"
    resume.write_text("resume", encoding="utf-8")
    data = sync_resume_directory(
        isolated_web["RESUMES_DIR"],
        isolated_web["CONFIG_DIR"] / "resume_intents.yaml",
    )
    resume_id = next(iter(data["resumes"]))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_ui.run_inspection({"resume_id": resume_id}))

    assert exc.value.status_code == 400
    assert "关键词" in str(exc.value.detail)


def test_health_repair_launches_one_agent_with_exact_selected_companies(isolated_web, monkeypatch):
    companies = {
        "companies": [
            {
                "id": "ruijie_campus",
                "name": "锐捷",
                "urls": {"campus": "https://example.com/ruijie/jobs?type=campus"},
            },
            {
                "id": "yonyou_campus",
                "name": "用友",
                "urls": {"campus": "https://example.com/yonyou/jobs?type=campus"},
            },
        ]
    }
    (isolated_web["CONFIG_DIR"] / "companies.yaml").write_text(
        yaml.safe_dump(companies, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    calls = []

    def fake_launch(**kwargs):
        calls.append(kwargs)
        return {"run_id": kwargs["run_dir"].name, "status": "launched", "pid": 5678}

    monkeypatch.setattr(web_ui, "launch_claude", fake_launch, raising=False)

    result = asyncio.run(web_ui.trigger_health_repair({
        "company_ids": ["ruijie_campus", "yonyou_campus"],
        "keyword": "产品经理",
        "job_type": "campus",
    }))

    assert result["status"] == "launched"
    assert len(calls) == 1
    assert calls[0]["agent"] == "crawler-strategy-inspector"
    assert "https://example.com/ruijie/jobs?type=campus" in calls[0]["prompt"]
    assert "https://example.com/yonyou/jobs?type=campus" in calls[0]["prompt"]


def test_launch_failure_is_returned_instead_of_fake_success(isolated_web, monkeypatch):
    resume = isolated_web["RESUMES_DIR"] / "candidate.md"
    resume.write_text("resume", encoding="utf-8")
    intent_path = isolated_web["CONFIG_DIR"] / "resume_intents.yaml"
    sync_resume_directory(isolated_web["RESUMES_DIR"], intent_path)
    upsert_intent(
        intent_path,
        resume_dir=isolated_web["RESUMES_DIR"],
        filename="candidate.md",
        keywords=["后端工程师"],
        job_types=["社招"],
        display_name="后端",
    )
    data = yaml.safe_load(intent_path.read_text(encoding="utf-8"))
    resume_id = next(iter(data["resumes"]))
    monkeypatch.setattr(
        web_ui,
        "launch_claude",
        lambda **kwargs: (_ for _ in ()).throw(ClaudeLaunchError("cannot launch")),
        raising=False,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_ui.run_inspection({"resume_id": resume_id}))

    assert exc.value.status_code == 500
    assert "cannot launch" in str(exc.value.detail)
