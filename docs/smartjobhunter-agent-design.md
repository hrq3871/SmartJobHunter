# SmartJobHunter Agent Design

> **文档用途**
> 本文档用于说明 SmartJobHunter 的内部 Agent 架构、状态机、评估入口和规范演进规则。
> 主要读者是维护本项目的 Claude/Codex Agent、开发者和需要理解系统设计的人。
> 不用于对外宣传、快速上手，也不作为 Agent 自动加载的定义文件；Agent 定义见 `CLAUDE.md` / `AGENTS.md`，Skill 路由见 `.claude/skills/jobhunter/skill.md`。

SmartJobHunter 是一个面向公司官网岗位巡检的 Agent 平台项目。Python 负责可复现的工具层，当前 Claude/Codex Agent 负责需要语义判断、证据复核和策略固化的部分。Python 不调用外部 LLM API。

## 1. 文档分层

```text
+----------------------------------------------+----------------------------------------------+
| 文件/目录                                     | 作用                                         |
+----------------------------------------------+----------------------------------------------+
| README.md / README_CN.md                      | 对外介绍、能力定位、快速开始、常用命令       |
| CLAUDE.md / AGENTS.md                         | 自动加载的 SmartJobHunter Agent 定义文件     |
| docs/smartjobhunter-agent-design.md           | 内部完整架构、状态机、评估入口和演进规则     |
| docs/smartjobhunter-evaluation-design.md      | 回归评估、真实巡检评估、人工标注和指标体系   |
| evals/evaluation-grader-rubrics.md            | Eval grader 判分标准和 schema                 |
| evals/eval-case-feedback-loop.md              | 真实失败/反馈沉淀为 eval case 的闭环         |
| docs/plans/                                   | 历史实施计划，不作为当前运行规则             |
| docs/optimization-log.md                      | 本地私有优化记录，不提交 Git                 |
| .claude/skills/jobhunter/skill.md             | JobHunter Skillmap：触发词和路由索引         |
| .claude/skills/jobhunter/profile.md           | 候选人画像子流程                             |
| .claude/skills/jobhunter/match.md             | 候选人-岗位匹配子流程                        |
| .claude/skills/jobhunter/prompts/*.md         | Agent 判断提示词                             |
| .claude/skills/jobhunter/tools/*.md           | Python 工具入口和命令说明                    |
| evals/regression/jobhunter_core.yaml          | 默认 regression eval 数据集                  |
| evals/capability/jobhunter_hard_cases.yaml    | 能力边界诊断数据集                           |
| evals/candidates/                             | 真实失败回流候选 case                        |
| config/companies.yaml                         | 用户维护的公司官网链接和策略配置             |
| config/agent.sample.yaml                      | 可提交的本地配置模板                         |
| config/agent.yaml                             | 本地私有配置，不提交 Git                     |
| config/resume_intents.yaml                    | Web 搜索意向，本地私有，不提交 Git           |
| profiles/*.md                                 | Agent 读取简历后生成的正式 profile           |
| resumes/*                                     | 简历原文，仅支持 PDF、Markdown、TXT          |
| src/                                          | Python 抓取、过滤、报告、评估工具层          |
| logs/strategy_tasks/                          | 策略任务，给 Agent 读取                      |
| logs/crawler_evidence/                        | 页面、DOM、网络、截图证据                    |
| output/{YYYY-MM-DD}/                          | 正式巡检报告和投递包                         |
| output/evals/                                 | 本地 eval 运行产物，不提交 Git               |
+----------------------------------------------+----------------------------------------------+
```

维护原则：

- README 只写对外信息；不要塞内部 Agent 运行规则。
- CLAUDE.md / AGENTS.md 写主 Agent 定义、状态机、Prompt 路由、委派规则和全局边界。
- `.claude/agents/crawler-strategy-inspector.md` 保存策略修复子 Agent 的唯一完整定义；主文档不复制其全部提示词。
- `.claude/skills/jobhunter/skill.md` 只写 Skillmap：触发场景、路由索引、常用命令和 eval 锚点。
- prompts 写具体判断标准，不承担系统分层说明。
- docs 根目录只保留全局设计、AI 自动维护或历史计划类文档；完整评估设计放 `docs/smartjobhunter-evaluation-design.md`。
- `evals/` 同时放评测集、grader 规则、失败回流流程和候选 case。

## 2. 系统定位

Python 工具层负责：

- 官网抓取、文本抽取、确定性过滤、fallback 粗评分。
- URL 校验、报告落盘、投递包落盘、memory 更新。
- 策略巡检、证据采集、评估 harness、真实报告解析、transcript 和 code graders。

当前 Claude/Codex Agent 负责：

- 从简历和求职目标构建候选人画像。
- 分析 JD，生成岗位画像。
- 语义过滤和最终匹配判断。
- 读取 strategy task 和 evidence，固化公司抓取策略。
- 复核报告质量、投递包质量和异常结果。
- 根据真实失败更新 eval case、prompt、Skillmap 和 Agent 定义。

关键边界：

- 不直接替用户投递。
- 不绕过登录、验证码或强反爬。
- 不把 Python fallback 分数当作最终 AI 结论。
- 不提交 `config/agent.yaml`、`output/`、`logs/`、`docs/optimization-log.md`。

## 3. 目录结构

```text
SmartJobHunter/
├── README.md / README_CN.md
├── CLAUDE.md / AGENTS.md
├── config/
│   ├── companies.yaml
│   ├── agent.sample.yaml
│   ├── agent.yaml                  # ignored, local only
│   ├── resume_intents.yaml         # ignored, local search intent only
│   └── system_templates.yaml
├── profiles/
├── resumes/
├── memory/
│   └── seen_jobs.md
├── logs/
│   ├── strategy_tasks/
│   └── crawler_evidence/
├── output/
│   ├── {YYYY-MM-DD}/
│   └── evals/
├── evals/
│   ├── regression/jobhunter_core.yaml
│   ├── capability/jobhunter_hard_cases.yaml
│   ├── evaluation-grader-rubrics.md
│   ├── eval-case-feedback-loop.md
│   ├── candidates/
│   └── jobhunter_agent_eval.yaml    # legacy/default-compatible copy
├── src/
│   ├── cli.py                       # JobHunter 主流程 & CLI 入口
│   ├── base_crawler.py              # 爬虫基类（API 拦截）
│   ├── config_crawler.py            # 配置驱动爬虫
│   ├── dom_crawler.py               # DOM 解析爬虫
│   ├── crawler_factory.py           # 爬虫工厂（配置 + 策略路由）
│   ├── company_registry.py          # 公司链接和策略注册表
│   ├── site_strategies/             # 专用公司 Python 策略
│   ├── browser_interactions.py      # 可重放浏览器搜索/点击操作
│   ├── health_monitor.py            # 每日策略巡检协调
│   ├── site_inspector.py            # 官网链接与策略轻量巡检
│   ├── crawler_evidence.py          # 页面/网络/DOM 证据采集
│   ├── strategy_planner.py          # Agent 策略任务生成
│   ├── strategy_applier.py          # Agent 决策写回配置
│   ├── crawler_verification.py      # 单站修复验收
│   ├── filters.py                   # 时间/去重/清洗过滤
│   ├── matching.py                  # 语义匹配 fallback 与评分
│   ├── resume_parser.py             # PDF/Markdown/TXT 简历解析
│   ├── resume_intents.py            # 搜索意向持久化和手动文件同步
│   ├── claude_launcher.py           # 可见 Claude Code CMD 启动器
│   ├── reporting.py                 # 报告生成
│   ├── run_records.py               # 运行账本记录
│   ├── eval_real_runs.py            # 真实巡检报告解析、人工标注模板和实测指标
│   ├── feishu_push.py               # 飞书 Wiki 推送
│   ├── feishu_bitable.py            # 飞书多维表格
│   ├── notifier.py                  # 用户通知（抓取失败路径）
│   ├── web_ui.py                    # 本地管理控制台（FastAPI，仅 127.0.0.1）
│   ├── scheduler.py                 # 定时调度（每天 20:00）
│   ├── evaluation.py                # Agent 评估 harness
│   ├── eval_graders.py              # Code/model/human grader
│   ├── eval_transcript.py           # JSONL 轨迹记录
│   └── exceptions.py                # 异常类型定义
├── templates/
│   └── index.html                    # Web 控制台 SPA 前端
├── .claude/skills/jobhunter/
│   ├── skill.md                    # Skillmap：触发词和路由索引
│   ├── profile.md
│   ├── match.md
│   ├── prompts/
│   │   ├── analyze_crawler_strategy.md
│   │   ├── analyze_resume.md
│   │   ├── build_candidate_profile.md
│   │   ├── semantic_filter.md
│   │   ├── analyze_job.md
│   │   ├── match_candidate_job.md
│   │   ├── evaluate.md
│   │   └── report.md
│   └── tools/
│       ├── load_config.md
│       ├── crawl.md
│       ├── filter.md
│       └── update_memory.md
└── docs/
    ├── smartjobhunter-agent-design.md
    ├── smartjobhunter-evaluation-design.md
    ├── optimization-log.md          # ignored, local only
    └── plans/
```

## 4. 运行架构

```text
用户意图
  |
  v
CLAUDE.md / AGENTS.md
  |  自动加载的 Agent 定义：身份、边界、状态机、Prompt 路由、评估
  v
.claude/skills/jobhunter/skill.md
  |  Skillmap：触发词、路由索引、常用命令
  +--> profile.md + build_candidate_profile.md / analyze_resume.md
  +--> match.md + analyze_job.md + match_candidate_job.md / evaluate.md
  +--> analyze_crawler_strategy.md
  +--> report.md
  |
  v
Python 工具层
  |  src.cli / crawler_factory / filters / matching / health_monitor / evaluation
  v
output / logs / memory / evals
```

### Skill / Prompt 路由

```text
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 场景                                 | 使用的 Skill / Prompt                         | Python / 数据入口                            |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
| 用户问项目是什么、怎么安装           | README.md / README_CN.md                      | 不进入完整状态机                             |
| 运行完整巡检                         | CLAUDE.md / AGENTS.md + jobhunter Skillmap    | python -m src.cli                            |
| 分析简历、补候选人画像               | profile.md + build_candidate_profile.md       | src.resume_parser.parse_resume               |
| 需要更偏 HR 的简历深挖               | prompts/analyze_resume.md                     | 简历原文                                     |
| 单个岗位是否适合                     | match.md + analyze_job.md + match_candidate_job.md | 岗位 JD + candidate_profile + profile   |
| Python fallback 兼容评分/旧流程       | prompts/evaluate.md                           | src.matching.evaluate_job_fit                |
| 过滤关键词噪音岗位                   | prompts/semantic_filter.md                    | src.filters + src.matching.match_job_intent  |
| 策略巡检出现 unknown/new/failed       | prompts/analyze_crawler_strategy.md           | logs/strategy_tasks + logs/crawler_evidence  |
| 生成或复核报告                       | prompts/report.md                             | output/{YYYY-MM-DD}/                         |
| 修复 eval 失败                       | evals/evaluation-grader-rubrics.md + transcripts | output/evals/.../agent_eval_report.md     |
| 真实失败回流                         | evals/eval-case-feedback-loop.md              | evals/candidates/                            |
+--------------------------------------+----------------------------------------------+----------------------------------------------+
```

### Python 主流程与 Agent 介入点

```text
src.cli.JobHunter.run_profile()
  -> load_config()
     Agent: 检查 profile 目标，不默认产品经理
  -> resume_parser.parse_resume()
     Agent: profile.md / build_candidate_profile.md
  -> crawl_jobs()
     Python: crawler_factory
     Agent: 若策略失败，analyze_crawler_strategy.md
  -> filter_jobs()
     Python: time -> dedup -> clean_data -> match_job_intent
     Agent: semantic_filter.md 复核高风险岗位
  -> evaluate_job()
     Python fallback: matching.evaluate_job_fit
     Agent: analyze_job.md + match_candidate_job.md 做最终判断
  -> _rank_and_filter_results()
  -> _filter_live_urls()
  -> generate_report()
     Agent: report.md 复核报告内容
  -> generate_application_package()
     Agent: 确认 Cover Letter 结合 JD 和简历证据
  -> Feishu push / Bitable
  -> filters.update_memory()
```

## 5. Agent 闭环

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

对应说明：`.claude/skills/jobhunter/tools/load_config.md`。

### LOADED

目标：确认 profile、简历、公司配置可用。

Agent 必须检查：

- `config/resume_intents.yaml` 中的 `search_intent` 只包含用户搜索目标，不能作为候选人能力证据。
- 上传简历时不得创建正式 profile；Agent 必须读取完整简历后生成 `profiles/<profile_id>.md`。
- 简历仅支持 PDF、Markdown、TXT；DOCX 和图片不支持上传、预览、解析或巡检。
- `target_roles`、`target_domains`、`must_have`、`avoid`、`keywords`。
- 简历是否存在且可解析。
- 目标宽泛时是否需要多个关键词抽样。
- 不得默认用户是产品经理。

候选人画像：

- 默认使用 `profile.md` + `prompts/build_candidate_profile.md`。
- 需要更细 HR 式分析时补充 `prompts/analyze_resume.md`。

### Web Agent 启动链

Web 控制台不直接运行 Python CLI 冒充 Agent。点击“启动巡检”时打开可见 CMD：

```powershell
claude --permission-mode auto --name "SmartHunter-巡检-<run_id>" "<任务 Prompt>"
```

Claude Code 必须先读取简历和 `search_intent`、生成正式 profile，再执行抓取、JD 画像、Agent 语义匹配和报告。点击批量修复时使用：

```powershell
claude --permission-mode auto --agent crawler-strategy-inspector --name "SmartHunter-策略修复-<run_id>" "<批量任务 Prompt>"
```

一次只启动一个修复 Agent，完整传递全部选中公司 ID 和原始链接。Web 只有取得真实 PID 后才能显示“已启动”；启动异常不得吞掉。

### CRAWLED 内嵌策略巡检

`STRATEGY_INSPECTED` 不再作为独立状态。策略巡检、失败收集、批量修复和重抓都内嵌在 `CRAWLED` 阶段。

目标：巡检公司官网链接和抓取策略。

命令：

```powershell
python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type <social|campus|internship>
python -m src.health_monitor --inspect-company <company_id> --keyword "<关键词>"
```

对 `unknown/new/changed/failed` 策略读取：

- `logs/strategy_tasks/.../task.json`
- `logs/crawler_evidence/.../evidence.json`
- `logs/crawler_evidence/.../network.json`
- `logs/crawler_evidence/.../page.html`
- `logs/crawler_evidence/.../page.txt`
- `logs/crawler_evidence/.../page.png`

Agent 使用 `prompts/analyze_crawler_strategy.md` 判断：

- `config_intercept`
- `config_dom`
- `legacy_python`
- `custom_python`
- `browser_operation`
- `unsupported`

本轮全部待修复公司一次性交给一个 `crawler-strategy-inspector` 子 Agent 串行处理，不按公司拆分，也不允许继续嵌套 Agent。Python 负责可复现交互、采证、配置写回和验证；LLM 只分析非固定 API 结构、data path、字段映射和配置无法表达的专用策略。登录、验证码、网络、强反爬、地域限制和不可复现交互必须落为 blocked/failed。

平台工具分流：`web-access 仅限 Claude Code`。Claude Code 未安装时先运行 `npx skills add eze-is/web-access`；Codex 不加载该 Skill，使用内置 Browser 探索公开页面，并仅在用户明确授权时使用 Chrome control。两者最终都回到 Python Playwright 重放和验证。

修改策略后必须验证：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "<关键词>" --max-jobs 3
```

验证命令以非零退出码表示失败，并输出 `verification.json` 所需指标：岗位数、`title/company/url/duty/requirement` 完整率、URL 有效率、耗时和最终状态。只有验证通过并保存 fingerprint 才能标为 verified。

### CRAWLED

目标：抓取岗位数据。

命令：

```powershell
python -m src.crawler_factory --crawl <company_id> --keyword "<关键词>" --max-jobs 10
```

说明：`.claude/skills/jobhunter/tools/crawl.md`。

若 CLI 输出为空，不直接结论“没有合适岗位”；应抽查原始抓取、关键词和 profile。

### FILTERED

目标：过滤岗位。

```text
raw jobs
  -> filter_by_time
  -> dedup
  -> clean_data
  -> match_job_intent
  -> Agent semantic review
```

工具说明：`.claude/skills/jobhunter/tools/filter.md`。

Agent 使用 `prompts/semantic_filter.md` 复核：

- 标题关键词是否只是噪音。
- 岗位核心职责是否匹配 profile。
- 销售、客服、审核、标注、纯运营等风险是否进入强推荐。

### EVALUATED

目标：生成岗位画像和最终匹配判断。

默认链路：

```text
profile.md
  -> build_candidate_profile.md
match.md
  -> analyze_job.md
  -> match_candidate_job.md
```

兼容/辅助链路：

- `prompts/evaluate.md`：旧版深度岗位评分 prompt，适合对齐 Python fallback 评分维度。
- `src.matching.evaluate_job_fit()`：无 Agent 执行 prompt 时的 deterministic fallback。

输出必须包含：

- JD 证据
- 简历证据
- 匹配分数
- 推荐等级
- 缺失技能
- 风险信号

### URL_VALIDATED

目标：报告前校验岗位详情链接。

Python 执行：`JobHunter._filter_live_urls()`。

规则：

- 空链接、404、不可访问链接不得进入推荐区、飞书或投递包。
- 链接校验后无推荐岗位时仍生成报告骨架和全量抓取审计附录。
- 原始岗位 URL 必须原封不动保存；可见文本和 Markdown href 使用同一个完整字符串，禁止截断或改写查询参数。

### REPORTED

目标：生成日期归档报告。

路径：

```text
output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md
```

Agent 使用 `prompts/report.md` 复核报告是否包含 recommendation、scoring breakdown、风险、行动建议和可访问链接。

推荐结果之后必须追加 `全量抓取与判断记录`。每条记录包含结构化字段、完整 JD、原始链接、处理状态、判断来源（`agent` / `python_fallback`）、语义判断与引用证据、评分拆解和最终结论。该附录来自本次运行账本，不因过滤、去重或 URL 失效被删除。

### PACKAGED

目标：生成 Top 3 投递包。

路径：

```text
output/{YYYY-MM-DD}/application_packages/{profile_id}_{YYYYMMDD_HHMM}/
```

Cover Letter 必须结合公司、岗位、JD 证据、简历证据和风险点。

### DONE

目标：更新 memory 并汇报。

工具说明：`.claude/skills/jobhunter/tools/update_memory.md`。

更新：

```text
memory/seen_jobs.md
```

## 7. 评估体系

命令：

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<report>.md"
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<report>.md" --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml"
lark-cli auth login --domain base
python -m src.eval_lark_sync setup
python -m src.eval_lark_sync export-labels --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml" --run-id "<run_id>"
python -m src.eval_lark_sync score-from-lark --report "output/YYYY-MM-DD/<report>.md" --run-id "<run_id>" --sync-badcases
python -m pytest tests/test_evaluation.py tests/test_eval_real_runs.py tests/test_eval_lark_sync.py -v
```

默认 regression 数据集：`evals/regression/jobhunter_core.yaml`。

真实巡检评估只读取已生成的报告，不重新抓取网页。第一次运行 `src.eval_real_runs` 会生成 `human_labels.yaml`；人工填写 `human_label`、必要备注和可选 1-5 维度分。URL 格式、推荐状态、报告存在、投递包存在等客观项由代码自动判定。标注入口可以是本地 YAML，也可以通过 `src.eval_lark_sync` 同步到飞书多维表格标注表；badcase 会写入本地 `bad_cases.md` 并可同步到飞书文档。详细标注规则和指标定义见 `docs/smartjobhunter-evaluation-design.md`。

输出：

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/
├── agent_eval_results.json
├── agent_eval_report.md
├── transcripts/<case_id>.jsonl
├── artifacts/
└── wf/

output/evals/real_runs/{YYYY-MM-DD}/{report_stem}_{HHMMSS}/
├── real_run_samples.json
├── human_labels.yaml
├── real_run_eval_results.json
├── real_run_eval_report.md
└── bad_cases.md
```

指标：

- `task_completion_rate`
- `pass@k`
- `pass^k`
- `tool_call_accuracy`
- `matching.precision`
- `matching.recall`
- `matching.f1`
- `bad_case_attribution`
- real-run `recommendation_precision`
- real-run `strict_recommendation_precision`
- real-run `reviewed_recall`
- real-run `reviewed_false_negative_rate`
- real-run `invalid_url_rate`
- real-run `label_completion_rate`
- real-run human dimension averages: `role_fit_avg`, `skill_match_avg`, `seniority_fit_avg`, `jd_quality_avg`, `risk_level_avg`, `apply_priority_avg`
- real-run badcase counts by type: 推荐误报、过滤误杀、推荐区坏链接、人工确认坏链接、证据不足

归因：

```text
+------------------------+-----------------------------------------------+
| 归因模块               | 测试内容                                      |
+------------------------+-----------------------------------------------+
| crawler_strategy       | crawl / collect_evidence / blocked 路由       |
| matching_filtering     | 保留目标岗位，拒绝关键词噪音                  |
| recommendation_quality | 评分和推荐等级边界                            |
| output_quality         | URL 过滤、报告、Top 3 投递包、memory          |
| instruction_drift      | AGENTS / CLAUDE / jobhunter Skillmap 一致性   |
+------------------------+-----------------------------------------------+
```

Code graders 是默认启用的机器判分；model/human grader 在回归 runner 中只保留 schema，离线 runner 默认 skipped。真实巡检评估通过本地 `human_labels.yaml` 或飞书标注表引入人工 gold labels，并输出中文指标、人工维度分和 badcase 表。具体 rubric 见 `evals/evaluation-grader-rubrics.md`，完整真实评估设计见 `docs/smartjobhunter-evaluation-design.md`。

## 8. 失败处理

失败时按顺序处理：

1. 打开 `agent_eval_report.md` 看失败 case 和 attribution。
2. 打开 `transcripts/<case_id>.jsonl` 回放执行过程。
3. 判断问题属于抓取策略、匹配过滤、推荐质量、输出质量还是 instruction_drift。
4. 修复代码、配置、prompt、Skill 或项目规则。
5. 重新运行 regression eval。
6. 如果是新真实失败，按 `evals/eval-case-feedback-loop.md`、真实巡检 `human_labels.yaml`、飞书标注表或 `bad_cases.md` 沉淀到 `evals/candidates/`。

## 9. 文档与规范演进

当出现以下情况时，必须更新相关文档：

- 用户指出当前行为或文档理解错误。
- JobHunter 状态机新增、删除或改名。
- 目录结构、输出路径、评估命令发生变化。
- 新增 prompt、工具、数据来源或 Python 主流程。
- 真实失败样本暴露出规则缺口。

同步更新顺序：

1. `CLAUDE.md` 和 `AGENTS.md`
2. `.claude/skills/jobhunter/skill.md`
3. `docs/smartjobhunter-agent-design.md`
4. 必要时更新 README 的对外说明
5. 修改后运行 `python -m src.evaluation --fail-under 1.0`；涉及真实巡检评估时同时运行 `python -m pytest tests/test_eval_real_runs.py -v`
