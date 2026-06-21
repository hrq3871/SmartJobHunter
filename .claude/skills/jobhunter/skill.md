---
name: jobhunter
description: Use when the user asks to run SmartJobHunter, find or evaluate jobs, analyze resumes, generate reports or application packages, inspect crawler evidence, or fix company crawler strategies.
---

# JobHunter Skillmap

本文件是 SmartJobHunter 的 Skillmap/路由索引，不是完整 Agent 定义。完整 Agent 定义由仓库根目录的 `CLAUDE.md` / `AGENTS.md` 自动加载并保障；本 Skill 只负责在触发时快速指向对应子流程、Prompt 和 Python 工具。

## 什么时候用

用户表达以下意图时加载本 Skill：

- 运行求职巡检、找岗位、今天有什么岗位。
- 分析简历、建立候选人画像。
- 判断岗位是否适合。
- 生成报告、生成 Top 3 投递包、复核 Cover Letter。
- 公司官网链接变化、抓取失败、需要分析 `logs/crawler_evidence/`。
- eval 失败、instruction_drift、需要回放 `transcripts/<case_id>.jsonl`。

不用于项目介绍、安装说明、公开能力说明；这些优先看 README。

## 路由表

```text
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 场景                                 | 读取/使用                                    | 输出或命令                                   |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 完整巡检                             | CLAUDE.md / AGENTS.md                         | python -m src.cli                            |
| 候选人画像                           | profile.md + prompts/build_candidate_profile.md | profiles/<profile_id>.md                  |
| HR 式简历深挖                        | prompts/analyze_resume.md                     | ability profile / highlights / gaps          |
| 单岗位匹配                           | match.md + prompts/analyze_job.md + prompts/match_candidate_job.md | match decision         |
| 语义过滤                             | prompts/semantic_filter.md                    | should_keep / concerns / evidence            |
| 兼容评分拆解                         | prompts/evaluate.md                           | score + scoring_breakdown                    |
| 抓取策略分析                         | prompts/analyze_crawler_strategy.md           | strategy type + patch plan + verification    |
| 批量策略修复                         | .claude/agents/crawler-strategy-inspector.md  | 单个子 Agent 串行处理全部 strategy tasks     |
| 报告生成/复核                        | prompts/report.md                             | output/{YYYY-MM-DD}/                         |
| 配置读取                             | tools/load_config.md                          | profiles / companies / agent config          |
| 抓取                                 | tools/crawl.md                                | raw jobs                                     |
| 过滤                                 | tools/filter.md                               | filtered jobs                                |
| 更新 memory                          | tools/update_memory.md                        | memory/seen_jobs.md                          |
| eval 失败排查                        | evals/evaluation-grader-rubrics.md            | agent_eval_report.md + transcripts           |
| 真实失败回流                         | evals/eval-case-feedback-loop.md              | evals/candidates/                            |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
```

## 状态机锚点

完整状态机在 `CLAUDE.md` / `AGENTS.md` 中定义；本 Skill 只保留触发和检查锚点，避免和 Agent 定义重复漂移。

```text
INIT -> LOADED -> STRATEGY_INSPECTED -> CRAWLED -> FILTERED -> EVALUATED -> URL_VALIDATED -> REPORTED -> PACKAGED -> DONE
```

关键状态：

- `STRATEGY_INSPECTED`：运行策略巡检，读取 strategy task 和 evidence。
- `URL_VALIDATED`：报告前必须过滤空链接、404、不可访问链接。
- `PACKAGED`：为 Top 3 岗位生成投递包，Cover Letter 必须结合 JD 证据和简历证据。

`config/resume_intents.yaml` 中的 `search_intent` 只表示搜索关键词和岗位类型，不是候选人画像。上传简历时不得创建正式 profile；当前 Agent 必须读取完整简历后生成 `profiles/<profile_id>.md`。简历仅支持 PDF、Markdown、TXT，DOCX 和图片不支持。

岗位 URL 在任何报告或 Agent 回复中都必须完整显示并可点击；禁止使用切片、摘要或省略号截断 URL。

## 常用命令

```powershell
# 完整巡检
python -m src.cli
python -m src.cli -t social
python -m src.cli -t internship
python -m src.cli -t campus
python -m src.cli -p "意向名称"

# 策略巡检
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type social
python -m src.health_monitor --inspect-company <company_id> --keyword "<关键词>"

# 抓取与验证
python -m src.crawler_factory --crawl <company_id> --keyword "<关键词>" --max-jobs 10
python tests/test_all_crawlers.py --company <company_id> --keyword "<关键词>" --max-jobs 3

# 飞书推送开关
python -m src.scheduler --feishu-push status
python -m src.scheduler --feishu-push on
python -m src.scheduler --feishu-push off

# eval
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

默认 regression 数据集是 `evals/regression/jobhunter_core.yaml`。eval 输出写入 `output/evals/{YYYY-MM-DD}/...`，正式巡检报告写入 `output/{YYYY-MM-DD}/...`。

## Eval 排查速记

- 先看 `agent_eval_report.md`。
- 再看 `transcripts/<case_id>.jsonl` 回放轨迹。
- 根据 `bad_case_attribution` 定位到 `crawler_strategy`、`matching_filtering`、`recommendation_quality`、`output_quality` 或 `instruction_drift`。
- Code graders 是默认启用的确定性判分；model/human grader 目前只保留 schema。

## 维护规则

- 完整流程、职责边界、状态机细节只改 `CLAUDE.md` / `AGENTS.md`。
- 本 Skill 只维护触发词、路由表、命令索引和 eval 锚点。
- 新增 prompt/tool 时，同步更新本路由表和 `docs/smartjobhunter-agent-design.md`。
