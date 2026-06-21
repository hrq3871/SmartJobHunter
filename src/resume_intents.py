#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Persist private resume search intents without pretending they are profiles."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_RESUME_EXTENSIONS = {".pdf", ".md", ".txt"}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def resume_id(filename: str) -> str:
    """Return a readable, collision-resistant identifier for one resume file."""
    stem = Path(filename).stem.strip()
    readable = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", stem, flags=re.UNICODE).strip("-_")
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
    return f"{readable or 'resume'}-{digest}"


def resume_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_intents(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"resumes": {}, "unsupported_files": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("resumes", {})
    data.setdefault("unsupported_files", [])
    return data


def save_intents(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _new_entry(filename: str, file_path: Path) -> dict[str, Any]:
    return {
        "filename": filename,
        "resume_path": f"resumes/{filename}",
        "display_name": Path(filename).stem,
        "enabled": True,
        "keywords": [],
        "job_types": [],
        "profile_path": None,
        "profile_status": "pending_agent",
        "resume_sha256": resume_sha256(file_path),
        "updated_at": _now(),
    }


def sync_resume_directory(resume_dir: Path, intent_path: Path) -> dict[str, Any]:
    """Discover supported files and default only new records to enabled."""
    resume_dir.mkdir(parents=True, exist_ok=True)
    data = load_intents(intent_path)
    records = data["resumes"]
    existing_by_name = {
        str(entry.get("filename")): (key, entry)
        for key, entry in records.items()
        if entry.get("filename")
    }
    active_names: set[str] = set()
    unsupported: list[str] = []

    for file_path in sorted(resume_dir.iterdir(), key=lambda item: item.name.lower()):
        if not file_path.is_file() or file_path.name.startswith(".") or file_path.name == "example_resume.md":
            continue
        if file_path.suffix.lower() not in SUPPORTED_RESUME_EXTENSIONS:
            unsupported.append(file_path.name)
            continue

        filename = file_path.name
        active_names.add(filename)
        existing = existing_by_name.get(filename)
        current_hash = resume_sha256(file_path)
        if existing:
            _, entry = existing
            if entry.get("resume_sha256") != current_hash:
                entry["resume_sha256"] = current_hash
                entry["profile_path"] = None
                entry["profile_status"] = "pending_agent"
                entry["updated_at"] = _now()
            entry["resume_path"] = f"resumes/{filename}"
            continue

        records[resume_id(filename)] = _new_entry(filename, file_path)

    data["resumes"] = {
        key: entry
        for key, entry in records.items()
        if entry.get("filename") in active_names
    }
    data["unsupported_files"] = unsupported
    save_intents(intent_path, data)
    return data


def upsert_intent(
    intent_path: Path,
    *,
    resume_dir: Path,
    filename: str,
    keywords: list[str],
    job_types: list[str],
    display_name: str,
    enabled: bool = True,
) -> dict[str, Any]:
    """Save user search input only; formal profiles are created by Claude Code."""
    file_path = resume_dir / filename
    if file_path.suffix.lower() not in SUPPORTED_RESUME_EXTENSIONS:
        raise ValueError(f"unsupported resume format: {file_path.suffix.lower()}")
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    data = sync_resume_directory(resume_dir, intent_path)
    key = next(
        (
            record_id
            for record_id, entry in data["resumes"].items()
            if entry.get("filename") == filename
        ),
        resume_id(filename),
    )
    entry = data["resumes"].get(key) or _new_entry(filename, file_path)
    entry.update({
        "display_name": display_name.strip() or Path(filename).stem,
        "enabled": bool(enabled),
        "keywords": [str(item).strip() for item in keywords if str(item).strip()],
        "job_types": [str(item).strip() for item in job_types if str(item).strip()],
        "resume_sha256": resume_sha256(file_path),
        "updated_at": _now(),
    })
    entry.setdefault("profile_path", None)
    entry.setdefault("profile_status", "pending_agent")
    data["resumes"][key] = entry
    save_intents(intent_path, data)
    return entry
