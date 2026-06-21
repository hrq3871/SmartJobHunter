"""Validate and apply structured crawler strategy decisions."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ALLOWED_STRATEGIES = {
    "config_intercept",
    "config_dom",
    "legacy_python",
    "custom_python",
    "browser_operation",
    "unsupported",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def validate_strategy_decision(decision: dict[str, Any]) -> None:
    company_id = str(decision.get("company_id") or "").strip()
    if not company_id:
        raise ValueError("company_id is required")
    strategy = decision.get("recommended_strategy") or {}
    strategy_type = strategy.get("type")
    if strategy_type not in ALLOWED_STRATEGIES:
        raise ValueError(f"unsupported strategy: {strategy_type}")
    if strategy.get("confidence") not in ALLOWED_CONFIDENCE:
        raise ValueError("strategy confidence must be high, medium, or low")
    unsupported_reason = (decision.get("unsupported") or {}).get("reason")
    if strategy_type == "unsupported":
        if not unsupported_reason:
            raise ValueError("unsupported strategy requires a reason")
        return
    if not decision.get("evidence_refs"):
        raise ValueError("evidence_refs are required before applying a strategy")
    if strategy_type in {"config_intercept", "config_dom"}:
        patch = decision.get("config_patch") or {}
        if not patch.get("api") or not patch.get("field_mappings"):
            raise ValueError("config strategy requires api and field_mappings")
        template = patch.get("url_template")
        if template and not str(template).startswith(("http://", "https://")):
            raise ValueError("url_template must be HTTP(S)")


def apply_strategy_decision(config_path: str | Path, decision: dict[str, Any]) -> dict[str, Any]:
    """Apply a normal config strategy while preserving unrelated YAML text."""
    validate_strategy_decision(decision)
    strategy_type = decision["recommended_strategy"]["type"]
    if strategy_type not in {"config_intercept", "config_dom"}:
        raise ValueError("only config_intercept/config_dom can be applied deterministically")

    path = Path(config_path)
    original_text = path.read_text(encoding="utf-8")
    config = yaml.safe_load(original_text) or {}
    companies = config.get("companies") or []
    company_id = str(decision["company_id"])
    target = next((item for item in companies if str(item.get("id")) == company_id), None)
    if target is None:
        raise ValueError(f"company not found: {company_id}")

    updated = deepcopy(target)
    for key, value in (decision.get("config_patch") or {}).items():
        if value is not None:
            updated[key] = deepcopy(value)
    updated["strategy"] = {
        **(updated.get("strategy") or {}),
        "type": strategy_type,
        "status": "needs_verification",
    }

    _replace_company_block(path, original_text, company_id, updated)
    return updated


def finalize_strategy_verification(
    config_path: str | Path,
    company_id: str,
    verification: dict[str, Any],
    *,
    fingerprint: str,
    evidence_dir: str,
) -> dict[str, Any]:
    """Mark a strategy verified only after strict deterministic validation."""
    if verification.get("status") != "passed":
        raise ValueError("strategy verification status must be passed")
    if int(verification.get("jobs_count") or 0) <= 0:
        raise ValueError("strategy verification must contain at least one job")
    if float(verification.get("valid_jobs_rate") or 0) < 1.0:
        raise ValueError("strategy verification valid_jobs_rate must be 1.0")
    if not str(fingerprint or "").strip():
        raise ValueError("strategy verification requires a fingerprint")
    if not str(evidence_dir or "").strip():
        raise ValueError("strategy verification requires an evidence_dir")

    path = Path(config_path)
    original_text = path.read_text(encoding="utf-8")
    config = yaml.safe_load(original_text) or {}
    target = next(
        (item for item in config.get("companies") or [] if str(item.get("id")) == str(company_id)),
        None,
    )
    if target is None:
        raise ValueError(f"company not found: {company_id}")

    updated = deepcopy(target)
    updated["strategy"] = {
        **(updated.get("strategy") or {}),
        "status": "verified",
        "fingerprint": str(fingerprint),
        "evidence_dir": str(evidence_dir),
        "last_verified_at": datetime.now().astimezone().isoformat(),
    }
    _replace_company_block(path, original_text, str(company_id), updated)
    return updated


def _replace_company_block(
    path: Path,
    original_text: str,
    company_id: str,
    updated: dict[str, Any],
) -> None:
    """Replace one YAML company block while retaining unrelated text/comments."""
    lines = original_text.splitlines(keepends=True)
    start_pattern = re.compile(rf"^  - id:\s*[\"\']?{re.escape(company_id)}[\"\']?\s*$")
    start = next((i for i, line in enumerate(lines) if start_pattern.match(line.rstrip("\r\n"))), None)
    if start is None:
        raise ValueError(f"could not locate company block: {company_id}")
    next_start = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(r"^  - id:\s*", lines[i])
            or (lines[i].strip() and not lines[i][0].isspace())
        ),
        len(lines),
    )
    end = next_start
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1

    dumped = yaml.safe_dump(
        {"companies": [updated]},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    dumped_lines = dumped.splitlines()
    block_lines = dumped_lines[1:]
    replacement = [f"  {line}\n" for line in block_lines]
    new_text = "".join(lines[:start] + replacement + lines[end:])
    path.write_text(new_text, encoding="utf-8")
