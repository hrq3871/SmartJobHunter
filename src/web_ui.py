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
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .claude_launcher import (
    ClaudeLaunchError,
    build_inspection_prompt,
    build_repair_prompt,
    launch_claude,
)
from .resume_intents import (
    SUPPORTED_RESUME_EXTENSIONS,
    load_intents,
    sync_resume_directory,
    upsert_intent,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
PROFILES_DIR = ROOT / "profiles"
RESUMES_DIR = ROOT / "resumes"
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"

ALLOWED_RESUME_EXTENSIONS = SUPPORTED_RESUME_EXTENSIONS
MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB

@asynccontextmanager
async def _lifespan(_: FastAPI):
    sync_resume_directory(RESUMES_DIR, CONFIG_DIR / "resume_intents.yaml")
    yield


app = FastAPI(title="SmartJobHunter Console", version="0.2.0", lifespan=_lifespan)

# Serve resumes as static files for inline preview
if RESUMES_DIR.exists():
    app.mount("/resumes", StaticFiles(directory=str(RESUMES_DIR)), name="resumes_static")


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
            "id": str(raw.get("id", "")),
            "name": str(raw.get("name", "")),
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
    data = sync_resume_directory(RESUMES_DIR, CONFIG_DIR / "resume_intents.yaml")
    files = []
    for resume_id, entry in data["resumes"].items():
        file_path = RESUMES_DIR / entry["filename"]
        if not file_path.exists():
            continue
        st = file_path.stat()
        files.append({
            "resume_id": resume_id,
            **entry,
            "name": entry["filename"],
            "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "format": file_path.suffix.lstrip(".").lower(),
        })
    files.sort(key=lambda item: item["modified"], reverse=True)
    return {
        "resumes": files,
        "unsupported_files": data.get("unsupported_files", []),
    }


def _extract_text_from_bytes(content: bytes, filename: str) -> str:
    """Try to extract readable text from a resume file for keyword suggestion."""
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content.decode("gbk", errors="replace")
            except Exception:
                return ""
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception:
            return ""
    return ""


def _suggest_search_intent(filename: str, text_content: str) -> dict:
    """Heuristically suggest keywords and job_type from filename + content."""
    combined = (filename + " " + text_content[:2000]).lower()

    # Detect job_type
    job_type = "社招"
    if any(kw in combined for kw in ["实习", "intern", "internship"]):
        job_type = "实习"
    elif any(kw in combined for kw in ["校招", "应届", "campus", "graduate"]):
        job_type = "校招"

    # Extract role keywords from filename
    name = Path(filename).stem
    # Split by common separators
    import re as _re
    parts = _re.split(r"[-_\s]+", name)
    role_hints = []
    for p in parts:
        p_clean = p.strip().lower()
        if p_clean in ("resume", "cv", "简历", "个人简历"):
            continue
        if len(p_clean) >= 2 and not p_clean.isdigit():
            role_hints.append(p_clean)

    # Extract from text content
    text_lower = text_content.lower()
    keyword_candidates = set()
    # Common role keywords
    ROLE_PATTERNS = [
        "产品经理", "产品总监", "产品负责人", "ai产品", "tob", "toc", "saas",
        "后端", "前端", "全栈", "算法", "数据分析", "数据工程师",
        "java", "python", "golang", "rust", "c++",
        "运营", "市场", "销售", "设计", "测试", "运维",
        "项目经理", "技术经理", "架构师",
    ]
    for kw in ROLE_PATTERNS:
        if kw in combined or kw.lower() in combined:
            keyword_candidates.add(kw if kw in combined else kw.lower())

    # Add filename hints
    for h in role_hints:
        if len(h) >= 2 and not h.isdigit():
            keyword_candidates.add(h)

    return {
        "suggested_name": name,
        "suggested_job_type": job_type,
        "suggested_keywords": sorted(keyword_candidates),
        "text_preview": text_content[:500] if text_content else "",
    }


@app.post("/api/resumes/analyze")
async def analyze_resume(file: UploadFile = File(...)):
    """Upload a resume temporarily, analyze it, return keyword suggestions.
    Does NOT save the file yet — user must call /api/resumes/confirm to finalize."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")
    content = await file.read()
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    # Check for duplicate filename
    if (RESUMES_DIR / file.filename).exists():
        raise HTTPException(status_code=409, detail=f"File already exists: {file.filename}")

    # Extract text and suggest
    text = _extract_text_from_bytes(content, file.filename)
    suggestion = _suggest_search_intent(file.filename, text)

    # Store content temporarily for confirm step (simple in-memory, keyed by filename)
    app.state._pending_upload = getattr(app.state, "_pending_upload", {})
    app.state._pending_upload[file.filename] = content

    return {
        "ok": True,
        "filename": file.filename,
        "size": len(content),
        "format": ext.lstrip("."),
        **suggestion,
    }


@app.post("/api/resumes/confirm")
async def confirm_resume(body: dict):
    """Finalize upload and save search intent; Claude creates the formal profile later."""
    filename = str(body.get("filename", "")).strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename required")
    keywords = body.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.replace(",", " ").split() if k.strip()]
    job_types = body.get("job_types") or [str(body.get("job_type", "社招")).strip()]
    if isinstance(job_types, str):
        job_types = [job_types]
    display_name = (
        str(body.get("display_name", "")).strip()
        or str(body.get("profile_name", "")).strip()
        or Path(filename).stem
    )

    # Retrieve pending content
    pending = getattr(app.state, "_pending_upload", {})
    content = pending.pop(filename, None)
    if content is None:
        raise HTTPException(status_code=404, detail="No pending upload found. Please re-upload.")

    # Save resume file
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESUMES_DIR / filename
    dest.write_bytes(content)

    intent = upsert_intent(
        CONFIG_DIR / "resume_intents.yaml",
        resume_dir=RESUMES_DIR,
        filename=filename,
        keywords=keywords,
        job_types=job_types,
        display_name=display_name,
    )
    intent_data = load_intents(CONFIG_DIR / "resume_intents.yaml")
    intent_id = next(
        key
        for key, entry in intent_data["resumes"].items()
        if entry.get("filename") == filename
    )

    return {
        "ok": True,
        "resume_id": intent_id,
        "filename": filename,
        **intent,
    }


@app.put("/api/resumes/{filename}/intent")
async def update_resume_intent(filename: str, body: dict):
    """Update search intent for an uploaded or manually added supported resume."""
    intent_path = CONFIG_DIR / "resume_intents.yaml"
    data = sync_resume_directory(RESUMES_DIR, intent_path)
    existing_id = next(
        (
            key
            for key, entry in data["resumes"].items()
            if entry.get("filename") == filename
        ),
        None,
    )
    if not existing_id:
        raise HTTPException(status_code=404, detail=f"简历不存在或格式不受支持: {filename}")
    existing = data["resumes"][existing_id]
    keywords = body.get("keywords", existing.get("keywords", []))
    if isinstance(keywords, str):
        keywords = [item for item in re.split(r"[,，\s]+", keywords) if item]
    job_types = body.get("job_types", existing.get("job_types", []))
    if isinstance(job_types, str):
        job_types = [job_types]
    updated = upsert_intent(
        intent_path,
        resume_dir=RESUMES_DIR,
        filename=filename,
        keywords=keywords,
        job_types=job_types,
        display_name=str(body.get("display_name", existing.get("display_name", ""))),
        enabled=bool(body.get("enabled", existing.get("enabled", True))),
    )
    return {"ok": True, "resume_id": existing_id, **updated}


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
            warnings.append(f"意向「{pf.stem}」仍引用此简历，删除后需由 Agent 重新关联")
    path.unlink()
    sync_resume_directory(RESUMES_DIR, CONFIG_DIR / "resume_intents.yaml")
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
# Schedule API
@app.get("/api/schedule")
async def get_schedule():
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"
    cfg = _read_yaml(agent_path) if agent_path.exists() else _read_yaml(sample_path)
    sc = cfg.get("schedule", {})
    return {
        "enabled": bool(sc.get("enabled", False)),
        "job_type": sc.get("job_type", "social"),
        "keyword": sc.get("keyword", "产品经理"),
        "feishu_push": bool(sc.get("feishu_push", False)),
        "git_push": bool(sc.get("git_push", False)),
        "last_run": sc.get("last_run", ""),
    }


@app.put("/api/schedule")
async def update_schedule(body: dict):
    agent_path = CONFIG_DIR / "agent.yaml"
    sample_path = CONFIG_DIR / "agent.sample.yaml"
    if not agent_path.exists():
        if sample_path.exists():
            shutil.copy(sample_path, agent_path)
        else:
            agent_path.write_text("", encoding="utf-8")
    cfg = _read_yaml(agent_path)
    cfg.setdefault("schedule", {})
    for f in ("enabled", "job_type", "keyword", "feishu_push", "git_push"):
        if f in body:
            if f in ("enabled", "feishu_push", "git_push"):
                cfg["schedule"][f] = bool(body[f])
            else:
                cfg["schedule"][f] = str(body[f])
    _write_yaml(agent_path, cfg)
    return {"ok": True, "schedule": cfg["schedule"]}


# Config API (with full Feishu credential editing)
# ---------------------------------------------------------------------------

FEISHU_FIELDS = ["app_id", "app_secret", "wiki_node_token", "bitable_token", "bitable_table_id"]
FEISHU_FIELD_META = {
    "app_id": {
        "label": "应用 ID",
        "desc": "飞书开放平台 → 开发者后台 → 应用设置 → 凭证与基础信息 → App ID",
    },
    "app_secret": {
        "label": "应用密钥 (App Secret)",
        "desc": "飞书开放平台 → 开发者后台 → 应用设置 → 凭证与基础信息 → App Secret",
    },
    "wiki_node_token": {
        "label": "知识库节点 Token",
        "desc": "飞书知识库 → 进入目标知识空间 → 浏览器地址栏 /wiki/ 后方的字符串即为 token",
    },
    "bitable_token": {
        "label": "多维表格 Token (Bitable)",
        "desc": "飞书多维表格 → 进入目标表格 → 浏览器地址栏 /base/ 后方的字符串即为 token",
    },
    "bitable_table_id": {
        "label": "数据表 ID",
        "desc": "多维表格中展开具体数据表 → 浏览器地址栏 ?table= 参数值（或从数据表 URL 获取）",
    },
}


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

    feishu_meta = {
        k: {"label": v["label"], "desc": v["desc"]}
        for k, v in FEISHU_FIELD_META.items()
    }

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

    schedule_cfg = cfg.get("schedule", {})
    schedule = {
        "enabled": bool(schedule_cfg.get("enabled", False)),
        "job_type": schedule_cfg.get("job_type", "social"),
        "keyword": schedule_cfg.get("keyword", "产品经理"),
        "feishu_push": bool(schedule_cfg.get("feishu_push", False)),
        "git_push": bool(schedule_cfg.get("git_push", False)),
        "last_run": schedule_cfg.get("last_run", ""),
    }

    return {
        "decision_level": cfg.get("decision_level", "moderate"),
        "time_filter_days": cfg.get("time_filter_days", 3),
        "threshold_score": cfg.get("threshold_score", 70),
        "jd_truncate_length": cfg.get("jd_truncate_length", 6000),
        "output": cfg.get("output", {}),
        "feishu": feishu,
        "feishu_meta": feishu_meta,
        "feishu_help_url": cfg.get("feishu_help_url", ""),
        "profiles": profiles,
        "schedule": schedule,
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

    # Update feishu help URL
    if "feishu_help_url" in body:
        cfg["feishu_help_url"] = str(body["feishu_help_url"]).strip()

    # Update top-level config fields
    for field in ("decision_level", "threshold_score", "time_filter_days"):
        if field in body:
            cfg[field] = type(cfg.get(field, ""))(body[field])

    _write_yaml(agent_path, cfg)

    # Update schedule settings
    schedule_updates = body.get("schedule", {})
    if schedule_updates:
        cfg.setdefault("schedule", {})
        for f in ("enabled", "job_type", "keyword", "feishu_push", "git_push"):
            if f in schedule_updates:
                cfg["schedule"][f] = type(cfg["schedule"].get(f, ""))(schedule_updates[f]) if f in ("enabled", "feishu_push", "git_push") else str(schedule_updates[f])

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


@app.post("/api/run")
async def run_inspection(body: dict):
    """Open a visible Claude Code session for the full Agent workflow."""
    resume_id = str(body.get("resume_id", "")).strip()
    if not resume_id:
        raise HTTPException(status_code=400, detail="resume_id required")

    intent_path = CONFIG_DIR / "resume_intents.yaml"
    data = sync_resume_directory(RESUMES_DIR, intent_path)
    intent = data["resumes"].get(resume_id)
    if not intent:
        raise HTTPException(status_code=404, detail=f"搜索意向不存在: {resume_id}")
    if not intent.get("enabled", True):
        raise HTTPException(status_code=400, detail="该简历搜索意向未开启")
    if not intent.get("keywords"):
        raise HTTPException(status_code=400, detail="请先为简历补充搜索关键词")
    if not intent.get("job_types"):
        raise HTTPException(status_code=400, detail="请先选择岗位类型")

    run_id = datetime.now().strftime("inspection-%Y%m%d-%H%M%S-%f")
    run_dir = LOGS_DIR / "agent_runs" / run_id
    result_path = run_dir / "result.json"
    prompt = build_inspection_prompt(
        run_id=run_id,
        resume_id=resume_id,
        resume_path=str(intent["resume_path"]),
        intent_path=str(intent_path),
        display_name=str(intent.get("display_name") or Path(intent["filename"]).stem),
        keywords=intent["keywords"],
        job_types=intent["job_types"],
        result_path=str(result_path),
    )
    try:
        launched = launch_claude(
            prompt=prompt,
            session_name=f"SmartHunter-巡检-{run_id}",
            run_dir=run_dir,
            cwd=ROOT,
            agent=None,
        )
    except ClaudeLaunchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "Claude Code 已在新窗口打开",
        "resume_id": resume_id,
        **launched,
    }


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
    # Compute duration from report header to file save time
    duration = None
    duration_str = ""
    if generated:
        try:
            gen_dt = datetime.strptime(generated.strip(), "%Y-%m-%d %H:%M")
            file_dt = datetime.fromtimestamp(path.stat().st_mtime)
            diff = (file_dt - gen_dt).total_seconds()
            if 0 < diff < 7200:  # up to 2 hours, filters out git-touched files from old runs
                duration = int(diff)
                mins, secs = divmod(duration, 60)
                duration_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
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
        "duration": duration,
        "duration_str": duration_str,
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
    """Launch one dedicated Claude Code Agent for all selected companies."""
    company_ids = [str(item).strip() for item in body.get("company_ids", []) if str(item).strip()]
    if not company_ids:
        raise HTTPException(status_code=400, detail="至少选择一家公司")
    keyword = str(body.get("keyword", "产品经理"))
    job_type = str(body.get("job_type", "social"))
    config = _read_companies_config()
    by_id = {str(item.get("id")): item for item in config.get("companies", [])}
    missing = [company_id for company_id in company_ids if company_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"公司不存在: {', '.join(missing)}")

    sources = {}
    for company_id in company_ids:
        company = by_id[company_id]
        links = company.get("links") or company.get("urls") or {}
        source = (
            links.get(job_type)
            or links.get("career_home")
            or links.get("social")
            or links.get("campus")
            or links.get("internship")
            or ""
        )
        sources[company_id] = str(source)

    run_id = datetime.now().strftime("repair-%Y%m%d-%H%M%S-%f")
    run_dir = LOGS_DIR / "agent_runs" / run_id
    prompt = build_repair_prompt(
        run_id=run_id,
        company_ids=company_ids,
        company_sources=sources,
        keyword=keyword,
        job_type=job_type,
        result_path=str(run_dir / "result.json"),
    )
    try:
        launched = launch_claude(
            prompt=prompt,
            session_name=f"SmartHunter-策略修复-{run_id}",
            run_dir=run_dir,
            cwd=ROOT,
            agent="crawler-strategy-inspector",
        )
    except ClaudeLaunchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": f"Claude Code 已在新窗口打开，将串行处理 {len(company_ids)} 家公司",
        "company_ids": company_ids,
        **launched,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web_ui:app", host="127.0.0.1", port=8080, reload=True)
