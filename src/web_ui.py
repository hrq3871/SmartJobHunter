#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SmartJobHunter Web Console — local management dashboard.

Start:
    pip install -r requirements-web.txt
    python -m uvicorn src.web_ui:app --reload --port 8080
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
PROFILES_DIR = ROOT / "profiles"
RESUMES_DIR = ROOT / "resumes"
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"

ALLOWED_RESUME_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}
MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="SmartJobHunter Console", version="0.1.0")


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse(TEMPLATES / "index.html")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _parse_profile_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a profile Markdown file."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def _write_profile_frontmatter(path: Path, fm: dict) -> None:
    """Write updated YAML frontmatter back, preserving body."""
    text = path.read_text(encoding="utf-8")
    body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)
    new_fm = yaml.safe_dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")


def _replace_company_yaml_block(company_id: str, updates: dict) -> None:
    """Update enabled / urls / note fields for one company in companies.yaml."""
    path = CONFIG_DIR / "companies.yaml"
    text = path.read_text(encoding="utf-8")
    config = _read_yaml(path)
    companies = config.get("companies", [])
    for i, c in enumerate(companies):
        if c.get("id") == company_id:
            target = dict(c)
            for key in ("enabled", "note"):
                if key in updates:
                    target[key] = updates[key]
            if "urls" in updates and isinstance(updates["urls"], dict):
                target.setdefault("urls", {})
                for k, v in updates["urls"].items():
                    if k in ("social", "campus", "internship"):
                        target["urls"][k] = v
            companies[i] = target
            break
    else:
        raise HTTPException(status_code=404, detail=f"Company not found: {company_id}")
    config["companies"] = companies
    _write_yaml(path, config)


# ---------------------------------------------------------------------------
# Companies API
# ---------------------------------------------------------------------------

@app.get("/api/companies")
async def list_companies():
    """Return all companies with status info."""
    config = _read_yaml(CONFIG_DIR / "companies.yaml")
    result = []
    for raw in config.get("companies", []):
        urls = raw.get("urls", {})
        strategy = raw.get("strategy", {})
        result.append({
            "id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "enabled": bool(raw.get("enabled", False)),
            "urls": {k: v for k, v in urls.items() if v},
            "strategy_type": strategy.get("type", "unknown"),
            "strategy_status": strategy.get("status", "unknown"),
            "note": raw.get("note", ""),
        })
    return result


@app.put("/api/companies/{company_id}")
async def update_company(company_id: str, body: dict):
    """Update company enabled / urls / note. Does NOT touch api or strategy fields."""
    allowed = {}
    if "enabled" in body:
        allowed["enabled"] = bool(body["enabled"])
    if "urls" in body and isinstance(body["urls"], dict):
        allowed["urls"] = body["urls"]
    if "note" in body:
        allowed["note"] = str(body["note"])
    if not allowed:
        raise HTTPException(status_code=400, detail="No updatable fields provided")
    _replace_company_yaml_block(company_id, allowed)
    return {"ok": True}


@app.post("/api/companies/{company_id}/test")
async def test_company(company_id: str, body: dict):
    """Run a quick test crawl for a company."""
    from src.crawler_factory import crawl_company

    keyword = str(body.get("keyword", "") or "").strip() or "产品经理"
    job_type = str(body.get("job_type", "") or "").strip() or "social"
    try:
        jobs = crawl_company(company_id, keyword=keyword, max_jobs=5, job_type=job_type, headless=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "jobs_count": 0, "sample_titles": []}
    return {
        "ok": len(jobs) > 0,
        "jobs_count": len(jobs),
        "sample_titles": [j.get("title", "")[:60] for j in jobs[:5]],
    }


# ---------------------------------------------------------------------------
# Resumes API
# ---------------------------------------------------------------------------

@app.get("/api/resumes")
async def list_resumes():
    """List all files in resumes/ directory."""
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(RESUMES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            st = f.stat()
            files.append({
                "name": f.name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "format": f.suffix.lstrip(".").lower(),
            })
    return files


@app.post("/api/resumes")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")
    content = await file.read()
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESUMES_DIR / file.filename
    dest.write_bytes(content)
    # Check which profiles reference this file
    referenced_by = []
    for pf in PROFILES_DIR.glob("*.md"):
        fm = _parse_profile_frontmatter(pf)
        resume_path = fm.get("resume", "")
        if file.filename in resume_path:
            referenced_by.append(pf.stem)
    return {"ok": True, "filename": file.filename, "size": len(content), "referenced_by": referenced_by}


@app.delete("/api/resumes/{filename}")
async def delete_resume(filename: str):
    """Delete a resume file, returning warning if still referenced."""
    path = RESUMES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Scan profiles for references
    warnings = []
    for pf in PROFILES_DIR.glob("*.md"):
        fm = _parse_profile_frontmatter(pf)
        resume_path = fm.get("resume", "")
        if filename in resume_path:
            warnings.append(f"Still referenced by profile '{pf.stem}'")
    path.unlink()
    return {"ok": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    """Return agent config + profile list."""
    # Agent config
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"
    cfg = _read_yaml(agent_path) if agent_path.exists() else _read_yaml(sample_path)

    # Security: mask secrets
    feishu = cfg.get("feishu", {})
    safe_feishu = {
        "enabled": bool(feishu.get("enabled", False)),
        "has_credentials": bool(feishu.get("app_id") and feishu.get("app_secret")),
        "has_wiki": bool(feishu.get("wiki_node_token")),
        "has_bitable": bool(feishu.get("bitable_token") and feishu.get("bitable_table_id")),
    }

    # Profiles
    profiles = []
    for pf in sorted(PROFILES_DIR.glob("*.md")):
        fm = _parse_profile_frontmatter(pf)
        profiles.append({
            "name": fm.get("name", pf.stem),
            "filename": pf.name,
            "enabled": fm.get("enabled", False) is not False,
            "job_type": fm.get("job_type", ""),
            "keywords": fm.get("keywords", []),
            "resume": fm.get("resume", ""),
        })

    return {
        "decision_level": cfg.get("decision_level", "moderate"),
        "time_filter_days": cfg.get("time_filter_days", 3),
        "threshold_score": cfg.get("threshold_score", 70),
        "jd_truncate_length": cfg.get("jd_truncate_length", 6000),
        "output": cfg.get("output", {}),
        "feishu": safe_feishu,
        "profiles": profiles,
    }


@app.put("/api/config")
async def update_config(body: dict):
    """Update agent.yaml (feishu toggle) and/or profile enabled states."""
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"

    # Ensure agent.yaml exists
    if not agent_path.exists():
        if sample_path.exists():
            shutil.copy(sample_path, agent_path)
        else:
            agent_path.write_text("", encoding="utf-8")
    cfg = _read_yaml(agent_path)

    # Update feishu
    feishu_updates = body.get("feishu", {})
    if feishu_updates:
        cfg.setdefault("feishu", {})
        if "enabled" in feishu_updates:
            cfg["feishu"]["enabled"] = bool(feishu_updates["enabled"])
    _write_yaml(agent_path, cfg)

    # Update profile enabled states
    profile_updates = body.get("profiles", [])
    for pu in profile_updates:
        name = pu.get("name", "")
        enabled = pu.get("enabled")
        if not name or enabled is None:
            continue
        pf_path = PROFILES_DIR / f"{name}.md"
        if pf_path.exists():
            fm = _parse_profile_frontmatter(pf_path)
            fm["enabled"] = bool(enabled)
            _write_profile_frontmatter(pf_path, fm)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Reports API
# ---------------------------------------------------------------------------

def _extract_report_meta(path: Path) -> Optional[dict]:
    """Parse a report file to extract Basic Info fields."""
    try:
        text = path.read_text(encoding="utf-8")[:3000]
    except Exception:
        return None
    profile = ""
    job_count = 0
    top_score = 0
    job_type = ""
    generated = ""

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- **Profile**:"):
            profile = line.split(":", 1)[-1].strip()
        elif line.startswith("- **Job Type**:"):
            job_type = line.split(":", 1)[-1].strip()
        elif line.startswith("- **Generated**:"):
            generated = line.split(":", 1)[-1].strip()
        elif line.startswith("- **Jobs Found**:"):
            try:
                job_count = int(line.split(":", 1)[-1].strip())
            except ValueError:
                pass
    # Extract top score
    for m in re.finditer(r"Score:\s*(\d+)", text):
        try:
            score = int(m.group(1))
            if score > top_score:
                top_score = score
        except ValueError:
            pass

    return {
        "filename": path.name,
        "relpath": str(path.relative_to(OUTPUT_DIR)).replace("\\", "/"),
        "profile": profile,
        "job_type": job_type,
        "generated": generated,
        "job_count": job_count,
        "top_score": top_score,
        "size": path.stat().st_size,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
    }


@app.get("/api/reports")
async def list_reports():
    """Scan output/ for reports, excluding evals and application_packages."""
    if not OUTPUT_DIR.exists():
        return []
    reports = []
    for f in sorted(OUTPUT_DIR.rglob("*.md"), reverse=True):
        if "evals" in f.parts or "application_packages" in f.parts:
            continue
        if f.name == "example_report.md":
            continue
        meta = _extract_report_meta(f)
        if meta:
            reports.append(meta)
    return reports


@app.get("/api/reports/{filename:path}")
async def get_report(filename: str):
    """Return a full Markdown report."""
    # Security: only allow relative paths within output/
    safe_path = (OUTPUT_DIR / filename).resolve()
    if not str(safe_path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return PlainTextResponse(safe_path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Health API
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_overview():
    """Aggregate strategy task status from logs/strategy_tasks/."""
    task_root = LOGS_DIR / "strategy_tasks"
    if not task_root.exists():
        return {"summary": {"total": 0, "pending": 0, "blocked": 0, "failed": 0, "repaired": 0}, "tasks": []}

    latest: Dict[str, dict] = {}
    for company_dir in sorted(task_root.iterdir()):
        if not company_dir.is_dir():
            continue
        cid = company_dir.name
        for ts_dir in sorted(company_dir.iterdir(), reverse=True):
            task_file = ts_dir / "task.json"
            if not task_file.exists():
                continue
            try:
                data = json.loads(task_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            entry = {
                "company_id": (data.get("company") or {}).get("id", cid),
                "company_name": (data.get("company") or {}).get("name", cid),
                "status": data.get("status", "pending"),
                "reason": (data.get("decision") or {}).get("reason", ""),
                "created_at": data.get("created_at", ""),
                "evidence_dir": data.get("evidence_dir"),
            }
            if cid not in latest or entry["created_at"] > latest[cid].get("created_at", ""):
                latest[cid] = entry
            break  # only need latest timestamp per company

    tasks = sorted(latest.values(), key=lambda t: t["created_at"], reverse=True)
    summary = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t["status"] == "pending"),
        "blocked": sum(1 for t in tasks if t["status"] == "blocked"),
        "failed": sum(1 for t in tasks if t["status"] in ("failed", "verification_failed")),
        "repaired": sum(1 for t in tasks if t["status"] == "repaired"),
    }
    return {"summary": summary, "tasks": tasks}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web_ui:app", host="0.0.0.0", port=8080, reload=True)
