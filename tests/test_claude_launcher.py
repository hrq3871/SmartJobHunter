#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import subprocess

import pytest

from src.claude_launcher import (
    ClaudeLaunchError,
    build_inspection_prompt,
    build_repair_prompt,
    launch_claude,
)


class _Process:
    pid = 43210


def test_build_inspection_prompt_requires_agent_profile_before_matching(tmp_path):
    run_dir = tmp_path / "run-001"

    prompt = build_inspection_prompt(
        run_id="run-001",
        resume_id="resume-1",
        resume_path="resumes/candidate.pdf",
        intent_path="config/resume_intents.yaml",
        display_name="AI 产品",
        keywords=["AI 产品经理", "ToB"],
        job_types=["校招", "实习"],
        result_path=str(run_dir / "result.json"),
    )

    assert "先读取完整简历" in prompt
    assert "生成或更新正式 profile" in prompt
    assert "profiles/" in prompt
    assert "Agent 语义匹配" in prompt
    assert "resume-1" in prompt
    assert "AI 产品经理" in prompt
    assert str(run_dir / "result.json") in prompt


def test_build_repair_prompt_contains_all_selected_companies_once():
    prompt = build_repair_prompt(
        run_id="repair-001",
        company_ids=["ruijie_campus", "yonyou_campus"],
        keyword="产品经理",
        job_type="campus",
        result_path="logs/agent_runs/repair-001/result.json",
    )

    assert prompt.count("ruijie_campus") == 1
    assert prompt.count("yonyou_campus") == 1
    assert "同一个 Agent" in prompt
    assert "不得再创建子 Agent" in prompt


def test_launch_claude_opens_visible_windows_cmd_with_auto_permissions(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("src.claude_launcher.shutil.which", lambda name: r"C:\Tools\claude.cmd" if name.startswith("claude") else None)
    monkeypatch.setattr("src.claude_launcher.sys.platform", "win32")
    monkeypatch.setattr("src.claude_launcher.os.environ", {"COMSPEC": r"C:\Windows\System32\cmd.exe"})

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return _Process()

    monkeypatch.setattr("src.claude_launcher.subprocess.Popen", fake_popen)
    run_dir = tmp_path / "run-001"

    result = launch_claude(
        prompt="执行真实巡检",
        session_name="SmartHunter-巡检-run-001",
        run_dir=run_dir,
        cwd=tmp_path,
    )

    command, kwargs = calls[0]
    assert command[:3] == [r"C:\Windows\System32\cmd.exe", "/d", "/k"]
    assert "--permission-mode auto" in command[3]
    assert "SmartHunter-巡检-run-001" in command[3]
    assert kwargs["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert kwargs["cwd"] == str(tmp_path)
    assert result["pid"] == 43210
    assert result["status"] == "launched"
    assert json.loads((run_dir / "launch.json").read_text(encoding="utf-8"))["pid"] == 43210


def test_launch_repair_uses_existing_crawler_strategy_agent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("src.claude_launcher.shutil.which", lambda name: r"C:\Tools\claude.cmd")
    monkeypatch.setattr("src.claude_launcher.sys.platform", "win32")
    monkeypatch.setattr("src.claude_launcher.os.environ", {"COMSPEC": "cmd.exe"})
    monkeypatch.setattr(
        "src.claude_launcher.subprocess.Popen",
        lambda command, **kwargs: calls.append(command) or _Process(),
    )

    launch_claude(
        prompt="修复两家公司",
        session_name="SmartHunter-策略修复-repair-001",
        run_dir=tmp_path / "repair-001",
        cwd=tmp_path,
        agent="crawler-strategy-inspector",
    )

    assert "--agent crawler-strategy-inspector" in calls[0][3]


def test_launch_claude_reports_missing_installation(tmp_path, monkeypatch):
    monkeypatch.setattr("src.claude_launcher.shutil.which", lambda name: None)

    with pytest.raises(ClaudeLaunchError, match="Claude Code"):
        launch_claude(
            prompt="test",
            session_name="test",
            run_dir=tmp_path / "missing",
            cwd=tmp_path,
        )


def test_launch_claude_does_not_write_success_when_popen_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("src.claude_launcher.shutil.which", lambda name: r"C:\Tools\claude.cmd")
    monkeypatch.setattr("src.claude_launcher.sys.platform", "win32")
    monkeypatch.setattr("src.claude_launcher.os.environ", {"COMSPEC": "cmd.exe"})
    monkeypatch.setattr(
        "src.claude_launcher.subprocess.Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cannot open console")),
    )
    run_dir = tmp_path / "failed"

    with pytest.raises(ClaudeLaunchError, match="cannot open console"):
        launch_claude(
            prompt="test",
            session_name="test",
            run_dir=run_dir,
            cwd=tmp_path,
        )

    assert (run_dir / "request.json").exists()
    assert not (run_dir / "launch.json").exists()
