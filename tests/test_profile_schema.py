#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import validate_profile


def test_profile_schema_document_supports_non_product_profiles():
    schema_path = Path("config/profile_schema.yaml")

    assert schema_path.exists()

    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    optional_fields = set(schema["optional"])

    assert "target_roles" in schema["required"]
    assert {"must_have", "nice_to_have", "avoid", "target_domains"}.issubset(optional_fields)
    assert "产品经理" not in str(schema.get("example", {}).get("name", ""))


def test_validate_profile_accepts_new_general_fields():
    profile = {
        "name": "后端开发",
        "enabled": True,
        "resume": "./resumes/backend.md",
        "target_roles": ["后端开发工程师"],
        "must_have": ["Python", "数据库"],
        "avoid": ["销售"],
    }

    assert validate_profile(profile) is True

