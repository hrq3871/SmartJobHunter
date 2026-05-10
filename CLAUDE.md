# SmartJobHunter AI 操作规范

本文档是 Claude 在本项目中的项目级运行规则。它必须说明“整体架构靠什么运行、什么时候用哪个 Skill/Prompt、哪些命令必须执行”。完整内部设计见 `docs/smartjobhunter-agent-design.md`；单次任务执行手册见 `.claude/skills/jobhunter/skill.md`。

`CLAUDE.md` 和 `AGENTS.md` 必须表达同一套规则。更新其中一个文件时，必须同步另一个文件，并运行 instruction alignment 相关评估。

## 文档分层

```text
+----------------------------------------------+----------------------------------------------+
| 文件/目录                                     | 用途                                         |
+----------------------------------------------+----------------------------------------------+
| README.md / README_CN.md                      | 对外介绍、快速开始、常用命令                 |
| CLAUDE.md / AGENTS.md                         | AI 项目级规则、运行架构、Skill/Prompt 路由   |
| docs/smartjobhunter-agent-design.md           | 内部完整 Agent 架构和评估设计                |
| evals/evaluation-grader-rubrics.md            | Eval grader 判分规则                         |
| evals/eval-case-feedback-loop.md              | 真实失败/反馈回流为 eval case 的流程         |
| docs/plans/                                   | 历史计划，不作为当前运行规则                 |
| .claude/skills/jobhunter/skill.md             | JobHunter Agent 具体执行手册                 |
| .claude/skills/jobhunter/profile.md           | 候选人画像子流程                             |
| .claude/skills/jobhunter/match.md             | 候选人-岗位匹配子流程                        |
| .claude/skills/jobhunter/prompts/*.md         | 具体 AI 判断提示词                           |
| .claude/skills/jobhunter/tools/*.md           | Python 工具入口和命令说明                    |
| evals/regression/jobhunter_core.yaml          | 默认 regression eval 数据集                  |
| evals/capability/jobhunter_hard_cases.yaml    | 能力边界评估数据集                           |
| src/                                          | Python 抓取、过滤、报告、评估工具层          |
| logs/strategy_tasks/                          | 策略任务，给 Agent 分析                      |
| logs/crawler_evidence/                        | 页面、DOM、网络、截图证据                    |
| output/{YYYY-MM-DD}/                          | 正式巡检报告和投递包                         |
| output/evals/                                 | 本地 eval 运行产物，不提交 Git               |
+----------------------------------------------+----------------------------------------------+
```

维护原则：`docs/` 只放全局设计、AI 自动维护记录和历史计划；eval 运行体系直接使用的规则、rubric、反馈闭环放在 `evals/`，和评测集一起维护。

## 运行架构

SmartJobHunter 不是只靠 `CLAUDE.md` 运行，也不是只靠 Skills 运行。运行保障来自四层：

```text
项目级规则：CLAUDE.md / AGENTS.md
  -> 执行手册：.claude/skills/jobhunter/skill.md
  -> 子流程与 Prompt：profile.md / match.md / prompts/*.md
  -> Python 工具层：src.cli / crawler_factory / filters / matching / health_monitor / evaluation
```

分工：

- `CLAUDE.md` / `AGENTS.md`：告诉 AI 项目边界、文档分层、什么时候用哪个 Skill/Prompt、哪些验证必须跑。
- `.claude/skills/jobhunter/skill.md`：告诉 AI 单次求职巡检按什么状态机执行。
- `profile.md` / `match.md`：把候选人画像和岗位匹配拆成可复用子流程。
- `prompts/*.md`：定义每类 AI 判断的输入、原则和输出格式。
- `src/`：执行可复现的抓取、过滤、fallback 评分、报告、投递包、评估。

## Skill / Prompt 路由

```text
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 用户意图/任务                         | 必须使用                                     | 同步使用                                     |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 项目介绍、安装、普通命令查询           | README.md / README_CN.md                      | 不进入完整状态机                             |
| 运行完整求职巡检                       | .claude/skills/jobhunter/skill.md             | python -m src.cli                            |
| 分析简历、建立候选人画像               | profile.md                                    | prompts/build_candidate_profile.md           |
| 简历需要更深 HR 式能力拆解             | prompts/analyze_resume.md                     | resume_parser 读取的简历原文                 |
| 判断单个岗位是否适合                   | match.md                                      | prompts/analyze_job.md + match_candidate_job.md |
| 过滤标题党或关键词噪音岗位             | prompts/semantic_filter.md                    | src.matching.match_job_intent                |
| 对齐旧评分/更细评分拆解                | prompts/evaluate.md                           | src.matching.evaluate_job_fit                |
| 新链接、链接变化、抓取失败、反爬        | prompts/analyze_crawler_strategy.md           | logs/strategy_tasks + logs/crawler_evidence  |
| 生成或复核报告                         | prompts/report.md                             | output/{YYYY-MM-DD}/                         |
| 评估失败或 instruction_drift           | evals/evaluation-grader-rubrics.md            | transcripts/<case_id>.jsonl                  |
| 真实失败样本回流                       | evals/eval-case-feedback-loop.md              | evals/candidates/                            |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
```

规则：

- 用户请求运行巡检、找岗位、生成报告或投递包时，先读 `.claude/skills/jobhunter/skill.md`。
- 用户请求分析简历或岗位适配时，先走 `profile.md` / `match.md`，不要直接套产品经理示例。
- 策略问题必须读取 evidence；不要让 Python 假装“AI 自动理解网站”。
- Python fallback 是粗筛和测试保障；最终语义判断由当前 Claude/Codex Agent 依据 prompt 完成。

## 状态机

完整状态机定义在 `.claude/skills/jobhunter/skill.md`，状态名必须保持一致：

```text
INIT -> LOADED -> STRATEGY_INSPECTED -> CRAWLED -> FILTERED -> EVALUATED -> URL_VALIDATED -> REPORTED -> PACKAGED -> DONE
```

状态与工具/Prompt 对应：

```text
+--------------------+----------------------------------------------+----------------------------------------------+
| 状态               | Python / 数据入口                            | Agent 使用                                   |
+--------------------+----------------------------------------------+----------------------------------------------+
| INIT               | config/companies.yaml, profiles, resumes     | tools/load_config.md                         |
| LOADED             | resume_parser, profile fields                | profile.md, build_candidate_profile.md       |
| STRATEGY_INSPECTED | health_monitor, crawler_evidence             | analyze_crawler_strategy.md                  |
| CRAWLED            | crawler_factory                              | tools/crawl.md                               |
| FILTERED           | filters, matching.match_job_intent           | semantic_filter.md                           |
| EVALUATED          | matching.evaluate_job_fit                    | match.md, analyze_job.md, match_candidate_job.md, evaluate.md |
| URL_VALIDATED      | JobHunter._filter_live_urls                  | 检查空链接/404 不进报告                      |
| REPORTED           | JobHunter.generate_report                    | report.md                                    |
| PACKAGED           | JobHunter.generate_application_package        | 检查 Top 3 Cover Letter 证据闭环             |
| DONE               | filters.update_memory                         | tools/update_memory.md                       |
+--------------------+----------------------------------------------+----------------------------------------------+
```

## 职责边界

Python 负责：

- 官网抓取、文本抽取、确定性过滤、fallback 粗评分。
- URL 校验、报告落盘、投递包落盘、memory 更新。
- 策略巡检、证据采集、评估 harness。

当前 Claude/Codex Agent 负责：

- 从简历和求职目标构建候选人画像。
- 分析岗位画像和语义匹配。
- 复核 Python fallback 的高风险结果。
- 根据证据包判断和固化抓取策略。
- 修复代码、配置、prompt 或文档后运行验证。

Python 不调用外部 LLM API。需要 AI 判断的部分由当前 Claude/Codex Agent 在会话中执行。

## 必须运行评估的情况

修改以下内容后必须运行 regression eval。默认 regression 数据集是 `evals/regression/jobhunter_core.yaml`：

- 抓取策略
- 岗位过滤
- 匹配评分
- 报告生成
- Top 3 投递包
- URL 校验
- memory 更新
- `CLAUDE.md`、`AGENTS.md`、`.claude/skills/jobhunter/skill.md`
- `.claude/skills/jobhunter/profile.md`、`.claude/skills/jobhunter/match.md`
- `.claude/skills/jobhunter/prompts/*`
- `src/evaluation.py`、`src/eval_graders.py`、`src/eval_transcript.py`

命令：

```powershell
python -m src.evaluation --fail-under 1.0
```

大改、发布前或稳定性复核时运行：

```powershell
python -m src.evaluation --trials 3 --fail-under 1.0
```

能力边界诊断时运行：

```powershell
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

评估输出：

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/
├── agent_eval_results.json
├── agent_eval_report.md
├── transcripts/<case_id>.jsonl
├── artifacts/
└── wf/
```

`output/evals/` 是本地运行产物，不提交 Git。评估默认使用 Code graders 做确定性判分；model/human grader 只保留 schema，离线 runner 默认 skipped。

## 评估失败处理

1. 打开 `agent_eval_report.md` 看失败 case。
2. 打开 `transcripts/<case_id>.jsonl` 回放执行过程。
3. 根据 `bad_case_attribution` 判断问题归属：
   - `crawler_strategy`
   - `matching_filtering`
   - `recommendation_quality`
   - `output_quality`
   - `instruction_drift`
4. 修复后重新运行评估，直到通过。
5. 如果失败来自真实用户或真实巡检，按 `evals/eval-case-feedback-loop.md` 沉淀为候选 eval case。

## 常用命令

```powershell
# 完整巡检
python -m src.cli
python -m src.cli -t social
python -m src.cli -t internship
python -m src.cli -t campus
python -m src.cli -p "意向名称"

# 爬虫管理
python -m src.crawler_factory --list
python -m src.crawler_factory --test <id>
python -m src.crawler_factory --crawl <id> --keyword "<关键词>" --max-jobs 10

# 策略巡检
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type social
python -m src.health_monitor --inspect-company <id> --keyword "<关键词>"

# 单公司策略验证
python tests/test_all_crawlers.py --company <company_id> --keyword "<关键词>" --max-jobs 3

# 飞书推送开关
python -m src.scheduler --feishu-push status
python -m src.scheduler --feishu-push on
python -m src.scheduler --feishu-push off
```

## Git 和文件规则

- 禁止直接 push 到 `main`。
- 功能分支可以推送到远程，合并到 main 前必须等待用户确认。
- 不提交 `config/agent.yaml`，只提交 `config/agent.sample.yaml`。
- 不提交 `output/`、`logs/` 运行产物。
- `docs/optimization-log.md` 是本地私有文档，不提交。
- 禁止使用 `rm` 删除文件；需要删除时使用 PowerShell `Remove-Item -LiteralPath ... -Force`。
- 不得回滚用户未要求回滚的改动。

## 飞书推送边界

飞书推送由 `config/agent.yaml` 的 `feishu.enabled` 控制。

`python -m src.scheduler --push` 指 Git commit/push 到远程仓库，不是飞书推送。

飞书推送链路：

1. `generate_report()` 写入 `output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md`。
2. `src.feishu_push.push_to_feishu()` 推送 Wiki。
3. `src.feishu_bitable.add_jobs_to_bitable()` 写入多维表格。

## 规范演进

出现以下情况时，必须更新相关文档：

- 用户指出当前规则不清楚或不正确。
- JobHunter 状态机变化。
- 目录结构、输出路径、评估命令变化。
- 新增 prompt、工具、Python 主流程或数据来源。
- 真实失败样本暴露规则缺口。

更新位置：

- 详细设计：`docs/smartjobhunter-agent-design.md`
- 执行架构：`.claude/skills/jobhunter/skill.md`
- 项目级规则：`CLAUDE.md` 和 `AGENTS.md`
- 外部介绍：`README.md` / `README_CN.md`
