#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书 Wiki 推送模块
将岗位报告推送到飞书知识库（使用 lark-cli）
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml


def load_feishu_config() -> Dict:
    """从配置文件加载飞书配置"""
    config_path = Path(__file__).parent.parent / "config" / "agent.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config.get('feishu', {})
    return {}


def _agent_config_path(config_path: str | Path = None) -> Path:
    return Path(config_path) if config_path else Path(__file__).parent.parent / "config" / "agent.yaml"


def get_feishu_push_status(config_path: str | Path = None) -> Dict:
    """Return Feishu push switch status and required config presence."""
    path = _agent_config_path(config_path)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    feishu = config.get('feishu', {}) or {}
    return {
        "config_path": str(path),
        "enabled": bool(feishu.get('enabled', False)),
        "has_wiki_node_token": bool(feishu.get('wiki_node_token')),
        "has_bitable_token": bool(feishu.get('bitable_token')),
        "has_bitable_table_id": bool(feishu.get('bitable_table_id')),
    }


def set_feishu_push_enabled(enabled: bool, config_path: str | Path = None) -> Dict:
    """Enable or disable Feishu push in config/agent.yaml."""
    path = _agent_config_path(config_path)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    feishu = config.get('feishu') or {}
    feishu['enabled'] = bool(enabled)
    config['feishu'] = feishu

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    return get_feishu_push_status(path)


def push_to_feishu(report_path: str, profile_name: str) -> Optional[Dict]:
    """推送报告到飞书 Wiki（使用 lark-cli）

    Args:
        report_path: 报告文件路径
        profile_name: 简历标识

    Returns:
        推送结果，包含 url
    """
    config = load_feishu_config()
    if not config.get('enabled', False):
        print("[Feishu] 推送未启用")
        return None

    wiki_node_token = config.get('wiki_node_token')
    if not wiki_node_token:
        print("[Feishu] 未配置 wiki_node_token")
        return None

    report_file = Path(report_path)
    if not report_file.exists():
        print(f"[Feishu] 报告文件不存在: {report_path}")
        return None

    # 读取报告内容
    content = report_file.read_text(encoding='utf-8')

    # 标题格式：{简历标识}_{YYYYMMDD_HHMM}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    title = f"{profile_name}_{timestamp}"

    return push_markdown_to_feishu(title, content, wiki_node_token)


def push_markdown_to_feishu(title: str, content: str, wiki_node_token: str = None) -> Optional[Dict]:
    """推送 Markdown 内容到飞书 Wiki

    Args:
        title: 文档标题
        content: Markdown 内容
        wiki_node_token: Wiki 节点 token（可选，默认从配置读取）

    Returns:
        推送结果
    """
    config = load_feishu_config()
    if not wiki_node_token:
        wiki_node_token = config.get('wiki_node_token')

    if not wiki_node_token:
        print("[Feishu] 未配置 wiki_node_token")
        return None

    # Windows 下需要完整路径
    lark_cli = os.path.expandvars(r"%APPDATA%\npm\lark-cli.cmd")
    if not os.path.exists(lark_cli):
        lark_cli = "lark-cli"

    # 直接通过 stdin 传递内容
    cmd = [
        lark_cli, "docs", "+create",
        "--title", title,
        "--markdown", "-",  # 从 stdin 读取
        "--wiki-node", wiki_node_token,
        "--as", "user"
    ]

    try:
        result = subprocess.run(
            cmd,
            input=content,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=120,
            shell=True
        )

        if result.returncode != 0:
            print(f"[Feishu] 推送失败: {result.stderr}")
            return None

        # 解析返回结果 (lark-cli 格式: {"ok": true, "data": {...}})
        try:
            data = json.loads(result.stdout)
            if data.get('ok'):
                doc_data = data.get('data', {})
                doc_url = doc_data.get('doc_url', '')
                print(f"[Feishu] 推送成功: {doc_url}")
                return {"url": doc_url, "doc_id": doc_data.get('doc_id')}
            else:
                error = data.get('error', {})
                print(f"[Feishu] 推送失败: {error.get('message', 'unknown error')}")
                return None
        except json.JSONDecodeError:
            print(f"[Feishu] 解析响应失败: {result.stdout[:200]}")
            return None

    except subprocess.TimeoutExpired:
        print("[Feishu] 推送超时")
        return None
    except FileNotFoundError:
        print("[Feishu] lark-cli 未安装")
        return None
    except Exception as e:
        print(f"[Feishu] 推送异常: {e}")
        return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="SmartJobHunter 飞书推送开关")
    parser.add_argument(
        "--push",
        choices=["on", "off", "status"],
        default="status",
        help="开启/关闭/查看每日巡检后的飞书 Wiki 和多维表格推送",
    )
    parser.add_argument("--config", help="agent.yaml 路径，默认 config/agent.yaml")
    args = parser.parse_args()

    if args.push == "on":
        status = set_feishu_push_enabled(True, args.config)
    elif args.push == "off":
        status = set_feishu_push_enabled(False, args.config)
    else:
        status = get_feishu_push_status(args.config)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
