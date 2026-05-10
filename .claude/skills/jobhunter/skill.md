---
name: jobhunter
description: 智能求职巡检 Agent
user_invocable: true
---

# SmartJobHunter Agent

当用户请求“运行巡检”“找岗位”“分析岗位是否适合”“生成报告”“生成投递包”或“修复公司抓取策略”时，使用本 skill。项目级规则见 `CLAUDE.md` / `AGENTS.md`；完整内部设计见 `docs/smartjobhunter-agent-design.md`。

## 目录结构

```text
SmartJobHunter/
├── README.md / README_CN.md              # 对外介绍、安装和常用命令
├── CLAUDE.md / AGENTS.md                 # AI 项目级规则和 Skill/Prompt 路由
├── docs/
│   ├── smartjobhunter-agent-design.md    # 内部完整 Agent 架构
│   ├── evaluation-grader-rubrics.md      # eval grader 判分规则
│   └── eval-case-feedback-loop.md        # 真实失败回流 eval case 的流程
├── config/
│   ├── companies.yaml                    # 公司官网链接和抓取策略
│   ├── agent.sample.yaml                 # 可提交示例配置
│   └── agent.yaml                        # 本地私有配置，不提交
├── profiles/                             # 求职意向，文件名作为 profile_id
├── resumes/                              # 简历文件
├── memory/seen_jobs.md                   # 已处理岗位记忆
├── logs/
│   ├── strategy_tasks/                   # 策略任务，给 Agent 读取
│   └── crawler_evidence/                 # 页面、DOM、网络、截图证据
├── output/{YYYY-MM-DD}/                  # 正式报告和投递包
├── output/evals/                         # 本地评估产物，不提交 Git
├── evals/
│   ├── regression/jobhunter_core.yaml    # 默认 regression eval
│   └── capability/jobhunter_hard_cases.yaml
├── src/                                  # Python 工具层
└── .claude/skills/jobhunter/
    ├── skill.md                          # 本执行手册
    ├── profile.md                        # 候选人画像子流程
    ├── match.md                          # 候选人-岗位匹配子流程
    ├── prompts/
    │   ├── analyze_crawler_strategy.md   # 读取 evidence，判断抓取策略
    │   ├── analyze_resume.md             # HR 式简历深挖
    │   ├── build_candidate_profile.md    # 结构化候选人画像
    │   ├── semantic_filter.md            # 语义意向过滤
    │   ├── analyze_job.md                # JD -> 岗位画像
    │   ├── match_candidate_job.md        # 候选人-岗位最终匹配
    │   ├── evaluate.md                   # 旧版/兼容深度评分 prompt
    │   └── report.md                     # 报告生成和复核
    └── tools/
        ├── load_config.md                # 读取配置、profile、简历、公司
        ├── crawl.md                      # 抓取和策略路由说明
        ├── filter.md                     # 时间、去重、清洗过滤说明
        └── update_memory.md              # 更新 seen_jobs.md
```

目录结构或重要文件变化时，必须同步更新本节、`docs/smartjobhunter-agent-design.md`、`CLAUDE.md` 和 `AGENTS.md`。

## 运行保障

本项目不是只靠 `CLAUDE.md` 或只靠 Skills 运行。实际运行链路是：

```text
CLAUDE.md / AGENTS.md
  -> .claude/skills/jobhunter/skill.md
  -> profile.md / match.md / prompts/*.md
  -> src/*.py
  -> output / logs / memory / evals
```

分工：

- `CLAUDE.md` / `AGENTS.md`：项目级规则和路由。
- 本 skill：单次任务状态机和命令。
- `profile.md` / `match.md`：可复用子流程。
- `prompts/*.md`：具体 AI 判断输入/输出。
- Python：可复现工具执行和 fallback。

## 触发方式

用户说以下意图时，使用本 skill：

- “运行巡检”
- “今天有什么岗位”
- “帮我看看有没有适合我的岗位”
- “分析这个岗位适不适合我”
- “生成报告”
- “生成投递包”
- “修复某家公司爬虫/策略”
- “评估这次报告质量”

如果用户只是问项目介绍、安装或公开能力，优先参考 README，不必进入完整状态机。

## Skill / Prompt 路由

```text
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 场景                                 | 使用                                         | 产物/入口                                    |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 完整巡检                             | 本 skill                                     | python -m src.cli                            |
| 候选人画像                           | profile.md + build_candidate_profile.md       | candidate_profile JSON                       |
| 简历深挖                             | analyze_resume.md                             | ability profile / highlights / gaps          |
| 单岗位适配                           | match.md + analyze_job.md + match_candidate_job.md | job_profile + match decision            |
| 语义过滤                             | semantic_filter.md                            | should_keep / concerns / evidence            |
| 兼容深度评分                         | evaluate.md                                   | score + scoring_breakdown                    |
| 抓取策略分析                         | analyze_crawler_strategy.md                   | strategy type + patch plan + verification    |
| 报告生成/复核                        | report.md                                     | Markdown report + Top 3 package requirement  |
| 配置读取                             | tools/load_config.md                          | profiles / companies / agent config          |
| 抓取                                 | tools/crawl.md                                | raw jobs                                     |
| 过滤                                 | tools/filter.md                               | filtered jobs                                |
| 更新 memory                          | tools/update_memory.md                        | memory/seen_jobs.md                          |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
```

## 职责

负责：

- 按状态机执行官网岗位巡检。
- 根据 profile 和简历构建候选人画像。
- 根据 JD 证据判断岗位画像和匹配度。
- 复核 Python fallback 的过滤和评分结果。
- 分析策略任务和证据包，固化可复用抓取策略。
- 生成或复核报告和 Top 3 投递包。
- 运行评估，确保流程没有退化。

不负责：

- 不直接替用户投递。
- 不绕过登录、验证码或强反爬。
- 不提交真实 `config/agent.yaml`。
- 不把 Python fallback 分数当成最终结论。
- 不只靠关键词决定岗位是否保留。

## 工作流程

```text
INIT
  -> LOADED
  -> STRATEGY_INSPECTED
  -> CRAWLED
  -> FILTERED
  -> EVALUATED
  -> URL_VALIDATED
  -> REPORTED
  -> PACKAGED
  -> DONE
```

### INIT

目标：初始化上下文。

动作：

1. 读取 `config/companies.yaml`。
2. 读取 `profiles/*.md`。
3. 读取对应 `resumes/*`。
4. 读取 `memory/seen_jobs.md`。
5. 如需飞书推送，读取本地 `config/agent.yaml`。

使用说明：`tools/load_config.md`。

完成条件：

- profile、resume、companies、seen memory 已加载。
- 明确本次 job type：`social`、`campus`、`internship` 或全部。

### LOADED

目标：确认求职目标、关键词和候选人画像。

动作：

1. 不要默认套用产品经理；必须读取 profile 中的 `target_roles`、`must_have`、`avoid`、`keywords`。
2. 如果 profile 目标过宽，选择多个代表关键词抽样。
3. 使用 `profile.md` 和 `prompts/build_candidate_profile.md` 生成 candidate_profile。
4. 如果用户要求“深度分析简历”或简历证据不足，再使用 `prompts/analyze_resume.md`。

完成条件：

- 明确本轮关键词。
- 明确候选人能力证据和缺失项。
- 明确哪些岗位应拒绝。

### STRATEGY_INSPECTED

目标：巡检公司官网链接和抓取策略。

命令：

```powershell
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type <social|campus|internship>
python -m src.health_monitor --inspect-company <company_id> --keyword "<关键词>"
```

对 `unknown/new/changed/failed` 读取：

- `logs/strategy_tasks/.../task.json`
- `logs/crawler_evidence/.../evidence.json`
- `logs/crawler_evidence/.../network.json`
- `logs/crawler_evidence/.../page.html`
- `logs/crawler_evidence/.../page.txt`
- `logs/crawler_evidence/.../page.png`

使用 `prompts/analyze_crawler_strategy.md` 判断：

- `config_intercept`
- `config_dom`
- `legacy_python`
- `custom_python`
- `browser_operation`
- `unsupported`

修改策略后验证：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "<关键词>" --max-jobs 3
```

完成条件：

- 可抓公司进入下一步。
- 阻塞公司记录原因并跳过，不阻塞其他公司。

### CRAWLED

目标：抓取岗位。

命令：

```powershell
python -m src.crawler_factory --crawl <company_id> --keyword "<关键词>" --max-jobs 10
```

使用说明：`tools/crawl.md`。

完成条件：

- 获得岗位列表，或确认本轮没有新岗位。
- 如果 CLI 输出为空，不要直接判断“没有合适岗位”；需抽查原始抓取样本和关键词。

### FILTERED

目标：过滤岗位。

```text
raw jobs -> filter_by_time -> dedup -> clean_data -> match_job_intent -> Agent semantic review
```

使用说明：

- `tools/filter.md`
- `prompts/semantic_filter.md`

规则：

- 时间过滤和去重由 Python 执行。
- 语义保留由 Agent 复核。
- 标题含 AI 但本质是工程、运营、销售、标注的岗位应拒绝或降权。
- 岗位职责与 profile 不闭环时，不进入强推荐。

### EVALUATED

目标：构建岗位画像和最终匹配判断。

默认使用：

- `match.md`
- `prompts/analyze_job.md`
- `prompts/match_candidate_job.md`

兼容/辅助使用：

- `prompts/evaluate.md`：当需要旧版深度评分格式、评分拆解或对齐 Python fallback 时使用。
- `src.matching.evaluate_job_fit()`：无 Agent prompt 时的 deterministic fallback。

输出必须包含：

- JD 证据
- 简历证据
- 匹配分数
- 推荐等级
- 缺失技能
- 风险信号

### URL_VALIDATED

目标：报告前校验岗位链接。

Python 入口：`JobHunter._filter_live_urls()`。

规则：

- 空链接、404、不可访问链接不得进入报告或飞书。
- 链接校验后无岗位时，停止报告生成并说明原因。

### REPORTED

目标：生成日期归档报告。

路径：

```text
output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md
```

使用 `prompts/report.md` 复核：

- recommendation 是否清楚。
- scoring_breakdown 是否存在。
- 链接是否都已校验可访问。
- 风险和行动建议是否明确。

飞书推送由 `config/agent.yaml` 控制：

```powershell
python -m src.scheduler --feishu-push status
python -m src.scheduler --feishu-push on
python -m src.scheduler --feishu-push off
```

注意：`python -m src.scheduler --push` 是 Git push，不是飞书推送。

### PACKAGED

目标：生成 Top 3 投递包。

路径：

```text
output/{YYYY-MM-DD}/application_packages/{profile_id}_{YYYYMMDD_HHMM}/
```

Cover Letter 必须结合：

- 公司
- 岗位
- JD 证据
- 简历证据
- 风险点

### DONE

目标：更新 memory 并汇报结果。

使用说明：`tools/update_memory.md`。

动作：

```text
filters.update_memory -> memory/seen_jobs.md
```

汇报必须包含：

- 报告路径
- 投递包路径
- 推荐岗位数量
- 被跳过或阻塞的公司
- 是否运行评估

## 可用命令

```powershell
# 完整巡检
python -m src.cli
python -m src.cli -t social
python -m src.cli -t internship
python -m src.cli -t campus
python -m src.cli -p "意向名称"

# 公司和爬虫
python -m src.crawler_factory --list
python -m src.crawler_factory --test <id>
python -m src.crawler_factory --crawl <id> --keyword "<关键词>" --max-jobs 10

# 策略巡检
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type social
python -m src.health_monitor --inspect-company <id> --keyword "<关键词>"

# 飞书推送开关
python -m src.scheduler --feishu-push status
python -m src.scheduler --feishu-push on
python -m src.scheduler --feishu-push off

# 评估
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

## 输出要求

报告：

```text
output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md
```

投递包：

```text
output/{YYYY-MM-DD}/application_packages/{profile_id}_{YYYYMMDD_HHMM}/
├── index.md
├── cover_letter_01_<company>.md
├── cover_letter_02_<company>.md
└── cover_letter_03_<company>.md
```

策略证据：

```text
logs/strategy_tasks/...
logs/crawler_evidence/...
```

评估：

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/
├── agent_eval_results.json
├── agent_eval_report.md
└── transcripts/<case_id>.jsonl
```

## 确认机制

以下操作需要用户确认：

- 合并到 main。
- 覆盖 main 或 force push。
- 提交真实凭证或修改 `config/agent.yaml`。
- 对登录、验证码、强反爬网站尝试绕过。
- 删除长期保留文件。
- 大规模重构公司策略或 profile schema。

## 错误处理

失败时：

1. 明确说明失败状态和原因。
2. 保留证据路径。
3. 判断是否可跳过该公司继续其他公司。
4. 如果是策略问题，生成或读取 strategy task。
5. 如果是评估失败，读取 `agent_eval_report.md` 和 `transcripts/<case_id>.jsonl`。
6. 修复后重新运行验证。

## 评估与监控

每次修改抓取、过滤、评分、报告、投递包、本 skill、`CLAUDE.md` 或 `AGENTS.md` 后，运行：

```powershell
python -m src.evaluation --fail-under 1.0
```

默认 regression 数据集是 `evals/regression/jobhunter_core.yaml`。

发布前或大改后运行：

```powershell
python -m src.evaluation --trials 3 --fail-under 1.0
```

评估归因：

```text
+------------------------+-----------------------------------------------+
| 归因模块               | 测试内容                                      |
+------------------------+-----------------------------------------------+
| crawler_strategy       | crawl / collect_evidence / blocked 路由       |
| matching_filtering     | 保留目标岗位，拒绝关键词噪音                  |
| recommendation_quality | 评分和推荐等级边界                            |
| output_quality         | URL 过滤、报告、Top 3 投递包、memory          |
| instruction_drift      | AGENTS / CLAUDE / jobhunter skill 一致性      |
+------------------------+-----------------------------------------------+
```

Code graders 是默认启用的机器判分；model/human grader 目前只保留 schema，离线 runner 默认 skipped。

## 规范演进

当发现以下情况时，更新本 skill：

- 用户指出流程、Prompt 路由或边界不清楚。
- 状态机步骤新增、删除或改名。
- 工具命令、输出路径、评估命令变化。
- 新增 prompt 或工具说明。
- 真实失败样本暴露规则缺口。

更新时同步：

- `docs/smartjobhunter-agent-design.md`
- `CLAUDE.md`
- `AGENTS.md`
- 必要时同步 README 的外部使用说明
