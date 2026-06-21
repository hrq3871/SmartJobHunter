#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build and launch visible Claude Code workflows from the local Web console."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


class ClaudeLaunchError(RuntimeError):
    """Raised when a Claude Code session cannot be started honestly."""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_inspection_prompt(
    *,
    run_id: str,
    resume_id: str,
    resume_path: str,
    intent_path: str,
    display_name: str,
    keywords: Iterable[str],
    job_types: Iterable[str],
    result_path: str,
) -> str:
    keyword_text = "、".join(str(item) for item in keywords)
    job_type_text = "、".join(str(item) for item in job_types)
    return f"""执行 SmartJobHunter 完整巡检，运行 ID：{run_id}。

严格读取项目 CLAUDE.md 和 jobhunter Skillmap。搜索意向 ID：{resume_id}；意向文件：{intent_path}；简历：{resume_path}；显示名称：{display_name}；关键词：{keyword_text}；岗位类型：{job_type_text}。

先读取完整简历，只引用简历事实，使用 profile.md 与 prompts/build_candidate_profile.md 生成或更新正式 profile 到 profiles/。正式 profile 必须包含目标角色、领域、must_have、nice_to_have、avoid、偏好、项目证据、缺口和简历 fingerprint。然后执行策略巡检、岗位抓取、去重、JD 画像和 Agent 语义匹配；Python 评分只能作为 fallback，不得冒充 Agent 判断。生成全量审计报告，并把最终状态、报告路径、profile 路径和错误写入 {result_path}。不要修改与本任务无关的文件。"""


def build_repair_prompt(
    *,
    run_id: str,
    company_ids: Iterable[str],
    company_sources: dict[str, str] | None = None,
    keyword: str,
    job_type: str,
    result_path: str,
) -> str:
    sources = company_sources or {}
    companies = "\n".join(
        f"- {company_id} | {sources.get(str(company_id), '未配置原始链接')}"
        for company_id in company_ids
    )
    return f"""执行 SmartJobHunter 批量抓取策略巡检与修复，运行 ID：{run_id}。

公司任务：
{companies}

关键词：{keyword}。岗位类型：{job_type}。必须由同一个 Agent 串行处理全部公司，不得再创建子 Agent。按 crawler-strategy-inspector 定义采证、分析 API/字段、应用策略并独立验证；链接必须原封不动。登录、验证码、网络、地域限制和强反爬必须如实报告，不得绕过。把中文汇总和最终状态写入 {result_path}。"""


def launch_claude(
    *,
    prompt: str,
    session_name: str,
    run_dir: Path,
    cwd: Path,
    agent: str | None = None,
) -> dict:
    """Open Claude Code interactively in a new visible Windows console."""
    run_dir = Path(run_dir)
    cwd = Path(cwd)
    run_id = run_dir.name
    request = {
        "run_id": run_id,
        "session_name": session_name,
        "agent": agent,
        "prompt": prompt,
        "cwd": str(cwd),
        "requested_at": datetime.now().astimezone().isoformat(),
    }
    _write_json(run_dir / "request.json", request)

    claude = shutil.which("claude.cmd") or shutil.which("claude")
    if not claude:
        raise ClaudeLaunchError("未找到 Claude Code；请先确认 `claude --version` 可运行")

    claude_args = [
        claude,
        "--permission-mode",
        "auto",
        "--name",
        session_name,
    ]
    if agent:
        claude_args.extend(["--agent", agent])
    claude_args.append(prompt)

    kwargs: dict = {"cwd": str(cwd)}
    if sys.platform == "win32":
        command_line = subprocess.list2cmdline(claude_args)
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/k", command_line]
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        command = claude_args

    try:
        process = subprocess.Popen(command, **kwargs)
    except Exception as exc:
        _write_json(
            run_dir / "failure.json",
            {
                "run_id": run_id,
                "status": "launch_failed",
                "error": str(exc),
                "failed_at": datetime.now().astimezone().isoformat(),
            },
        )
        raise ClaudeLaunchError(f"Claude Code 启动失败：{exc}") from exc

    result = {
        "run_id": run_id,
        "status": "launched",
        "pid": process.pid,
        "agent": agent,
        "session_name": session_name,
        "launched_at": datetime.now().astimezone().isoformat(),
    }
    _write_json(run_dir / "launch.json", result)
    return result
