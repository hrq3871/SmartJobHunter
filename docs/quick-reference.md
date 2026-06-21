# SmartJobHunter 快速参考

> 可放入全局 CLAUDE.md 或项目 AGENTS.md 作为导入提示语。

---

## SmartJobHunter 可用能力

当用户提到求职巡检、岗位抓取、简历分析、投递准备或策略修复时，你作为 SmartJobHunter Agent 执行。

### 自然语言触发

| 用户说 | 执行内容 |
|--------|----------|
| 「运行巡检」「今天有什么岗位」 | 完整状态机巡检：INIT → 策略检查 → 抓取 → 过滤 → 评估 → 报告 → 投递包 |
| 「分析我的简历」「建立画像」 | 读取 `profiles/` + `resumes/`，生成候选人画像 |
| 「这个岗位适合我吗」 | 岗位-候选人匹配：JD 分析 → 匹配打分 → 推荐等级 |
| 「修复 XX 抓取」「策略坏了」 | 读 `logs/crawler_evidence/`，判断策略类型，改 `config/companies.yaml` 或 `src/site_strategies/` |
| 「批量修复策略」 | 委派 `crawler-strategy-inspector` 子 Agent 串行处理所有 pending 任务 |
| 「生成报告」「复核报告」 | 检查 `output/{YYYY-MM-DD}/` 下的报告质量 |
| 「生成投递包」「写 Cover Letter」 | Top 3 岗位 + 定制化求职材料 |
| 「运行评估」 | 执行 `python -m src.evaluation --fail-under 1.0` |
| 「帮我设每天 9 点巡检」 | Claude Code 内置 cron 设定时任务 |

### CLI 命令

```bash
# 巡检
python -m src.cli                                  # 完整社招巡检
python -m src.cli -t campus                        # 校招
python -m src.cli -t internship                    # 实习
python -m src.cli -p "意向名称"                     # 按 profile 巡检

# 爬虫
python -m src.crawler_factory --list               # 列出爬虫
python -m src.crawler_factory --crawl <id> --keyword "关键词" --max-jobs 10
python tests/test_all_crawlers.py --company <id> --keyword "关键词" --max-jobs 3

# 策略健康
python -m src.health_monitor --inspect-strategies --keyword "关键词"
python -m src.health_monitor --inspect-company <id>

# 调度
python -m src.scheduler --schedule                 # 定时模式（读 agent.yaml）
python -m src.scheduler --run                      # 立即巡检
python -m src.scheduler --feishu-push on/off/status

# 评估
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

### Web 控制台（仅本地 127.0.0.1）

```bash
python -m uvicorn src.web_ui:app --host 127.0.0.1 --port 8080
```

五个管理 Tab：简历与巡检 / 策略健康 / 公司配置 / 飞书推送 / 定时任务。

### 定时任务

用 Claude Code 内置 cron：`设个每天早上 9 点跑 python -m src.scheduler --schedule 的持久定时任务`。命令自动读取 `config/agent.yaml` 里的 schedule 配置。

### 关键边界

- 禁止 `rm` 删除文件 → 用 PowerShell `Remove-Item -LiteralPath ... -Force`
- 禁止直接 push main → 功能分支 → 等用户确认合并
- 不提交 `config/agent.yaml`、`output/`、`logs/`
- Python 不调外部 LLM API → AI 判断由当前 Agent 在会话中完成
- Web 控制台仅本地使用，不对外暴露
