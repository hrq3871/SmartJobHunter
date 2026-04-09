#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Git 自动提交脚本
在测试通过后自动提交并推送到 GitHub
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_git_command(cmd: list, check: bool = True) -> tuple:
    """执行 git 命令"""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if check and result.returncode != 0:
            print(f"[Git] 命令失败: git {' '.join(cmd)}")
            print(f"       错误: {result.stderr}")
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        return False, str(e)


def is_git_repo() -> bool:
    """检查是否是 git 仓库"""
    success, _ = run_git_command(["rev-parse", "--git-dir"], check=False)
    return success


def has_changes() -> bool:
    """检查是否有未提交的更改"""
    success, output = run_git_command(["status", "--porcelain"])
    if success and output.strip():
        return True
    return False


def auto_commit_push(message: str = None) -> bool:
    """自动提交并推送

    Args:
        message: 提交信息，默认自动生成

    Returns:
        是否成功
    """
    # 检查是否是 git 仓库
    if not is_git_repo():
        print("[Git] 不是 git 仓库，请先运行: git init")
        return False

    # 检查是否有更改
    if not has_changes():
        print("[Git] 没有需要提交的更改")
        return True

    # 生成提交信息
    if not message:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        message = f"auto: 巡检更新 {timestamp}"

    # 添加所有更改
    print("[Git] 添加更改...")
    success, _ = run_git_command(["add", "-A"])
    if not success:
        return False

    # 提交
    print(f"[Git] 提交: {message}")
    success, _ = run_git_command(["commit", "-m", message])
    if not success:
        return False

    # 推送
    print("[Git] 推送到远程...")
    success, _ = run_git_command(["push"])
    if not success:
        print("[Git] 推送失败，可能需要先设置远程仓库")
        print("      git remote add origin <your-repo-url>")
        print("      git push -u origin main")
        return False

    print("[Git] 推送成功!")
    return True


def setup_git():
    """初始化 git 仓库"""
    if is_git_repo():
        print("[Git] 已经是 git 仓库")
        return True

    print("[Git] 初始化仓库...")
    success, _ = run_git_command(["init"])
    if not success:
        return False

    print("[Git] 添加所有文件...")
    run_git_command(["add", "-A"])

    print("[Git] 创建初始提交...")
    run_git_command(["commit", "-m", "init: SmartJobHunter 初始化"])

    print("\n[Git] 仓库初始化完成!")
    print("\n下一步:")
    print("1. 在 GitHub 创建新仓库 (不要勾选 README)")
    print("2. 运行以下命令:")
    print("   git remote add origin https://github.com/你的用户名/SmartJobHunter.git")
    print("   git branch -M main")
    print("   git push -u origin main")

    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Git 自动提交工具')
    parser.add_argument('--init', action='store_true', help='初始化 git 仓库')
    parser.add_argument('-m', '--message', help='提交信息')
    parser.add_argument('--push', action='store_true', help='自动提交并推送')

    args = parser.parse_args()

    if args.init:
        setup_git()
    elif args.push:
        auto_commit_push(args.message)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
