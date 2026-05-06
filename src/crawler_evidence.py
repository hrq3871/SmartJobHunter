#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Collect crawler/network evidence for agent-side repair analysis."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "auth",
    "authorization",
    "session",
    "sid",
    "cookie",
}

JOB_FIELD_HINTS = {
    "id",
    "jobid",
    "postid",
    "positionid",
    "jobunionid",
    "title",
    "name",
    "jobname",
    "recruitpostname",
    "description",
    "requirement",
    "responsibility",
    "jobduty",
    "city",
    "location",
    "workplace",
}


def sanitize_url(url: str) -> str:
    """Remove obvious secrets from query strings while keeping useful params."""
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_QUERY_KEYS or "token" in key.lower():
            query.append((key, "[redacted]"))
        else:
            query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _field_score(item: Dict[str, Any]) -> tuple[int, List[str]]:
    keys = {str(key).lower() for key in item.keys()}
    field_hints = sorted(key for key in keys if key in JOB_FIELD_HINTS)
    score = len(field_hints)
    if any(key in keys for key in ["title", "name", "jobname", "recruitpostname"]):
        score += 3
    if any(key in keys for key in ["description", "requirement", "responsibility", "jobduty"]):
        score += 2
    if any(key in keys for key in ["id", "jobid", "postid", "positionid", "jobunionid"]):
        score += 2
    return score, field_hints


def find_job_array_candidates(payload: Any, path: str = "") -> List[Dict[str, Any]]:
    """Find list-of-dict payload paths that look like job arrays."""
    candidates: List[Dict[str, Any]] = []

    if isinstance(payload, list):
        dict_items = [item for item in payload if isinstance(item, dict)]
        if dict_items:
            score, field_hints = _field_score(dict_items[0])
            if score > 0:
                candidates.append({
                    "path": path or "$",
                    "score": score,
                    "item_count": len(dict_items),
                    "field_hints": field_hints,
                    "sample_keys": list(dict_items[0].keys())[:30],
                })
        for index, item in enumerate(payload[:10]):
            candidates.extend(find_job_array_candidates(item, f"{path}.{index}" if path else str(index)))
        return sorted(candidates, key=lambda item: item["score"], reverse=True)

    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}" if path else str(key)
            candidates.extend(find_job_array_candidates(value, child_path))

    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _truncate_sample(value: Any, limit: int = 300) -> Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        return {key: _truncate_sample(child, limit) for key, child in list(value.items())[:20]}
    if isinstance(value, list):
        return [_truncate_sample(child, limit) for child in value[:3]]
    return value


def collect_evidence(
    url: str,
    company_id: str = "",
    keyword: str = "",
    output_root: str = "logs/crawler_evidence",
    headless: bool = True,
) -> Dict[str, Any]:
    """Visit a URL and capture JSON responses that may contain job arrays."""
    from playwright.sync_api import sync_playwright

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = company_id or "url"
    output_dir = Path(output_root) / company_slug / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    responses: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        def handle_response(response):
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower():
                return
            try:
                data = response.json()
            except Exception:
                return
            candidates = find_job_array_candidates(data)
            responses.append({
                "url": sanitize_url(response.url),
                "status": response.status,
                "content_type": content_type,
                "job_array_candidates": candidates[:5],
                "sample": _truncate_sample(data),
            })

        page.on("response", handle_response)
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        screenshot_path = output_dir / "page.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        title = page.title()
        final_url = sanitize_url(page.url)
        browser.close()

    evidence = {
        "company_id": company_id,
        "input_url": sanitize_url(url),
        "final_url": final_url,
        "page_title": title,
        "keyword": keyword,
        "captured_at": datetime.now().isoformat(),
        "responses": responses,
        "screenshot": str(screenshot_path),
        "agent_next_steps": [
            "Compare top candidate paths with config/companies.yaml api.data_path.",
            "Compare sample keys with field_mappings.",
            "Patch config only if evidence supports the change.",
            "Run targeted crawler validation after patching.",
        ],
    }
    evidence_path = output_dir / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence["evidence_path"] = str(evidence_path)
    return evidence


def _company_url(company_id: str, keyword: str, job_type: str) -> str:
    from .crawler_factory import get_company_config

    config = get_company_config(company_id)
    if not config:
        raise SystemExit(f"Company not found: {company_id}")
    urls = config.get("urls", {})
    url = urls.get(job_type) or urls.get("social")
    if not url:
        raise SystemExit(f"No URL configured for {company_id} ({job_type})")
    if "{keyword}" in url:
        return url.replace("{keyword}", keyword)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}keyword={keyword}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect crawler evidence for agent repair analysis")
    parser.add_argument("--company", help="Company id from config/companies.yaml")
    parser.add_argument("--url", help="Direct URL to inspect")
    parser.add_argument("--keyword", default="产品经理")
    parser.add_argument("--job-type", default="social")
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    url = args.url or _company_url(args.company, args.keyword, args.job_type)
    evidence = collect_evidence(
        url=url,
        company_id=args.company or "",
        keyword=args.keyword,
        headless=not args.headful,
    )
    print(f"Evidence saved: {evidence['evidence_path']}")
    print(f"JSON responses captured: {len(evidence['responses'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
