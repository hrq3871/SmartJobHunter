#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Company link and crawler strategy registry.

Users maintain company career links in config/companies.yaml. This module keeps
that user-maintained list compatible with the existing urls/api/field_mappings
configuration so old solidified crawlers continue to work.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

import yaml


DEFAULT_STRATEGY = {
    "status": "unknown",
    "type": "unknown",
    "owner": "agent",
    "last_verified_at": None,
    "evidence_dir": None,
    "fingerprint": None,
}


def normalize_company(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a company dict with links and strategy fields populated."""
    company = deepcopy(raw)
    links = {
        key: value
        for key, value in (company.get("links") or {}).items()
        if value
    }

    for key, value in (company.get("urls") or {}).items():
        if value and key not in links:
            links[key] = value

    company["links"] = links
    strategy = dict(DEFAULT_STRATEGY)
    strategy.update(company.get("strategy") or {})

    if strategy["type"] == "unknown":
        api_type = (company.get("api") or {}).get("type") or (company.get("api") or {}).get("method")
        if api_type == "intercept":
            strategy["type"] = "config_intercept"
        elif api_type == "dom":
            strategy["type"] = "config_dom"
        elif company.get("legacy_python"):
            strategy["type"] = "legacy_python"

    # A usable configuration is not proof that it still matches the live site.
    # Only an evidence-backed strategy with a stored page fingerprint is verified.
    if strategy["status"] == "verified" and not strategy.get("fingerprint"):
        strategy["status"] = "needs_review"

    company["strategy"] = strategy
    return company


def load_companies(config_path: str | Path | None = None, enabled_only: bool = True) -> List[Dict[str, Any]]:
    """Load normalized companies from config/companies.yaml."""
    path = Path(config_path) if config_path else Path(__file__).parent.parent / "config" / "companies.yaml"
    if not path.exists():
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    companies = [normalize_company(company) for company in data.get("companies", [])]
    if enabled_only:
        companies = [company for company in companies if company.get("enabled", False)]
    return companies


def company_needs_strategy(company: Dict[str, Any]) -> bool:
    """Return True when a company needs agent strategy analysis."""
    strategy = company.get("strategy") or {}
    status = strategy.get("status", "unknown")
    strategy_type = strategy.get("type", "unknown")
    if status in {"unknown", "failed", "stale", "needs_review"}:
        return True
    if strategy_type in {"unknown", "", None}:
        return True
    return False


def choose_company_url(company: Dict[str, Any], keyword: str = "产品经理", job_type: str = "social") -> str:
    """Choose the best configured URL for a company and apply a keyword."""
    links = company.get("links") or {}
    urls = company.get("urls") or {}
    url = (
        links.get(job_type)
        or urls.get(job_type)
        or links.get("career_home")
        or urls.get("social")
        or links.get("social")
        or ""
    )
    if not url:
        return ""
    if "{keyword}" in url:
        return url.replace("{keyword}", keyword)
    return url


def _has_solidified_config(company: Dict[str, Any], strategy: Dict[str, Any]) -> bool:
    strategy_type = strategy.get("type")
    if strategy_type in {"config_intercept", "config_dom"}:
        return bool(company.get("api") and company.get("field_mappings"))
    if strategy_type == "legacy_python":
        return True
    return False
