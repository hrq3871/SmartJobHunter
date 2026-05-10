---
name: jobhunter
description: 智能求职巡检 Agent
user_invocable: true
---

# SmartJobHunter Agent

当用户请求“运行巡检”“找岗位”“分析岗位是否适合”“生成投递包”时，使用本 skill。项目级规则见 `CLAUDE.md` / `AGENTS.md`；完整设计见 `docs/smartjobhunter-agent-design.md`。

## 目录结构

```text
SmartJobHunter/
├── CLAUDE.md / AGENTS.md              # AI 项目级规则
├── docs/smartjobhunter-agent-design.md # 内部完整设计
├── config/
│   ├── companies.yaml                 # 公司官网链接和策略配置
│   ├── agent.sample.yaml              # 可提交示例配置
│   └── agent.yaml                     # 本地私有配置，不提交
├── profiles/                          # 求职意向，文件名作为 _profile_id
├── resumes/                           # 简历文件
├── memory/seen_jobs.md                # 已处理岗位记忆
├── logs/
│   ├── strategy_tasks/                # 策略巡检任务
│   └── crawler_evidence/              # 策略证据包
├── output/{YYYY-MM-DD}/               # 日期归档报告和投递包
├── evals/
│   ├── regression/jobhunter_core.yaml
│   └── capability/jobhunter_hard_cases.yaml
├── src/                               # Python 抓取、过滤、报告、评估代码
└── .claude/skills/jobhunter/
    ├── skill.md                       # 当前 Agent 执行架构
    ├── profile.md                     # 候选人/profile 操作说明
    ├── match.md                       # 匹配判断操作说明
    ├── prompts/
    │   ├── build_candidate_profile.md
    │   ├── analyze_job.md
    │   ├── match_candidate_job.md
    │   ├── semantic_filter.md
    │   └── report.md
    └── tools/
        ├── load_config.md
        ├── crawl.md
        ├── filter.md
        └── update_memory.md
```

目录结构或重要文件变化时，必须同步更新本节、`docs/smartjobhunter-agent-design.md`、`CLAUDE.md` 和 `AGENTS.md`。

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

## 边界

Python 负责抓取、清洗、确定性过滤、URL 校验、报告落盘、投递包落盘和机器评估。

当前 Claude/Codex Agent 负责语义判断、证据复核、策略固化和异常归因。

Python 不调用外部 LLM API。需要 AI 判断的步骤由当前 Agent 在会话中执行。

## 触发方式

用户说以下意图时，使用本 skill：

- “运行巡检”
- “今天有什么岗位”
- “帮我看看有没有适合我的岗位”
- “分析这个岗位适不适合我”
- “生成投递包”
- “修复某家公司爬虫/策略”
- “评估这次报告质量”

如果用户只是问项目介绍或安装方式，优先参考 README，不必进入完整状态机。

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

完成条件：

- profile、resume、companies、seen memory 已加载。
- 明确本次 job type：`social`、`campus`、`internship` 或全部。

### LOADED

目标：确认求职目标和关键词。

动作：

1. 不要默认套用产品经理；必须读取 profile 中的 `target_roles`、`must_have`、`avoid`、`keywords`。
2. 如果 profile 目标过宽，选择多个代表关键词抽样。
3. 信息不足时向用户说明缺口，而不是编造偏好。

完成条件：

- 明确本轮关键词。
- 明确哪些岗位应拒绝。

### STRATEGY_INSPECTED

目标：巡检公司官网链接和抓取策略。

命令：

```powershell
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type <social|campus|internship>
```

单公司巡检：

```powershell
python -m src.health_monitor --inspect-company <company_id> --keyword "<关键词>"
```

对 `unknown/new/changed/failed` 读取：

- `logs/strategy_tasks/.../task.json`
- `logs/crawler_evidence/.../evidence.json`
- `logs/crawler_evidence/.../network.json`
- `logs/crawler_evidence/.../page.html`
- `logs/crawler_evidence/.../page.txt`

策略判断：

- `config_intercept`：稳定 XHR/fetch API，可写入 `api.pattern`、`api.data_path`、`field_mappings`。
- `config_dom`：无稳定 API，但 DOM selector 可复现。
- `legacy_python`：保留旧 `src.crawler` 中已固化逻辑。
- `custom_python`：新建或更新 `src/site_strategies/*.py`。
- `browser_operation`：只能通过可复现浏览器操作抓取，需记录步骤和限制。
- `unsupported`：登录、验证码、强反爬、信息不足或不可解析。

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

完成条件：

- 获得岗位列表，或确认本轮没有新岗位。
- 如果 CLI 输出为空，不要直接判断“没有合适岗位”；需抽查原始抓取样本和关键词。

### FILTERED

目标：过滤岗位。

过滤链路：

```text
raw jobs -> filter_by_time -> dedup -> clean_data -> match_job_intent -> Agent semantic review
```

规则：

- 时间过滤和去重由 Python 执行。
- 语义保留由 Agent 复核。
- 标题含 AI 但本质是工程、运营、销售、标注的岗位应拒绝或降权。
- 岗位职责与 profile 不闭环时，不进入强推荐。

使用 prompt：

- `.claude/skills/jobhunter/prompts/semantic_filter.md`

### EVALUATED

目标：构建候选人画像、岗位画像和匹配判断。

使用 prompt：

- `.claude/skills/jobhunter/prompts/build_candidate_profile.md`
- `.claude/skills/jobhunter/prompts/analyze_job.md`
- `.claude/skills/jobhunter/prompts/match_candidate_job.md`

输出必须包含：

- JD 证据
- 简历证据
- 匹配分数
- 推荐等级
- 缺失技能
- 风险信号

### URL_VALIDATED

目标：报告前校验岗位链接。

规则：

- 空链接、404、不可访问链接不得进入报告或飞书。
- 链接校验后无岗位时，停止报告生成并说明原因。

### REPORTED

目标：生成日期归档报告。

路径：

```text
output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md
```

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

## 可用工具和命令

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

- 用户指出流程或边界不清楚。
- 状态机步骤新增、删除或改名。
- 工具命令、输出路径、评估命令变化。
- 新增 prompt 或工具说明。
- 真实失败样本暴露规则缺口。

更新时同步：

- `CLAUDE.md`
- `AGENTS.md`
- `docs/smartjobhunter-agent-design.md`
- 必要时同步 README 的外部使用说明
