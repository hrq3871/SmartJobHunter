#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书多维表格模块
管理岗位投递状态追踪（使用 lark-cli）
"""

import os
import json
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional
import yaml
from pathlib import Path


def load_feishu_config() -> Dict:
    """从配置文件加载飞书配置"""
    config_path = Path(__file__).parent.parent / "config" / "agent.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config.get('feishu', {})
    return {}


def batch_add_records(app_token: str, table_id: str, records: List[Dict]) -> Optional[Dict]:
    """批量添加记录到多维表格

    Args:
        app_token: 多维表格 token
        table_id: 数据表 ID
        records: 记录列表

    Returns:
        添加结果
    """
    lark_cli = os.path.expandvars(r"%APPDATA%\npm\lark-cli.cmd")
    if not os.path.exists(lark_cli):
        lark_cli = "lark-cli"

    # lark-cli 格式: {"fields": ["字段1", "字段2"], "rows": [["值1", "值2"], ...]}
    fields = ["岗位标题", "公司", "岗位链接", "AI评分", "投递状态", "录取状态", "岗位类型", "投递简历", "报告链接", "创建时间"]
    rows = []
    for record in records:
        rows.append([
            record.get("岗位标题", ""),
            record.get("公司", ""),
            record.get("岗位链接", ""),
            record.get("AI评分", 0),
            record.get("投递状态", "待投递"),
            record.get("录取状态", "待定"),
            record.get("岗位类型", "社招"),
            record.get("投递简历", ""),
            record.get("报告链接", ""),
            record.get("创建时间", "")
        ])

    payload = {"fields": fields, "rows": rows}

    # Write JSON to local file (lark-cli requires relative path for @file)
    tmp_path = Path("_bitable_batch.json")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    cmd = [
        lark_cli, "base", "+record-batch-create",
        "--base-token", app_token,
        "--table-id", table_id,
        "--json", "@_bitable_batch.json",
        "--as", "user"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=60,
            shell=True if os.name == 'nt' else False,
        )
        tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            print(f"[Bitable] 添加失败 (exit={result.returncode}): {result.stderr}")
            return None

        stdout = result.stdout.strip() if result.stdout else ""
        if not stdout:
            print("[Bitable] 添加失败: lark-cli 无输出")
            return None
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"[Bitable] 解析响应失败: {stdout[:200]}")
            return None
        if data.get('ok'):
            return data.get('data', {})
        print(f"[Bitable] 添加失败: {data.get('error', {}).get('message', data)}")
        return None

    except Exception as e:
        print(f"[Bitable] 添加异常: {e}")
        return None


def add_jobs_to_bitable(jobs: List[Dict], profile_name: str, report_url: str = None) -> Optional[int]:
    """添加岗位到多维表格

    Args:
        jobs: 岗位列表
        profile_name: 简历标识
        report_url: 报告链接

    Returns:
        添加数量
    """
    config = load_feishu_config()
    if not config.get('enabled', False):
        print("[Bitable] 多维表格未启用")
        return None

    app_token = config.get('bitable_token')
    table_id = config.get('bitable_table_id')

    if not all([app_token, table_id]):
        print("[Bitable] 配置不完整，跳过添加")
        return None

    _JOB_TYPE_CN = {"campus": "校招", "internship": "实习", "social": "社招"}

    # 构建记录
    records = []
    for job in jobs:
        jt = job.get("job_type", "社招")
        record = {
            "岗位标题": job.get("title", ""),
            "公司": job.get("company", ""),
            "岗位链接": job.get("url", ""),
            "AI评分": job.get("score", 0),
            "投递状态": "待投递",
            "录取状态": "待定",
            "岗位类型": _JOB_TYPE_CN.get(jt, jt),
            "投递简历": profile_name,
            "报告链接": report_url or "",
            "创建时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        records.append(record)

    # 分批添加（每批最多500条）
    batch_size = 100
    total_added = 0

    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        result = batch_add_records(app_token, table_id, batch)
        if result:
            added = result.get('total', len(batch))
            total_added += added
            print(f"[Bitable] 批次 {i//batch_size + 1}: 添加 {added} 条记录")
        time.sleep(0.5)  # 避免频率限制

    print(f"[Bitable] 共添加 {total_added} 条记录")
    return total_added


def batch_import_from_report(report_path: str, profile_name: str, report_url: str = None) -> Optional[int]:
    """从报告文件导入岗位到多维表格

    Args:
        report_path: 报告文件路径
        profile_name: 简历标识
        report_url: 报告链接

    Returns:
        导入数量
    """
    import re

    report_file = Path(report_path)
    if not report_file.exists():
        print(f"[Bitable] 报告文件不存在: {report_path}")
        return None

    content = report_file.read_text(encoding='utf-8')

    # 解析报告中的岗位信息
    jobs = []

    # 匹配岗位块：### N. 公司－标题 [🟢/🟡/🔴] Score: 分数
    pattern = r'### \d+\. (.+?) \[(?:🟢|🟡|🔴|Green|Yellow|Red)\] Score: (\d+)'
    matches = re.findall(pattern, content)

    for match in matches:
        title_raw = match[0].strip()
        score = int(match[1])

        # 标题格式: "公司－岗位名"，拆出公司
        if '－' in title_raw:
            company, title = title_raw.split('－', 1)
            company = company.strip()
            title = title.strip()
        else:
            title = title_raw
            # Fallback: 从表格行提取公司
            cm = re.search(rf'### \d+\. {re.escape(title_raw)}.*?\| Company \| (.+?) \|', content, re.DOTALL)
            company = cm.group(1).strip() if cm else ""

        # 提取链接
        link_match = re.search(rf'### \d+\. {re.escape(title_raw)}.*?\*\*Link\*\*: \[(.+?)\]\((.+?)\)', content, re.DOTALL)
        url = link_match.group(2) if link_match else ""

        # 提取岗位类型
        jt = "社招"
        jt_match = re.search(rf'### \d+\. {re.escape(title_raw)}.*?岗位类型.*?\|\s*(.+?)\s*\|', content, re.DOTALL)
        if jt_match:
            jt = jt_match.group(1).strip()

        jobs.append({
            "title": title,
            "company": company,
            "url": url,
            "score": score,
            "job_type": jt,
        })

    if not jobs:
        print("[Bitable] 未找到岗位信息")
        return 0

    # 添加到多维表格
    return add_jobs_to_bitable(jobs, profile_name, report_url)
