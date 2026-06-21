from pathlib import Path

import pytest
import yaml

from src.strategy_applier import (
    apply_strategy_decision,
    finalize_strategy_verification,
    validate_strategy_decision,
)


def _valid_decision():
    return {
        "company_id": "alpha",
        "status": "repaired",
        "recommended_strategy": {"type": "config_intercept", "confidence": "high"},
        "evidence_refs": [{"artifact": "network.json", "locator": "data.jobs"}],
        "config_patch": {
            "api": {"type": "intercept", "pattern": "/api/jobs", "data_path": "data.jobs"},
            "field_mappings": {
                "id": {"source": "id"},
                "title": {"source": "title"},
                "duty": {"source": "description"},
                "requirement": {"source": "requirement"},
            },
            "url_template": "https://alpha.example/jobs/{id}",
        },
        "unsupported": {"reason": None},
    }


def test_validate_strategy_decision_rejects_unknown_strategy_and_missing_evidence():
    invalid = _valid_decision()
    invalid["recommended_strategy"]["type"] = "magic"
    with pytest.raises(ValueError, match="strategy"):
        validate_strategy_decision(invalid)

    missing_evidence = _valid_decision()
    missing_evidence["evidence_refs"] = []
    with pytest.raises(ValueError, match="evidence"):
        validate_strategy_decision(missing_evidence)


def test_apply_strategy_decision_changes_only_target_company_and_preserves_other_text(tmp_path):
    path = tmp_path / "companies.yaml"
    path.write_text(
        """# header comment
companies:
  - id: alpha
    name: Alpha
    enabled: true
    api:
      type: intercept
      pattern: old
      data_path: old.items
    field_mappings:
      id: {source: old_id}
      title: {source: old_title}
  # keep beta comment
  - id: beta
    name: Beta
    enabled: true
    custom: untouched
""",
        encoding="utf-8",
    )
    before_beta = path.read_text(encoding="utf-8").split("  # keep beta comment", 1)[1]

    apply_strategy_decision(path, _valid_decision())

    content = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    alpha = next(item for item in parsed["companies"] if item["id"] == "alpha")
    assert alpha["api"]["pattern"] == "/api/jobs"
    assert alpha["url_template"] == "https://alpha.example/jobs/{id}"
    assert content.split("  # keep beta comment", 1)[1] == before_beta


def test_finalize_strategy_verification_requires_pass_and_persists_fingerprint(tmp_path):
    path = tmp_path / "companies.yaml"
    path.write_text(
        """companies:
  - id: alpha
    name: Alpha
    strategy:
      type: config_intercept
      status: needs_verification

# keep defaults comment
defaults:
  max_jobs: 50
""",
        encoding="utf-8",
    )

    updated = finalize_strategy_verification(
        path,
        "alpha",
        {"status": "passed", "jobs_count": 3, "valid_jobs_rate": 1.0},
        fingerprint="abc123",
        evidence_dir="logs/evidence/alpha",
    )

    assert updated["strategy"]["status"] == "verified"
    assert updated["strategy"]["fingerprint"] == "abc123"
    assert updated["strategy"]["evidence_dir"] == "logs/evidence/alpha"
    assert updated["strategy"]["last_verified_at"]
    saved = path.read_text(encoding="utf-8")
    assert "# keep defaults comment" in saved
    assert "defaults:\n  max_jobs: 50" in saved

    with pytest.raises(ValueError, match="passed"):
        finalize_strategy_verification(
            path,
            "alpha",
            {"status": "failed"},
            fingerprint="abc123",
            evidence_dir="logs/evidence/alpha",
        )
