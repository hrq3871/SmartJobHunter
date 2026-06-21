# SmartHunter 报告审计与独立策略修复子 Agent 设计及执行计划

> 日期：2026-06-20  
> 状态：已执行，待用户审核本地提交  
> 范围：报告追加全量抓取与判断记录；一个独立子 Agent 串行处理全部策略任务；Python 优先，LLM 只处理非固定规则。

## 1. 背景与现状

当前架构方向是正确的：Python 负责抓取、清洗、fallback、URL 校验和测试；当前 Claude/Codex Agent 阅读 strategy task 与 crawler evidence，分析 API 并修改配置或代码。

源码检查发现的缺口：

- Windows 定时 CLI 的“AI 评估”实际调用 Python fallback，没有自动执行 Agent Prompt。
- 报告没有展示已有的语义证据、简历证据、完整评分拆解和最终判断来源，也没有保留被过滤岗位的审计记录。
- `crawler_evidence.collect_evidence()` 只访问页面并等待，不会搜索、点击或翻页；交互后出现的真实 XHR 可能无法被采集。
- 当前 Agent 直接处理全部 DOM、Network、截图和错误，污染主求职上下文。
- `browser_operation` 目前只是枚举，没有真实执行入口。
- 零岗位、异常被吞掉、缺少 fingerprint 等情况会导致修复任务无法稳定触发。

## 2. 目标与非目标

### 目标

- 保持当前推荐结果结构，在其下方追加本次抓取的全部原始岗位链接和结构化判断记录。
- 保留语义判断、引用证据、各维度评分、总分和最终结论。
- 明确判断来源：`agent`、`python_fallback` 或 `not_evaluated`。
- 将全部策略任务交给一个专用 `crawler-strategy-inspector` 子 Agent 串行处理。
- Python 尽量承担通用交互、采证、配置应用和验证；LLM 只分析 API 结构、字段映射和非固定规则。

### 非目标

- 不在 Python 中调用外部 LLM API。
- 不自动绕过登录、验证码、强反爬或地域限制。
- 不为每家公司创建不同 Agent，也不嵌套更多 Agent。
- 不在报告里加入人工金标、历史模型对比或本次运行无法产生的数据。

## 3. 总体架构

```text
主 Agent
  -> 启动一个 crawler-strategy-inspector 子 Agent
       -> 读取全部 pending strategy tasks
       -> 调用 Python 做确定性检查与通用交互采证
       -> evidence 不足时使用 Codex Browser 探索页面交互
       -> LLM 分析真实接口结构与字段映射
       -> 输出 strategy_decision
       -> Python 应用普通配置并执行单站验证
       -> 复杂策略由子 Agent 修改专用代码
       -> 顺序处理下一家公司
  -> 主 Agent 只接收压缩摘要和 artifact 路径
  -> 继续岗位匹配与报告流程
```

## 4. Playwright 与 Codex 浏览器能力

### Python Playwright

Python Playwright 是可复现的浏览器执行和 Network Evidence 采集层，负责：

- 按已知选择器输入关键词、点击搜索和翻页。
- 监听 XHR/Fetch 请求与 JSON 响应。
- 保存请求 URL、响应状态、脱敏 Payload、响应样本和截图。
- 在策略固化后稳定重复执行。

### Claude Code 与 Codex 浏览器能力

- `web-access 仅限 Claude Code`；Claude Code 用户未安装时先执行 `npx skills add eze-is/web-access`。
- Codex 不加载、安装或触发 `web-access`；公开页面使用 Codex 内置 Browser，登录态仅在用户明确授权时使用 Chrome control。
- 平台浏览器用于探索未知交互，但当前文档没有证明它们对完整 XHR 响应体提供与 Python Playwright 等价的稳定落盘接口。

推荐组合：

```text
Python Playwright 通用交互 + Network Evidence
  -> evidence 不足
Claude Code web-access / Codex 内置 Browser 探索未知控件和交互路径
  -> 形成可重复 action plan
Python Playwright 按 action plan 重放并落盘真实响应
```

默认不使用登录态。必须登录时输出 `login_required`；只有用户明确授权时才考虑 Claude Code CDP 或 Codex Chrome control。

准确表述：

> Python Playwright 负责可复现的网页交互和接口响应采集；独立策略子 Agent 在遇到非固定页面结构时，Claude Code 使用 web-access、Codex 使用内置 Browser 探索交互路径，并由当前大模型分析 API 结构、字段映射和固化方案。

## 5. Python 与 LLM 的职责边界

### Python 优先处理

- URL、跳转、HTTP 状态、耗时和 fingerprint。
- 通用搜索框、关键词输入、搜索按钮和常见翻页。
- XHR/Fetch 请求及 JSON 响应采集与脱敏。
- 候选岗位数组扫描和字段提示。
- 登录、验证码、网络错误和阻断信号识别。
- `strategy_decision` Schema 校验。
- 普通 `config_intercept` / `config_dom` 配置的确定性应用。
- 单公司抓取、字段完整性检查、回归测试和报告渲染。

### LLM 子 Agent 处理

- 判断多个请求中哪个是真实岗位接口。
- 分析 `api.pattern`、`api.data_path`、`field_mappings` 和 `url_template`。
- 判断 API、DOM、旧 Python、专用 Python、浏览器操作或不支持哪种策略更合理。
- 对 Python 通用交互无法覆盖的页面探索可复现操作路径。
- 配置无法表达时编写最小专用策略。
- 对不可修复场景生成带证据结论。

## 6. 报告运行记录

每次巡检先创建唯一 `run_id`，抓取完成后立即建立不可丢失的运行账本。每条抓取结果形成独立 `run_record_id`，即使 `job_id`、Hash 或 URL 重复也能逐条审计：

```yaml
run_id: string
run_record_id: string
original_job_id: string
job_hash: string
original_url: string
raw_job: object  # 抓取完成时的完整岗位字典，无损保留 job_type/product/bg 及未来字段
processing:
  stage: crawled | time_filtered | deduplicated | semantic_rejected | below_threshold | url_rejected | recommended
  reason: string | null
evaluation:
  source: agent | python_fallback
  semantic_decision: object | null
  matched_evidence: array
  gaps: array
  risks: array
  scoring_breakdown: object | null
  score: number | null
  final_decision: string | null
```

运行账本规则：

- Python fallback 对本次抓取的全部结构化岗位生成基础判断，因此所有报告记录的来源只显示 `agent` 或 `python_fallback`。
- 时间过滤、去重、语义拒绝、阈值和 URL 校验只更新 `processing.stage/reason`，不得从运行账本删除记录。
- Agent 对某条岗位完成判断后，可用同一 Schema 覆盖该条 fallback 结果，并将来源更新为 `agent`。
- Python CLI 没有 Agent 输出时必须显示 `python_fallback`。
- 零推荐、全部被过滤或全部 URL 失效时仍生成报告骨架和全量附录，不得提前返回而丢失本次证据。

## 7. 报告格式

当前 `## Recommended Jobs` 保持兼容，其后追加：

```markdown
## 全量抓取与判断记录

### 1. 公司－岗位标题

| 字段 | 内容 |
|---|---|
| 公司 | |
| 岗位名称 | |
| 地点 | |
| 类别 | |
| 完整职责 | |
| 完整任职要求 | |
| 发布时间 | |
| 工作年限 | |
| 原始链接 | |
| 处理状态 | |
| 判断来源 | agent / python_fallback |
| 最终结论 | |

#### 语义判断与引用证据
- 是否保留、判断理由、JD 引用、简历证据、风险和缺口

#### 评分拆解
- 各维度得分、风险扣分、总分和最终结论
```

报告只引用本次运行数据，不添加人工结论、未来计划或无法由单次任务产生的指标。

### 原始链接硬规则

- 原始岗位 URL 从抓取结果进入运行账本后必须原封不动保存，不得切片、截断、增加省略号或改写查询参数。
- Markdown 同时显示完整 URL 并将同一个完整字符串作为 href，确保可以点击。
- URL 不得使用 `[:N]`、`...`、`…` 或摘要函数处理。
- 若原始 URL 为空、含省略号或无法解析为 `http/https`，必须标记 `url_rejected`，不能生成看似可点击的伪链接。
- 该规则同时写入 `AGENTS.md`、`CLAUDE.md`、报告 Prompt 和 Python 渲染测试，代码层作为最终兜底。

## 8. 独立修复子 Agent

主 Agent 每轮只启动一个 `crawler-strategy-inspector`，将当前待处理任务队列一次性交给它。子 Agent 顺序处理全部公司：

```text
pending task
  -> Python baseline inspection
  -> Python generic interaction evidence
  -> LLM evidence analysis
  -> optional Codex Browser exploration
  -> strategy_decision
  -> deterministic config apply or minimal custom strategy
  -> targeted verification
  -> task status update
  -> next company
```

子 Agent 最终只向主 Agent 返回总数、`verified_existing/repaired/blocked/failed` 状态、变更文件、artifact 路径和短原因。它不读取简历、候选人画像、岗位匹配报告或投递材料。

## 9. Evidence 与策略产物

每家公司统一保存：

```text
logs/crawler_evidence/{company_id}/{run_id}/
├── inspection.json
├── actions.json
├── network.json
├── xhr_samples/
├── page.html
├── page.txt
├── page.png
├── evidence.json
├── strategy_decision.yaml
└── verification.json
```

- `inspection.json`：URL、最终 URL、主页面状态、耗时和页面信号。
- `actions.json`：输入、点击、等待、切换和翻页动作及结果。
- `network.json`：请求、响应状态、脱敏 Payload 和触发动作。
- `strategy_decision.yaml`：LLM 策略、证据引用、配置变更和验证命令。
- `verification.json`：岗位数、字段完整率、URL 有效率、耗时和测试状态。

普通配置型策略由 Python 校验并应用；专用 Python 策略才由子 Agent修改代码。

## 10. 不可修复结果

必须区分并报告：

- `login_required`
- `network_unreachable`
- `captcha`
- `anti_crawl`
- `region_restricted`
- `insufficient_evidence`
- `browser_operation_not_repeatable`

结果必须包含直接证据、已尝试动作、不继续处理的原因和人工下一步。

## 11. 需要修复的现有技术问题

1. `crawler_evidence` 缺少通用交互和主页面 HTTP 状态。
2. `network.json` 缺少响应状态、Payload 和动作来源。
3. `browser_operation` 没有真实执行入口。
4. 有 API 配置的公司会被自动推断为 verified，但没有持久化 fingerprint。
5. 爬虫吞掉异常或返回零岗位时，策略任务可能不触发。
6. 单站验证对零岗位和关键字段缺失没有可靠失败门禁。
7. strategy task 缺少 repaired、blocked、failed 和 verification_failed 等最终状态。
8. 当前流程在过滤为空或零推荐时提前退出，导致本次抓取记录和失败证据不生成报告。
9. 当前浏览器启动包含隐藏自动化特征的 stealth 配置，与“遇到强反爬就报告、不尝试绕过”的边界冲突；采证、修复和验证必须使用标准 Playwright context，并移除相关反检测参数。
10. 需要新增 `.claude/agents/crawler-strategy-inspector.md` 作为 Claude Code 子 Agent 的正式描述；`AGENTS.md` / `CLAUDE.md` 保存主 Agent 委派规则，Codex 运行时按同一描述启动一个子 Agent。

## 12. 测试设计

### 报告测试

- 推荐区保持现有结构。
- 附录包含全部原始链接和结构化字段。
- 语义保留与拒绝岗位都显示证据、评分和结论。
- 时间/去重淘汰岗位仍保留 fallback 判断，同时显示真实过滤阶段和原因。
- Agent 与 fallback 两套字段可以统一渲染。
- 原始 URL 显示和 href 均与输入字符串完全一致，不允许截断或省略号。
- 零推荐时仍生成报告和全量附录。

### 策略工作流测试

- 未知策略进入待处理队列。
- 一个子 Agent 接收完整任务队列并顺序处理。
- Python 通用交互记录 actions 和交互后的响应。
- LLM 输出不符合 Schema 时拒绝应用。
- 普通配置策略由 Python 确定性应用。
- 零岗位、关键字段缺失和 URL 无效使单站验证失败。
- 登录、验证码、网络和强反爬产生明确 blocked 报告。
- 修复后保存 fingerprint 和 verification。
- 采证、修复和验证浏览器上下文不包含 stealth/反检测参数。

### 回归命令

```powershell
python -m pytest tests/test_cli.py -v
python -m pytest tests/test_crawler_evidence.py tests/test_strategy_planner.py tests/test_health_workflow.py tests/test_all_crawlers.py -v
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

真实联网验证由独立子 Agent 在离线测试通过后执行。

## 13. 验收标准

- 当前推荐结果保持兼容。
- 报告底部包含本次抓取的全部原始岗位链接和处理状态。
- 所有进入语义判断的岗位保留证据、评分拆解和最终结论。
- 报告明确区分 Agent 和 Python fallback。
- 原始 URL 原封不动、完整显示并可点击，禁止截断链接。
- 零推荐和全部过滤场景仍产生完整运行报告。
- 主 Agent 只接收子 Agent 汇总，不读取完整公司 evidence。
- 一个独立子 Agent 顺序处理全部待修复公司。
- Python 完成通用浏览器操作、采证、配置校验和验证。
- LLM 只处理 API 结构、字段映射和非固定交互。
- 无法修复的公司有明确原因、证据和下一步。
- 全部离线测试和 Agent regression 通过后才允许本地提交。

## 14. 执行计划（审核通过后执行）

### Phase 0：Git 开工检查

- [x] 在 `main` 执行 `git fetch origin`、`git status -sb`、`git worktree list` 和 `git log -1 --oneline`。
- [x] 若本地 main 落后，使用 `git pull --ff-only origin main`；发现未知修改立即停止。
- [x] 创建 `feature/report-audit-subagent-repair` 功能分支，禁止直接在 main 开发。

### Phase 1：无损运行账本

**新增：** `src/run_records.py`、`tests/test_run_records.py`  
**修改：** `src/cli.py`

- [x] 先写失败测试：两个相同 job ID/Hash 的岗位仍有独立 `run_record_id`。
- [x] 测试 `raw_job` 深拷贝保留 `job_type/product/bg/custom_field` 等全部字段。
- [x] 测试 `original_url` 与输入字符串完全一致。
- [x] 实现 `create_run_records()`、`update_record_stage()`、`attach_evaluation()`。
- [x] 各过滤阶段只更新状态，不从账本删除记录。
- [x] 运行：`python -m pytest tests/test_run_records.py -v`。

### Phase 2：报告结构与完整 URL

**新增：** `src/reporting.py`、`tests/test_reporting.py`  
**修改：** `src/cli.py`、`.claude/skills/jobhunter/prompts/report.md`

- [x] 先写失败测试，断言报告完全采用第 7 节确认的字段顺序。
- [x] 先写长 URL 测试，覆盖 Query、百分号编码和多个参数。
- [x] 断言完整 URL 同时作为可见文本与 Markdown href，禁止 `...`、`…` 和任何切片。
- [x] 实现 Agent/fallback 字段归一化与全量附录渲染。
- [x] Python fallback 对全部原始结构化岗位生成基础判断；Agent 结果可按相同 Schema 覆盖。
- [x] 零推荐、全部过滤或 URL 全失效时仍生成报告骨架和附录。
- [x] 只有最终推荐岗位进入投递包、飞书、多维表格和 memory。
- [x] 运行：`python -m pytest tests/test_reporting.py tests/test_cli.py -v`。

### Phase 3：子 Agent 正式描述与存放结构

**新增：** `.claude/agents/crawler-strategy-inspector.md`  
**修改：** `AGENTS.md`、`CLAUDE.md`、`.claude/skills/jobhunter/skill.md`、`.claude/skills/jobhunter/prompts/analyze_crawler_strategy.md`

- [x] 实现前读取 `agent-designer` Skill 和当前 Claude/Codex 子 Agent 规范。
- [x] `.claude/agents/crawler-strategy-inspector.md` 保存完整角色描述，作为 Claude Code 的正式子 Agent 定义。
- [x] 子 Agent 一次接收全部待修复公司，串行处理，不按公司拆 Agent、不再嵌套。
- [x] `AGENTS.md` / `CLAUDE.md` 只保存委派条件、输入队列、摘要输出和全局硬规则，并保持内容一致。
- [x] Codex 运行时读取同一描述，通过 subagent 工具启动一个实例。
- [x] Skillmap 只维护触发与路由，不复制完整 Agent 定义。
- [x] 将“岗位 URL 原封不动、完整显示、可点击、禁止截断”同步到 Agent 定义与报告 Prompt。

### Phase 4：Python 通用浏览器交互与无 stealth 边界

**新增：** `src/browser_interactions.py`、`tests/test_browser_interactions.py`  
**修改：** `src/base_crawler.py`、`tests/test_base_crawler.py`

- [x] 先写失败测试：通用关键词输入、搜索点击、等待和翻页返回结构化 action trace。
- [x] 先写失败测试：浏览器启动不包含 `AutomationControlled` 和隐藏 `navigator.webdriver` 的脚本。
- [x] 同一测试还必须断言移除伪造 `window.chrome`、`navigator.plugins`、`navigator.languages` 的初始化脚本及其他反检测参数；使用标准 Playwright context。
- [x] 提取并复用稳定的 Playwright 通用交互逻辑。
- [x] 未知页面控件不在 Python 中猜测，交给子 Agent 的 Codex Browser 探索。
- [x] 运行：`python -m pytest tests/test_browser_interactions.py tests/test_base_crawler.py -v`。

### Phase 5：补强 crawler evidence

**修改：** `src/crawler_evidence.py`、`tests/test_crawler_evidence.py`

- [x] 先写失败测试：保存 initial/final URL、主页面 HTTP 状态和耗时。
- [x] 保存 `actions.json`，记录输入、点击、等待、翻页及结果。
- [x] `network.json` 增加响应状态、Content-Type、脱敏 Post Data 和触发 action ID。
- [x] 保存 XHR response sample 与候选岗位数组。
- [x] 严禁保存 Cookie、Authorization、Token 或完整敏感请求头。
- [x] 运行：`python -m pytest tests/test_crawler_evidence.py -v`。
- [x] 检查src里是否存在迭代后无用了但未删除的py文件，进行谨慎清理。只有在任何地方都没有引用的才能删除。


### Phase 6：LLM 策略决策与 Python 确定性应用

**新增：** `src/strategy_applier.py`、`tests/test_strategy_applier.py`  
**修改：** `.claude/skills/jobhunter/prompts/analyze_crawler_strategy.md`

- [x] 先写失败测试：合法/非法 `strategy_decision`、evidence 引用、URL Template 和 blocked 结果。
- [x] LLM 输出 API pattern、data path、field mappings、URL template、证据引用和置信度。
- [x] Python 校验并应用 `config_intercept/config_dom`，只修改目标公司。
- [x] `custom_python` 只生成 Patch Plan，由子 Agent 编写最小专用策略。
- [x] 运行：`python -m pytest tests/test_strategy_applier.py -v`。

### Phase 7：修复任务触发与生命周期

**修改：** `src/strategy_planner.py`、`src/health_monitor.py`、`src/crawler_factory.py`、`src/company_registry.py`  
**测试：** `tests/test_strategy_planner.py`、`tests/test_health_workflow.py`、`tests/test_company_registry.py`、`tests/test_config_crawler.py`

- [x] 先新增失败测试：没有真实验证结果和 fingerprint 时仍被标记 verified。
- [x] 先新增失败测试：异常或可疑零岗位没有生成待分析任务。
- [x] 先新增失败测试：任务无法从 `pending` 更新为 `analyzing/repaired/blocked/failed/verification_failed`。
- [x] 再修改生产代码，使任务保留 `reason`、evidence 路径和状态变更时间。
- [x] 实现时区分真实零岗位、关键词过窄、网络错误和抓取策略失效。
- [x] 运行：`python -m pytest tests/test_strategy_planner.py tests/test_health_workflow.py tests/test_company_registry.py tests/test_config_crawler.py -v`。

### Phase 8：单站验证门禁

**新增：** `src/crawler_verification.py`、`tests/test_crawler_verification.py`  
**修改：** `tests/test_all_crawlers.py`

- [x] 先写失败测试：零岗位、字段缺失、URL 非 HTTP(S) 或 URL 含省略号时没有返回失败。
- [x] 先写失败测试：验证结果无法生成 `verification.json`。
- [x] 实现 `verify_crawler_output()` 和 `write_verification_report()`，最低字段要求为 `title/company/url/duty/requirement`。
- [x] 修改 `tests/test_all_crawlers.py` 的命令入口，使用生产验证模块并返回机器可判定退出码。
- [x] 输出 `verification.json`，包含岗位数、字段完整率、URL 有效率、耗时和状态。
- [x] 运行：`python -m pytest tests/test_crawler_verification.py -v`。

### Phase 9：文档与评估同步

**修改：** `docs/smartjobhunter-agent-design.md`、`README_CN.md`、`evals/regression/jobhunter_core.yaml`、`evals/capability/jobhunter_hard_cases.yaml`

- [x] 同步报告结构、子 Agent 位置、Python/LLM 边界和 Browser/Chrome 使用条件。
- [x] 增加长链接不截断、零推荐报告、Agent/fallback 兼容、blocked 分类和 instruction drift Case。
- [x] 运行：`python -m pytest tests/test_evaluation.py -v`。
- [x] 运行：`python -m src.evaluation --fail-under 1.0`。


### Phase 10：全量离线验证

- [x] 运行：`python -m pytest -v`，要求 0 failed。
- [x] 运行：`python -m src.evaluation --trials 3 --fail-under 1.0`。
- [x] 运行：`python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml`。
- [x] 运行：`git diff --check` 和 `git status -sb`，确认只有计划内文件。
- [x] 测试失败时持续修复并重新运行，全部通过前不提交。

### Phase 11：一个独立子 Agent 真实巡检

- [x] 主 Agent 只启动一个 `crawler-strategy-inspector`，只传入5个待修复公司测试，并完成后告诉我修复时长。
我给你几个
https://app.mokahr.com/campus-recruitment/ruijie/136206#/jobs
https://dcar.jobs.feishu.cn/campus/position/list
https://career.yonyou.com/SU67ac41886202cc7916ae3029/pb/school.html
https://campus.sf-express.com/#/positionList
https://genertec.zhiye.com/custom/813f55cb-8392-5c3d-038e-1f815555e637


- [x] 子 Agent 逐公司执行：Python baseline -> 通用交互采证 -> LLM 分析 -> 必要时 Codex Browser 探索 -> Python 重放/应用 -> 单站验证。
- [x] 登录、网络、验证码、强反爬、地域限制和不可复现交互必须输出 blocked/failed，不得绕过。
- [x] 主 Agent 只接收公司状态、耗时、变更文件、artifact 路径和短原因。
- [x] 运行一次报告冒烟测试，人工检查完整 URL、字段、证据、评分和最终结论。

### Phase 12：本地提交与收尾审核

- [x] 完整验证通过后执行：`git add -A`。
- [x] 创建本地提交：`git commit -m "feat: add auditable reports and isolated crawler repair agent"`。
- [x] 不直接 push main。
- [x] 汇报：`git status -sb`、`git worktree list`、`git log -1 --oneline`、本地 main 与 origin/main 是否一致。
- [ ] 普通 merge：等待用户审核确认，本轮不执行
