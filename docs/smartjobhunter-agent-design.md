# SmartJobHunter Agent Design

本文档是 SmartJobHunter 的内部 Agent 架构设计说明。它承接原来 `CLAUDE.md` 中过长的详细设计内容，用来让人完整理解系统如何运行；`CLAUDE.md` / `AGENTS.md` 只保留 AI 执行时必须遵守的项目级规则；`.claude/skills/jobhunter/skill.md` 是具体任务执行手册；`README.md` / `README_CN.md` 保持对外宣传和使用入口。

## 1. 文档分层

```text
+-------------------------------+----------------------------------------------+
| 文件                          | 职责                                         |
+-------------------------------+----------------------------------------------+
| README.md / README_CN.md       | 对外介绍、能力定位、快速开始、常用命令       |
| docs/smartjobhunter-agent-design.md | 内部完整设计、架构、流程、评估体系       |
| CLAUDE.md / AGENTS.md          | AI 项目级规则、边界、必须执行的命令          |
| .claude/skills/jobhunter/skill.md | JobHunter Agent 的具体执行架构和状态机    |
| .claude/skills/jobhunter/prompts/ | 候选人画像、岗位画像、匹配判断等 prompt   |
| src/evaluation.py              | 机器评估 harness                             |
+-------------------------------+----------------------------------------------+
```

设计原则：

- `CLAUDE.md` / `AGENTS.md` 不写成长篇产品说明，只写 AI 必须遵守的规则。
- 具体求职巡检怎么做，以 `.claude/skills/jobhunter/skill.md` 为准。
- 详细设计、背景解释、评估体系说明放在 `docs/`。
- README 面向外部用户，避免塞内部 Agent 工作流细节。

## 2. 系统定位

SmartJobHunter 是一个面向公司官网岗位巡检的 Agent 平台项目。

Python 负责：

- 官网抓取
- 文本抽取
- 确定性过滤
- fallback 粗评分
- URL 校验
- 报告和投递包落盘
- 评估 harness

当前 Claude/Codex Agent 负责：

- 从简历和求职目标构建候选人画像
- 分析岗位画像
- 语义过滤和最终匹配判断
- 根据证据修复抓取策略
- 复核报告质量和异常结果
- 根据用户反馈推动规则演进

Python 不调用外部 LLM API。需要 AI 判断的部分由当前 Claude/Codex Agent 在会话中完成。

## 3. 目标与边界

### 核心目标

让用户只维护公司官网/招聘链接和求职 profile，Agent 每日主动发现新岗位、识别策略变化、过滤不匹配岗位、生成可投递材料，并用评估体系防止流程退化。

### 成功标准

- 能稳定巡检启用公司官网。
- 遇到新链接、失效链接、登录、验证码、反爬、fingerprint 变化时能正确归因。
- 只把真实可访问的岗位链接写入报告。
- 过滤时不能只靠关键词命中，必须结合 profile、JD 和简历证据。
- Top 3 投递包必须结合公司、岗位、JD 证据和简历证据。
- 修改抓取、过滤、评分、报告、投递包或 Agent 文档后，评估必须通过。

### 不做的事

- 不直接替用户投递。
- 不把 Python fallback 分数当成最终 AI 判断。
- 不在仓库提交真实 `config/agent.yaml`、运行产物、私有优化记录。
- 不把登录、验证码、强反爬网站伪装成可抓取。

## 4. 目录结构

```text
SmartJobHunter/
├── config/
│   ├── companies.yaml              # 用户维护的公司链接和策略
│   ├── agent.sample.yaml           # 可提交的飞书/Agent 示例配置
│   └── agent.yaml                  # 本地私有配置，不提交
├── profiles/                       # 求职 profile，文件名作为 _profile_id
├── resumes/                        # 简历文件
├── memory/
│   └── seen_jobs.md                # 去重记忆
├── logs/
│   ├── strategy_tasks/             # 策略任务
│   └── crawler_evidence/           # 策略证据包
├── output/
│   └── {YYYY-MM-DD}/               # 日期归档报告和投递包
├── evals/
│   ├── regression/jobhunter_core.yaml
│   ├── capability/jobhunter_hard_cases.yaml
│   └── candidates/
├── src/
│   ├── cli.py                      # JobHunter 主流程
│   ├── crawler_factory.py          # 抓取入口
│   ├── health_monitor.py           # 每日策略巡检
│   ├── crawler_evidence.py         # 证据采集
│   ├── matching.py                 # fallback 语义匹配和评分
│   ├── evaluation.py               # eval harness
│   ├── eval_graders.py             # grader helper
│   └── eval_transcript.py          # transcript recorder
├── .claude/skills/jobhunter/
│   ├── skill.md                    # JobHunter Agent 执行架构
│   ├── prompts/                    # AI 判断 prompt
│   └── tools/                      # 工具说明
└── docs/
    ├── smartjobhunter-agent-design.md
    ├── evaluation-grader-rubrics.md
    └── eval-case-feedback-loop.md
```

## 5. Agent 闭环架构

```text
+----------+     +----------+     +----------+     +----------+     +----------+
| 感知     | --> | 决策     | --> | 执行     | --> | 反馈     | --> | 学习     |
+----------+     +----------+     +----------+     +----------+     +----------+
| 配置     |     | 策略分类 |     | 抓取     |     | 报告     |     | eval case|
| 证据包   |     | 是否保留 |     | 过滤     |     | 投递包   |     | 文档演进 |
| 简历/JD  |     | 是否推荐 |     | 评估     |     | 用户反馈 |     | 策略固化 |
+----------+     +----------+     +----------+     +----------+     +----------+
```

## 6. 核心状态机

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

目标：初始化并加载配置。

读取：

- `config/companies.yaml`
- `profiles/*.md`
- `resumes/*`
- `memory/seen_jobs.md`
- `config/agent.yaml`（如果存在）

输出：

- profile
- resume text
- companies
- seen hashes

### LOADED

目标：确认 profile、简历、公司配置可用。

Agent 要检查：

- profile 是否有真实目标岗位，而不是默认产品经理示例。
- `target_roles`、`must_have`、`avoid` 是否覆盖求职方向。
- 简历文件是否存在且可解析。

### STRATEGY_INSPECTED

目标：每日官网链接巡检和策略判断。

命令：

```powershell
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type <social|campus|internship>
```

对 `unknown/new/changed/failed` 策略，读取：

- `logs/strategy_tasks/.../task.json`
- `logs/crawler_evidence/.../evidence.json`
- `logs/crawler_evidence/.../network.json`
- `logs/crawler_evidence/.../page.html`
- `logs/crawler_evidence/.../page.txt`

策略类型：

- `config_intercept`
- `config_dom`
- `legacy_python`
- `custom_python`
- `browser_operation`
- `unsupported`

修改策略后必须验证：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "<关键词>" --max-jobs 3
```

### CRAWLED

目标：抓取岗位数据。

常用命令：

```powershell
python -m src.crawler_factory --crawl <company_id> --keyword "<关键词>" --max-jobs 10
```

若目标较宽，不要只用一个关键词。应根据 profile 抽样多个代表关键词。

### FILTERED

目标：过滤岗位。

过滤链路：

```text
raw jobs
  -> filter_by_time
  -> dedup
  -> clean_data
  -> match_job_intent
  -> Agent semantic review
```

要求：

- 不要只靠关键词命中决定保留。
- 标题含 AI 但本质是运营、销售、工程、标注的岗位应拒绝或降权。
- Python fallback 只是粗筛，Agent 必须复核高风险岗位。

### EVALUATED

目标：深度评估匹配岗位。

使用 prompt：

- `.claude/skills/jobhunter/prompts/build_candidate_profile.md`
- `.claude/skills/jobhunter/prompts/analyze_job.md`
- `.claude/skills/jobhunter/prompts/match_candidate_job.md`

输出必须包含：

- JD 证据
- 简历证据
- 匹配分数
- 推荐等级
- 缺失技能或风险

### URL_VALIDATED

目标：报告前校验岗位详情链接。

规则：

- 空链接、404、不可访问链接不得进入报告。
- 链接校验后无岗位时，不生成报告，说明原因。

### REPORTED

目标：生成日期归档报告。

路径：

```text
output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md
```

飞书推送由 `config/agent.yaml` 控制，不是 `src.scheduler --push`。

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

更新：

```text
memory/seen_jobs.md
```

## 7. 评估体系

### 命令

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
python -m pytest tests/test_evaluation.py -v
```

### 评估结构

```text
+----------------+     +-------------------------+     +-------------+
| 评测集 YAML    | --> | 评估 harness            | --> | Case runner |
| regression /   |     | python -m src.evaluation|     | 逐 case 执行|
| capability     |     +-------------------------+     +------+------+
+----------------+                                          |
                                                            |
                         +----------------------------------+------------------+
                         |                                                     |
                         v                                                     v
                  +---------------+                                  +-----------------+
                  | Code graders  |                                  | Transcript JSONL|
                  | pass / fail   |                                  | 可回放轨迹      |
                  +-------+-------+                                  +--------+--------+
                          |                                                   |
                          v                                                   v
                  +---------------+                                  +-----------------+
                  | 指标聚合      |                                  | 失败定位证据    |
                  +-------+-------+                                  +-----------------+
                          |
                          v
                  +------------------------+
                  | Markdown + JSON 报告   |
                  +------------------------+
```

### 输出

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/
├── agent_eval_results.json
├── agent_eval_report.md
├── transcripts/<case_id>.jsonl
├── artifacts/
└── wf/
```

### 指标

- `task_completion_rate`
- `pass@k`
- `pass^k`
- `tool_call_accuracy`
- `matching.precision`
- `matching.recall`
- `matching.f1`
- `bad_case_attribution`

### 归因

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

## 8. Grader 设计

当前默认启用 code grader：

- action 是否正确
- 分数是否在预期区间
- 推荐等级是否合理
- 文件是否生成
- URL 是否过滤
- 必需文本是否存在

model grader 和 human grader 只保留 schema，离线 runner 默认 skipped。具体 rubric 见 `docs/evaluation-grader-rubrics.md`。

## 9. 失败处理

失败时按顺序处理：

1. 打开 `agent_eval_report.md` 看失败 case 和 attribution。
2. 打开 `transcripts/<case_id>.jsonl` 回放执行过程。
3. 判断问题属于抓取策略、匹配过滤、推荐质量、输出质量还是文档漂移。
4. 修复代码、配置或文档。
5. 重新运行 regression eval。
6. 如果是新真实失败，沉淀到 `evals/candidates/` 或 promotion 到 regression。

## 10. 文档与规范演进

当出现以下情况时，必须更新相关文档：

- 用户指出当前行为或文档理解错误。
- JobHunter 状态机新增、删除或改名。
- 目录结构、输出路径、评估命令发生变化。
- 新增 prompt、工具或数据来源。
- 真实失败样本暴露出规则缺口。

更新位置：

- 项目级规则：`CLAUDE.md` 和 `AGENTS.md`
- 执行架构：`.claude/skills/jobhunter/skill.md`
- 详细设计：`docs/smartjobhunter-agent-design.md`
- 外部介绍：`README.md` / `README_CN.md`

