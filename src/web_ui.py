#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SmartJobHunter Web Console — local management dashboard.

Start:
    pip install -r requirements-web.txt
    python -m uvicorn src.web_ui:app --reload --port 8080
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
PROFILES_DIR = ROOT / "profiles"
RESUMES_DIR = ROOT / "resumes"
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"

ALLOWED_RESUME_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}
MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="SmartJobHunter Console", version="0.2.0")


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


def _read_companies_config() -> dict:
    return _read_yaml(CONFIG_DIR / "companies.yaml")


def _write_companies_config(config: dict) -> None:
    _write_yaml(CONFIG_DIR / "companies.yaml", config)


# ---------------------------------------------------------------------------
# Bilingual reason labels
# ---------------------------------------------------------------------------

REASON_LABELS: Dict[str, str] = {
    "unknown_strategy":        "未知策略 / Unknown strategy",
    "missing_config_crawler":  "缺少爬虫配置 / Missing crawler config",
    "network_or_link_error":   "网络或链接错误 / Network or link error",
    "zero_jobs_returned":      "返回空岗位 / Zero jobs returned",
    "missing_strategy_fingerprint": "缺少策略指纹 / Missing fingerprint",
    "fingerprint_changed":     "页面指纹变更 / Page fingerprint changed",
    "needs_review_strategy":   "策略待复核 / Strategy needs review",
    "failed_strategy":         "策略失败 / Strategy failed",
    "login_required":          "需要登录 / Login required",
    "captcha":                 "验证码拦截 / Captcha detected",
    "anti_crawl":              "反爬拦截 / Anti-crawl detected",
    "blocked":                 "已被拦截 / Blocked",
    "company_not_found":       "公司配置缺失 / Company not found",
    "no_company_link_configured": "未配置公司链接 / No link configured",
    "config_error":            "配置错误 / Config error",
    "api_changed":             "API已变更 / API changed",
    "url_invalid":             "链接失效 / URL invalid",
    "network_error":           "网络错误 / Network error",
    "unknown":                 "未知原因 / Unknown",
}


def _bilingual(reason: str) -> str:
    """Return CN+EN label for a strategy reason code."""
    for key, label in REASON_LABELS.items():
        if key in reason.lower().replace(" ", "_"):
            return label
    return reason if reason else "未指定 / Unspecified"


# ---------------------------------------------------------------------------
# Companies API (full CRUD)
# ---------------------------------------------------------------------------

@app.get("/api/companies")
async def list_companies():
    config = _read_companies_config()
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
    """Update company fields: enabled, urls (social/campus/internship), note, name."""
    config = _read_companies_config()
    companies = config.get("companies", [])
    found = False
    for c in companies:
        if c.get("id") == company_id:
            found = True
            if "name" in body:
                c["name"] = str(body["name"])
            if "enabled" in body:
                c["enabled"] = bool(body["enabled"])
            if "note" in body:
                c["note"] = str(body["note"])
            if "urls" in body and isinstance(body["urls"], dict):
                c.setdefault("urls", {})
                for k in ("social", "campus", "internship"):
                    if k in body["urls"]:
                        c["urls"][k] = body["urls"][k]
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Company not found: {company_id}")
    _write_companies_config(config)
    return {"ok": True}


@app.post("/api/companies")
async def create_company(body: dict):
    """Add a new company entry."""
    company_id = str(body.get("id", "")).strip()
    company_name = str(body.get("name", "")).strip()
    if not company_id or not company_name:
        raise HTTPException(status_code=400, detail="id and name are required")
    config = _read_companies_config()
    companies = config.get("companies", [])
    for c in companies:
        if c.get("id") == company_id:
            raise HTTPException(status_code=409, detail=f"Company already exists: {company_id}")
    new_entry = {
        "id": company_id,
        "name": company_name,
        "enabled": bool(body.get("enabled", False)),
        "urls": {},
        "note": str(body.get("note", "")),
    }
    for k in ("social", "campus", "internship"):
        if body.get("urls", {}).get(k):
            new_entry["urls"][k] = body["urls"][k]
    strategy_type = str(body.get("strategy_type", "")).strip()
    if strategy_type in ("config_intercept", "config_dom", "custom_python", "legacy_python", "browser_operation", "unsupported"):
        new_entry["strategy"] = {"type": strategy_type, "status": "unknown", "owner": "agent"}
        if strategy_type == "custom_python" and body.get("strategy_module"):
            new_entry["strategy"]["module"] = body["strategy_module"]
    companies.append(new_entry)
    _write_companies_config(config)
    return {"ok": True, "id": company_id}


@app.delete("/api/companies/{company_id}")
async def delete_company(company_id: str):
    """Remove a company from the config."""
    config = _read_companies_config()
    companies = config.get("companies", [])
    before = len(companies)
    config["companies"] = [c for c in companies if c.get("id") != company_id]
    if len(config["companies"]) == before:
        raise HTTPException(status_code=404, detail=f"Company not found: {company_id}")
    _write_companies_config(config)
    return {"ok": True}


@app.post("/api/companies/{company_id}/test")
async def test_company(company_id: str, body: dict):
    from src.crawler_factory import crawl_company

    keyword = str(body.get("keyword", "") or "").strip() or "产品经理"
    job_type = str(body.get("job_type", "") or "").strip() or "social"
    try:
        jobs = await asyncio.to_thread(
            crawl_company, company_id, keyword=keyword, max_jobs=5, job_type=job_type, headless=True
        )
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
    referenced_by = []
    for pf in PROFILES_DIR.glob("*.md"):
        fm = _parse_profile_frontmatter(pf)
        rp = fm.get("resume", "")
        if file.filename in rp:
            referenced_by.append(pf.stem)
    return {"ok": True, "filename": file.filename, "size": len(content), "referenced_by": referenced_by}


@app.delete("/api/resumes/{filename}")
async def delete_resume(filename: str):
    path = RESUMES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    warnings = []
    for pf in PROFILES_DIR.glob("*.md"):
        fm = _parse_profile_frontmatter(pf)
        rp = fm.get("resume", "")
        if filename in rp:
            warnings.append(f"Still referenced by profile '{pf.stem}'")
    path.unlink()
    return {"ok": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# Profiles API
# ---------------------------------------------------------------------------

@app.get("/api/profiles/{name}/resume")
async def get_profile_resume(name: str):
    """Return the resume file content associated with a profile."""
    pf_path = PROFILES_DIR / f"{name}.md"
    if not pf_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")
    fm = _parse_profile_frontmatter(pf_path)
    resume_path = fm.get("resume", "")
    if not resume_path:
        raise HTTPException(status_code=404, detail="No resume associated with this profile")
    # Resolve relative path
    resolved = (PROFILES_DIR / resume_path).resolve()
    if not resolved.exists():
        # Try from project root
        resolved = (ROOT / resume_path).resolve()
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Resume file not found: {resume_path}")
    content = resolved.read_text(encoding="utf-8")
    return {
        "filename": resolved.name,
        "content": content,
        "format": resolved.suffix.lstrip(".").lower(),
    }


# ---------------------------------------------------------------------------
# Config API (with full Feishu credential editing)
# ---------------------------------------------------------------------------

FEISHU_FIELDS = ["app_id", "app_secret", "wiki_node_token", "bitable_token", "bitable_table_id"]


@app.get("/api/config")
async def get_config():
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"
    cfg = _read_yaml(agent_path) if agent_path.exists() else _read_yaml(sample_path)

    feishu_cfg = cfg.get("feishu", {})
    # Return actual values so they can be edited inline (local-only, not exposed to internet)
    feishu = {
        "enabled": bool(feishu_cfg.get("enabled", False)),
    }
    for f in FEISHU_FIELDS:
        feishu[f] = feishu_cfg.get(f, "")

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
        "feishu": feishu,
        "profiles": profiles,
    }


@app.put("/api/config")
async def update_config(body: dict):
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"
    if not agent_path.exists():
        if sample_path.exists():
            shutil.copy(sample_path, agent_path)
        else:
            agent_path.write_text("", encoding="utf-8")
    cfg = _read_yaml(agent_path)

    # Update feishu credentials
    feishu_updates = body.get("feishu", {})
    if feishu_updates:
        cfg.setdefault("feishu", {})
        if "enabled" in feishu_updates:
            cfg["feishu"]["enabled"] = bool(feishu_updates["enabled"])
        for f in FEISHU_FIELDS:
            if f in feishu_updates:
                cfg["feishu"][f] = str(feishu_updates[f])

    # Update top-level config fields
    for field in ("decision_level", "threshold_score", "time_filter_days"):
        if field in body:
            cfg[field] = type(cfg.get(field, ""))(body[field])

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
    safe_path = (OUTPUT_DIR / filename).resolve()
    if not str(safe_path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return PlainTextResponse(safe_path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Health API (with batch repair)
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_overview():
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
            raw_reason = (data.get("decision") or {}).get("reason", "")
            entry = {
                "company_id": (data.get("company") or {}).get("id", cid),
                "company_name": (data.get("company") or {}).get("name", cid),
                "status": data.get("status", "pending"),
                "reason": raw_reason,
                "reason_label": _bilingual(raw_reason),
                "created_at": data.get("created_at", ""),
                "evidence_dir": data.get("evidence_dir"),
                "task_path": str(task_file.relative_to(LOGS_DIR)),
            }
            if cid not in latest or entry["created_at"] > latest[cid].get("created_at", ""):
                latest[cid] = entry
            break

    tasks = sorted(latest.values(), key=lambda t: t["created_at"], reverse=True)
    summary = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t["status"] == "pending"),
        "blocked": sum(1 for t in tasks if t["status"] == "blocked"),
        "failed": sum(1 for t in tasks if t["status"] in ("failed", "verification_failed")),
        "repaired": sum(1 for t in tasks if t["status"] == "repaired"),
    }
    return {"summary": summary, "tasks": tasks}


@app.delete("/api/health/{company_id}")
async def clear_health_entry(company_id: str):
    """Remove all strategy tasks for a company (e.g., after a successful retry)."""
    task_dir = LOGS_DIR / "strategy_tasks" / company_id
    if task_dir.exists():
        shutil.rmtree(task_dir)
        return {"ok": True, "message": f"Cleared health tasks for {company_id}"}
    return {"ok": True, "message": f"No tasks found for {company_id}"}


@app.post("/api/health/repair")
async def trigger_health_repair(body: dict):
    """Batch trigger health inspection for selected companies (or all)."""
    company_ids = body.get("company_ids", [])
    keyword = str(body.get("keyword", "产品经理"))
    job_type = str(body.get("job_type", "social"))

    def _run():
        from src.health_monitor import HealthMonitor
        monitor = HealthMonitor()
        if company_ids:
            import json as _json
            results = []
            for cid in company_ids:
                try:
                    r = monitor.inspect_company_strategy(cid, keyword=keyword, job_type=job_type, headless=True)
                    results.append({"company_id": cid, "status": "ok", "result": r})
                except Exception as exc:
                    results.append({"company_id": cid, "status": "error", "error": str(exc)})
            print(_json.dumps(results, ensure_ascii=False, indent=2))
        else:
            summary = monitor.inspect_all_strategies(keyword=keyword, job_type=job_type, headless=True)
            print(_json.dumps(summary, ensure_ascii=False, indent=2))
        print("[HealthRepair] Batch inspection complete")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "message": f"Started batch repair for {len(company_ids) if company_ids else 'all'} companies in background"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web_ui:app", host="0.0.0.0", port=8080, reload=True)
