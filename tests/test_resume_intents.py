#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from src.resume_intents import (
    SUPPORTED_RESUME_EXTENSIONS,
    sync_resume_directory,
    upsert_intent,
)


def _entry_for(data: dict, filename: str) -> dict:
    return next(
        item
        for item in data["resumes"].values()
        if item["filename"] == filename
    )


def test_sync_new_supported_files_defaults_enabled(tmp_path):
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "产品.pdf").write_bytes(b"pdf")
    (resume_dir / "developer.md").write_text("backend", encoding="utf-8")
    (resume_dir / "notes.txt").write_text("data", encoding="utf-8")
    intent_path = tmp_path / "config" / "resume_intents.yaml"

    data = sync_resume_directory(resume_dir, intent_path)

    assert SUPPORTED_RESUME_EXTENSIONS == {".pdf", ".md", ".txt"}
    assert {entry["filename"] for entry in data["resumes"].values()} == {
        "产品.pdf",
        "developer.md",
        "notes.txt",
    }
    for entry in data["resumes"].values():
        assert entry["enabled"] is True
        assert entry["keywords"] == []
        assert entry["profile_status"] == "pending_agent"
        assert entry["resume_sha256"]


def test_sync_preserves_existing_disabled_state(tmp_path):
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "candidate.pdf").write_bytes(b"pdf")
    intent_path = tmp_path / "config" / "resume_intents.yaml"
    initial = sync_resume_directory(resume_dir, intent_path)
    entry = _entry_for(initial, "candidate.pdf")
    entry["enabled"] = False
    entry["keywords"] = ["数据分析"]
    intent_path.write_text(
        yaml.safe_dump(initial, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    updated = sync_resume_directory(resume_dir, intent_path)

    preserved = _entry_for(updated, "candidate.pdf")
    assert preserved["enabled"] is False
    assert preserved["keywords"] == ["数据分析"]


def test_sync_rejects_docx_and_images(tmp_path):
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    for filename in ("old.docx", "photo.png", "photo.jpg", "photo.jpeg"):
        (resume_dir / filename).write_bytes(b"unsupported")
    intent_path = tmp_path / "config" / "resume_intents.yaml"

    data = sync_resume_directory(resume_dir, intent_path)

    assert data["resumes"] == {}
    assert sorted(data["unsupported_files"]) == [
        "old.docx",
        "photo.jpeg",
        "photo.jpg",
        "photo.png",
    ]


def test_save_intent_does_not_create_profile(tmp_path):
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "candidate.pdf").write_bytes(b"pdf")
    intent_path = tmp_path / "config" / "resume_intents.yaml"
    profiles_dir = tmp_path / "profiles"

    saved = upsert_intent(
        intent_path,
        resume_dir=resume_dir,
        filename="candidate.pdf",
        keywords=["AI 产品经理", "ToB"],
        job_types=["校招", "实习"],
        display_name="AI 产品",
    )

    assert saved["keywords"] == ["AI 产品经理", "ToB"]
    assert saved["job_types"] == ["校招", "实习"]
    assert saved["profile_status"] == "pending_agent"
    assert not profiles_dir.exists()
