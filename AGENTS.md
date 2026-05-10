# SmartJobHunter AI 操作规范

本文档是 Codex/Agent 在本项目中的项目级规则。完整系统设计见 `docs/smartjobhunter-agent-design.md`；具体求职巡检执行架构见 `.claude/skills/jobhunter/skill.md`；README 只保留对外介绍和常用入口。

`CLAUDE.md` 和 `AGENTS.md` 必须表达同一套规则。更新其中一个文件时，必须同步另一个文件，并运行 instruction alignment 相关评估。

## 文档分层

```text
+--------------------------------------+-----------------------------------------+
| 文件                                 | 用途                                    |
+--------------------------------------+-----------------------------------------+
| README.md / README_CN.md              | 对外介绍、快速开始、常用命令            |
| docs/smartjobhunter-agent-design.md   | 内部完整设计和架构说明                  |
| CLAUDE.md / AGENTS.md                 | AI 项目级规则和操作边界                 |
| .claude/skills/jobhunter/skill.md     | JobHunter Agent 具体执行流程            |
| .claude/skills/jobhunter/prompts/     | 候选人画像、岗位画像、匹配判断 prompts |
| src/evaluation.py                     | 机器评估 harness                        |
+--------------------------------------+-----------------------------------------+
```

## Skill 使用规则

当用户请求运行求职巡检、查找岗位、分析岗位是否适合、生成报告或投递包时，使用 `.claude/skills/jobhunter/skill.md` 作为具体流程说明。

具体边界：

- 完整巡检：按 jobhunter skill 的状态机执行。
- 构建候选人画像：使用 `.claude/skills/jobhunter/prompts/build_candidate_profile.md`。
- 分析岗位画像：使用 `.claude/skills/jobhunter/prompts/analyze_job.md`。
- 判断候选人与岗位匹配：使用 `.claude/skills/jobhunter/prompts/match_candidate_job.md`。
- 生成报告前：必须完成 `URL_VALIDATED`。
- 生成投递包：必须进入 `PACKAGED`。
- 修改抓取、过滤、评分、报告、投递包、Agent 文档或 prompt 后：必须运行评估。

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
- 修复代码、配置或文档后运行验证。

Python 不调用外部 LLM API。需要 AI 判断的部分由当前 Claude/Codex Agent 在会话中执行。

## 核心状态机

完整状态机定义在 `.claude/skills/jobhunter/skill.md`。状态名必须保持一致：

```text
INIT -> LOADED -> STRATEGY_INSPECTED -> CRAWLED -> FILTERED -> EVALUATED -> URL_VALIDATED -> REPORTED -> PACKAGED -> DONE
```

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

`output/evals/` 是本地运行产物，不提交 Git。

巡检正式报告输出在 `output/{YYYY-MM-DD}/`。评估默认使用 Code graders 做确定性判分；model/human grader 只保留 schema，离线 runner 默认 skipped。

## 评估失败处理

评估失败时：

1. 打开 `agent_eval_report.md` 看失败 case。
2. 打开 `transcripts/<case_id>.jsonl` 回放执行过程。
3. 根据 `bad_case_attribution` 判断问题归属：
   - `crawler_strategy`
   - `matching_filtering`
   - `recommendation_quality`
   - `output_quality`
   - `instruction_drift`
4. 修复后重新运行评估，直到通过。
5. 如果失败来自真实用户或真实巡检，应按 `docs/eval-case-feedback-loop.md` 沉淀为候选 eval case。

## 常用命令

```powershell
# 立即执行巡检
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
- 新增 prompt、工具或数据来源。
- 真实失败样本暴露规则缺口。

更新位置：

- 项目级规则：`CLAUDE.md` 和 `AGENTS.md`
- 执行架构：`.claude/skills/jobhunter/skill.md`
- 详细设计：`docs/smartjobhunter-agent-design.md`
- 外部介绍：`README.md` / `README_CN.md`
