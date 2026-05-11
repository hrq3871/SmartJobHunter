#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feishu_push import get_feishu_push_status, set_feishu_push_enabled


def test_feishu_push_switch_updates_agent_config(tmp_path):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "feishu": {
                "enabled": False,
                "wiki_node_token": "wiki",
                "bitable_token": "base",
                "bitable_table_id": "table",
            }
        }, allow_unicode=True),
        encoding="utf-8",
    )

    enabled_status = set_feishu_push_enabled(True, config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert enabled_status["enabled"] is True
    assert config["feishu"]["enabled"] is True

    disabled_status = set_feishu_push_enabled(False, config_path)

    assert disabled_status["enabled"] is False
    assert get_feishu_push_status(config_path)["has_wiki_node_token"] is True


def test_feishu_push_switch_creates_missing_config(tmp_path):
    config_path = tmp_path / "missing" / "agent.yaml"

    status = set_feishu_push_enabled(True, config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert status["enabled"] is True
    assert config["feishu"]["enabled"] is True
