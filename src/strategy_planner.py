#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Plan crawler strategy actions from link inspection results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


BLOCKING_SIGNALS = {
    "login_required": "login_required",
    "captcha": "captcha",
    "blocked": "anti_crawl",
}


def plan_strategy_action(company: Dict[str, Any], inspection: Dict[str, Any]) -> Dict[str, Any]:
    """Return crawl/collect_evidence/blocked decision for one company."""
    signals = set(inspection.get("signals") or [])
    for signal, block_type in BLOCKING_SIGNALS.items():
        if signal in signals:
            return {
                "action": "blocked",
                "block_type": block_type,
                "reason": signal,
                "requires_agent": False,
                "next_commands": [],
            }

    if not inspection.get("ok", True) or "network_error" in signals:
        return _collect_decision(company, "network_or_link_error")

    strategy = company.get("strategy") or {}
    status = strategy.get("status", "unknown")
    strategy_type = strategy.get("type", "unknown")
    fingerprint = inspection.get("fingerprint")
    old_fingerprint = strategy.get("fingerprint")

    if status == "verified" and strategy_type not in {"unknown", "", None}:
        if old_fingerprint and fingerprint and old_fingerprint != fingerprint:
            return _collect_decision(company, "fingerprint_changed")
        return {
            "action": "crawl",
            "reason": "strategy_verified",
            "requires_agent": False,
            "next_commands": [],
        }

    return _collect_decision(company, f"{status}_strategy")


def write_strategy_task(
    company: Dict[str, Any],
    decision: Dict[str, Any],
    evidence_dir: str | None = None,
    output_root: str | Path = "logs/strategy_tasks",
) -> Path:
    """Write a strategy task for the current agent to analyze."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_id = str(company.get("id", "unknown"))
    task_dir = Path(output_root) / company_id / timestamp
    task_dir.mkdir(parents=True, exist_ok=True)

    task = {
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "company": {
            "id": company.get("id"),
            "name": company.get("name"),
            "links": company.get("links") or company.get("urls") or {},
            "strategy": company.get("strategy") or {},
        },
        "decision": decision,
        "requires_agent": bool(decision.get("requires_agent")),
        "evidence_dir": evidence_dir,
        "next_commands": decision.get("next_commands") or _default_next_commands(company),
        "agent_instructions": [
            "Read evidence.json, network.json, page.html/page.txt, and page.png if available.",
            "Decide whether the site should use config_intercept, config_dom, legacy_python, custom_python, browser_operation, or unsupported.",
            "Patch config/companies.yaml or src/site_strategies only when evidence supports the strategy.",
            "Run a targeted crawler validation after patching.",
        ],
    }
    task_path = task_dir / "task.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return task_path


def _collect_decision(company: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "action": "collect_evidence",
        "reason": reason,
        "requires_agent": True,
        "next_commands": _default_next_commands(company),
    }


def _default_next_commands(company: Dict[str, Any]) -> list[str]:
    company_id = company.get("id", "<company_id>")
    return [
        f'python -m src.crawler_evidence --company {company_id} --keyword "产品经理" --job-type social'
    ]
