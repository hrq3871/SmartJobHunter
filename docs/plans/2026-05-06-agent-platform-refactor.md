# General Agent Job Matching Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not implement before the user reviews and confirms this plan.

**Goal:** 把 SmartJobHunter 从“偏产品经理的 Python 巡检脚本”收敛成一个真正依托 Claude/Codex 等 agent 平台工作的通用求职代理：任何用户放入简历和求职目标后，agent 能做岗位理解、简历理解、语义过滤、匹配评分、报告和爬虫修复判断。

**Architecture:** Agent 平台是主脑，Python 是工具层。Python 不调用 OpenAI/Anthropic API，也不假装自己能做大模型分析；Python 只负责简历文本抽取、官网抓取、确定性预过滤、证据采集、fallback 粗评分、报告落盘和测试入口。Claude/Codex 通过 `CLAUDE.md`、`AGENTS.md`、`.claude/skills/jobhunter/` 执行真正的岗位语义理解、候选人画像、匹配判断、修复分析和最终推荐。现有“自动自愈”降级为“健康检测 + agent 辅助修复工作流”，只是整个 agent 项目的一个子系统。

**Tech Stack:** Python, Playwright, YAML, pytest, Claude Code project instructions/skills, Codex `AGENTS.md` workflow.

---

## 0. 当前结论

这个项目现在不是一个合格的通用 agent 平台项目，主要问题不是“用了 Python”，而是边界和泛化能力错了：

- 当前匹配/过滤不是通用求职匹配。`src/matching.py` 内置 `TERM_GROUPS["product"]`、`ai`、`tob`、`execution` 等产品经理语境词，并在 `match_job_intent()` / `evaluate_job_fit()` 对 `product` 做特殊判断；这对 PM 简历能凑合，但对研发、数据、设计、市场、运营、金融、法务等用户不成立。
- 当前 profile 示例和 README 示例高度产品经理化，容易让 agent 以为项目主场景就是 TOB/AI 产品经理。
- 当前“语义过滤”和“评分”虽然文档说由 Agent 主判，但 Python CLI 实际 fallback 仍会给出机械分数；如果 agent 没真正介入，结果质量会受硬编码规则限制。
- 当前简历解析只是抽文本或返回图片占位，缺少“任意简历 -> 通用候选人画像”的结构化 agent 流程。
- 当前报告模板和 prompt 示例也偏 AI 产品经理，不能稳定服务多行业、多岗位、多 seniority 的用户。
- `README_CN.md` 和 `CLAUDE.md` 写了“自愈系统”“自动分析 API”“自动修复”，但 `src/auto_analyzer.py` 的 `search_official_site()` 直接 `return None`，`_capture_api_requests()` 直接 `return []`。
- `src/health_monitor.py` 的健康检测本质是 smoke test：创建 crawler、跑少量 crawl、看是否有岗位。失败诊断主要靠异常字符串猜。
- `src/health_monitor.py` 的自动修复链路目前也不可靠：`_repair_url()` 调用不存在的 `analyze_company()`；`_repair_api()` 把 `CompanyConfig` dataclass 当 dict 调 `.get()`。
- `src/scheduler.py` 反而写清楚了真实边界：修复任务是“输出提示，由 Agent 执行”，但 README/CLAUDE 把它描述成系统自动修复。
- `.claude/skills/jobhunter/` 已经在描述 agent 流程，但它没有把“健康巡检/修复”定义成足够明确的 agent 操作规程。
- 当前 `src/*.py` 没有真正的大模型客户端调用；这符合新的产品定位，因为大模型分析应由 Claude/Codex 平台承担，而不是 Python 内部调用外部 LLM API。

后续整改原则：

- 不在 Python 里接大模型 API。
- 不把产品经理、TOB、AI 作为默认世界观；它们只能是某个 profile 的输入，不是系统规则。
- 任意用户的匹配依据必须来自三类输入：简历证据、用户求职目标、岗位 JD 本身。
- Agent 输出的候选人画像、岗位画像、过滤判断、评分结果必须有 schema，便于落盘、测试和报告复用。
- Python fallback 只能做保守粗筛和工程兜底，不能冒充最终智能判断。
- 不让 Python 自动覆盖 `config/companies.yaml`，除非 agent 或用户明确执行修改。
- Python 只产出证据和候选信息，agent 平台读证据、分析网页/API、改配置、跑验证。
- 所有文档中的“自动自愈”统一改成“agent 辅助修复”，避免过度承诺。

---

## 1. 文件结构规划

### 新增文件

- `AGENTS.md`
  - Codex 入口说明。让 Codex 在这个仓库里稳定知道“运行巡检”“分析简历”“评估岗位”“健康巡检”“修复爬虫”分别该做什么。
- `docs/agent-platform-contract.md`
  - 项目真实架构边界：agent 做什么、Python 做什么、哪些事情禁止 Python 假装自动完成。
- `docs/general-matching-design.md`
  - 通用匹配设计：任意简历、任意岗位、任意求职方向下如何拆分候选人画像、岗位画像、过滤、评分和报告。
- `config/profile_schema.yaml`
  - 新版求职目标 schema：目标岗位、行业/方向、级别、岗位类型、地点、必须项、加分项、排除项、偏好和阈值。
- `config/matching_rubric.yaml`
  - 通用评分维度配置，不再把产品经理写进代码。
- `docs/agent-health-repair-runbook.md`
  - 面向 Claude/Codex 的健康巡检和爬虫修复操作手册，包含精确命令、输入输出、验收标准。
- `.claude/skills/jobhunter/profile.md`
  - Claude Code 可触发的简历/求职目标理解 skill 文档。
- `.claude/skills/jobhunter/match.md`
  - Claude Code 可触发的通用岗位匹配 skill 文档。
- `.claude/skills/jobhunter/health.md`
  - Claude Code 可触发的健康巡检 skill 文档。
- `.claude/skills/jobhunter/repair_crawler.md`
  - Claude Code 可触发的爬虫修复 skill 文档。
- `.claude/skills/jobhunter/prompts/build_candidate_profile.md`
  - Agent 从任意简历中抽取通用候选人画像的提示词。
- `.claude/skills/jobhunter/prompts/analyze_job.md`
  - Agent 把任意 JD 转成岗位画像的提示词。
- `.claude/skills/jobhunter/prompts/match_candidate_job.md`
  - Agent 根据候选人画像、求职目标和岗位画像做匹配判断的提示词。
- `.claude/skills/jobhunter/prompts/analyze_crawler_failure.md`
  - Agent 读取健康报告和证据包后分析失败原因的提示词。
- `.claude/skills/jobhunter/prompts/propose_company_config.md`
  - Agent 根据网络证据提出 `companies.yaml` 修复方案的提示词。
- `src/crawler_evidence.py`
  - Playwright 网络证据采集器。记录 XHR/fetch 响应、候选岗位数组路径、字段样例、页面标题、最终 URL、截图路径。
- `tests/test_crawler_evidence.py`
  - 单元测试证据采集的纯函数部分，例如 JSON data path 探测、候选字段评分、敏感字段脱敏。
- `tests/test_health_monitor_workflow.py`
  - 单元测试健康巡检输出 repair task，而不是自动改配置。
- `tests/test_profile_schema.py`
  - 测试新版 profile schema 能兼容产品经理、数据分析、研发等不同用户。
- `tests/test_general_matching.py`
  - 测试 Python fallback 不再默认偏产品经理，能按 profile 输入做保守粗筛。
- `tests/fixtures/resumes/`
  - 放匿名化测试简历样例：产品、数据、研发至少各一份。
- `tests/fixtures/jobs/`
  - 放匿名化 JD 样例：产品、数据、研发、运营/销售噪声岗位至少各一份。

### 修改文件

- `CLAUDE.md`
  - 降低过度承诺，补充通用求职 agent 工作流、健康巡检和修复的 agent 操作规程。
- `README.md`
  - 英文文档同步真实能力边界。
- `README_CN.md`
  - 中文文档同步真实能力边界。
- `.claude/skills/jobhunter/skill.md`
  - 主 skill 增加“简历画像”“岗位匹配”“健康巡检”“修复爬虫”的触发分支。
- `.claude/skills/jobhunter/run.md`
  - 明确巡检时哪些判断由 agent 做，哪些由 Python fallback 做。
- `.claude/skills/jobhunter/tools/*.md`
  - 把“工具”改成可执行命令和 Python 函数边界，避免只写概念。
- `src/matching.py`
  - 去掉产品经理硬编码作为核心逻辑；保留为可配置 fallback 或测试 fixture。
- `src/cli.py`
  - 支持新版 profile schema 和 agent 输出落盘；非 agent 模式明确标注为 fallback。
- `src/resume_parser.py`
  - 只负责文本抽取，不声称能完成图片/复杂简历的智能分析；结构化画像交给 agent。
- `src/health_monitor.py`
  - 从“健康监控与自愈系统”改成“健康检测与 repair task 生成器”。
- `src/crawler_factory.py`
  - 默认不再自动尝试修复；失败时生成证据/repair task，并把下一步交给 agent。
- `src/scheduler.py`
  - `--repair` 改成生成 agent repair task，不再暗示 Python 自我修复。
- `src/auto_analyzer.py`
  - 改名语义或降级为兼容 wrapper；禁止继续声称自动分析 API。实际网络采集迁移到 `src/crawler_evidence.py`。
- `src/health_check.py`
  - 标记为 legacy wrapper，统一调用 `health_monitor`，避免两套健康检测入口漂移。
- `config/crawler_schema.py`
  - 增加证据采集输出和 repair task 的 schema 校验。
- `tests/test_config_crawler.py`
  - 保留现有官方站点集成验证，并补充“配置修复后必须可抓取岗位”的回归路径。
- `tests/test_cli.py`
  - 确认 CLI 仍可在非 agent 模式下跑通 Python fallback。

---

## 2. Task 1: 重定通用求职代理产品边界

**Files:**
- Create: `docs/general-matching-design.md`
- Create: `config/profile_schema.yaml`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: 写通用匹配设计文档**

`docs/general-matching-design.md` 必须先回答“这个项目到底靠什么可行”：

```markdown
# General Matching Design

## Core Assumption

SmartJobHunter is useful only if the current agent platform performs semantic judgment.
Python fallback is not the product intelligence. It is a conservative fallback for reproducibility and tests.

## Universal Inputs

- Resume text or extracted resume content
- User target profile
- Company job postings
- Agent-generated candidate profile
- Agent-generated job profile

## Universal Matching Flow

1. Extract resume text with Python.
2. Let the agent build a structured candidate profile.
3. Crawl jobs with Python.
4. Let the agent analyze each JD into a structured job profile.
5. Let the agent match candidate profile + target profile + job profile.
6. Python stores JSON results and renders Markdown.

## What Makes A Match Reliable

- The job's actual core work matches the target role.
- The resume has concrete evidence for the job's core requirements.
- The match result quotes evidence from both resume and JD.
- The result distinguishes strong match, adjacent match, potential match, and skip.
```

- [ ] **Step 2: 设计新版 profile schema**

`config/profile_schema.yaml` 不要以产品经理为中心：

```yaml
required:
  - name
  - enabled
  - resume
  - target_roles
optional:
  - target_domains
  - employment_types
  - seniority
  - locations
  - must_have
  - nice_to_have
  - avoid
  - dealbreakers
  - preferences
  - threshold_score
  - max_jobs_per_report
example:
  name: "数据分析-实习"
  enabled: true
  resume: "./resumes/example_data_resume.pdf"
  target_roles:
    - "数据分析实习生"
    - "商业分析实习生"
  target_domains:
    - "互联网"
    - "金融科技"
  employment_types:
    - "实习"
  must_have:
    - "SQL"
    - "Python"
    - "数据分析项目"
  nice_to_have:
    - "A/B 实验"
    - "指标体系"
  avoid:
    - "电话销售"
    - "纯运营"
```

- [ ] **Step 3: README/CLAUDE 降低产品经理中心化**

替换 README/README_CN 中“产品经理”作为唯一示例的写法，至少提供三类示例：

- 产品经理
- 数据分析/商业分析
- 研发/算法/工程

并明确：

```markdown
项目不是只给产品经理用。产品经理只是示例 profile。
通用能力来自 agent 对简历、JD 和求职目标的语义判断。
```

- [ ] **Step 4: 写可行性边界**

在 `docs/general-matching-design.md` 写明：

```markdown
## Limitations

- Without an agent actively applying prompts, Python CLI results are fallback quality.
- Weak JD content cannot produce high-confidence recommendations.
- A vague user target profile will produce vague matching.
- The project should show "needs review" instead of pretending confidence when evidence is weak.
```

- [ ] **Step 5: 文档检查**

Run:

```bash
Select-String -Path README.md,README_CN.md,CLAUDE.md,docs\general-matching-design.md -Pattern "产品经理|任意简历|fallback|Agent|证据"
```

Expected:

- 产品经理只作为示例出现。
- 文档明确说明 agent 是主判断层，Python 是 fallback/tooling。

- [ ] **Step 6: Commit**

```bash
git add README.md README_CN.md CLAUDE.md AGENTS.md docs/general-matching-design.md config/profile_schema.yaml
git commit -m "docs: define general agent matching model"
```

---

## 3. Task 2: 把简历和 JD 都结构化为 Agent 可判断对象

**Files:**
- Create: `.claude/skills/jobhunter/profile.md`
- Create: `.claude/skills/jobhunter/match.md`
- Create: `.claude/skills/jobhunter/prompts/build_candidate_profile.md`
- Create: `.claude/skills/jobhunter/prompts/analyze_job.md`
- Create: `.claude/skills/jobhunter/prompts/match_candidate_job.md`
- Modify: `.claude/skills/jobhunter/prompts/analyze_resume.md`
- Modify: `.claude/skills/jobhunter/prompts/semantic_filter.md`
- Modify: `.claude/skills/jobhunter/prompts/evaluate.md`
- Modify: `.claude/skills/jobhunter/prompts/report.md`

- [ ] **Step 1: 写 candidate profile prompt**

`build_candidate_profile.md` 输出固定 JSON，不要输出散文：

```json
{
  "candidate_summary": "...",
  "role_experience": [
    {
      "role_family": "product | data | engineering | design | marketing | operations | finance | legal | other",
      "years": null,
      "evidence": ["resume quote 1", "resume quote 2"]
    }
  ],
  "skills": {
    "hard_skills": [],
    "domain_skills": [],
    "tools": [],
    "soft_skills": []
  },
  "project_evidence": [
    {
      "project": "...",
      "actions": [],
      "impact": [],
      "evidence_quote": "..."
    }
  ],
  "constraints": [],
  "missing_or_unclear": []
}
```

- [ ] **Step 2: 写 job profile prompt**

`analyze_job.md` 输出：

```json
{
  "job_title": "...",
  "role_family": "...",
  "seniority": "intern | junior | mid | senior | lead | unknown",
  "employment_type": "internship | campus | full_time | contractor | unknown",
  "core_responsibilities": [],
  "must_have_requirements": [],
  "nice_to_have_requirements": [],
  "domain_context": [],
  "risk_signals": [],
  "evidence_quotes": []
}
```

- [ ] **Step 3: 写通用 match prompt**

`match_candidate_job.md` 的评分不固定产品维度：

```json
{
  "should_keep": true,
  "score": 82,
  "confidence": "high | medium | low",
  "decision": "strong_apply | apply | consider | needs_review | skip",
  "breakdown": {
    "target_role_fit": 0,
    "core_responsibility_fit": 0,
    "resume_evidence_fit": 0,
    "domain_or_industry_fit": 0,
    "preference_fit": 0,
    "risk_penalty": 0
  },
  "matched_evidence": [
    {
      "job_requirement": "...",
      "resume_evidence": "...",
      "strength": "strong | partial | weak"
    }
  ],
  "gaps": [],
  "risks": [],
  "why_not_higher": "...",
  "application_advice": []
}
```

- [ ] **Step 4: 改旧 prompts**

删除旧 prompt 中默认产品经理、TOB、AI 的示例作为主样例。保留时必须标注：

```markdown
The following is only one example profile, not a global rule.
```

- [ ] **Step 5: 增加 agent 触发说明**

`.claude/skills/jobhunter/skill.md` 增加分支：

```markdown
If the user provides a resume or asks whether jobs fit them, first build `candidate_profile`.
If the user asks for job inspection, crawl jobs first, then analyze each JD before matching.
Do not rely on keyword hits as the final decision.
```

- [ ] **Step 6: 文档检查**

Run:

```bash
Select-String -Path '.claude\skills\jobhunter\prompts\*.md','.claude\skills\jobhunter\*.md' -Pattern "TOB产品|AI产品经理|产品经理|target_role_fit|candidate_profile|job_profile"
```

Expected:

- `candidate_profile`、`job_profile`、`target_role_fit` 出现在新 prompts。
- 产品经理相关文本只出现在明确标注的示例里。

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/jobhunter
git commit -m "docs: generalize agent matching prompts"
```

---

## 4. Task 3: 重构 Python fallback，去掉产品经理硬编码

**Files:**
- Create: `config/matching_rubric.yaml`
- Create: `tests/fixtures/resumes/product_pm.md`
- Create: `tests/fixtures/resumes/data_analyst.md`
- Create: `tests/fixtures/resumes/software_engineer.md`
- Create: `tests/fixtures/jobs/product_job.yaml`
- Create: `tests/fixtures/jobs/data_job.yaml`
- Create: `tests/fixtures/jobs/engineering_job.yaml`
- Create: `tests/fixtures/jobs/sales_noise_job.yaml`
- Create: `tests/test_profile_schema.py`
- Create: `tests/test_general_matching.py`
- Modify: `src/matching.py`
- Modify: `src/cli.py`
- Modify: `src/resume_parser.py`
- Modify: `README.md`
- Modify: `README_CN.md`

- [ ] **Step 1: 写失败测试：数据分析 profile 不应被产品经理规则误伤**

`tests/test_general_matching.py`：

```python
def test_data_profile_keeps_data_analyst_job_without_product_terms():
    from src.matching import match_job_intent

    profile = {
        "target_roles": ["数据分析师", "商业分析师"],
        "must_have": ["SQL", "Python", "指标分析"],
        "avoid": ["销售", "客服"],
    }
    job = {
        "title": "数据分析实习生",
        "duty": "负责业务指标分析、SQL取数、看板建设",
        "requirement": "熟悉 Python 和 SQL，有数据分析项目经验",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6
```

- [ ] **Step 2: 写失败测试：研发 profile 不应需要产品经理信号**

```python
def test_engineering_profile_keeps_backend_engineer_job():
    from src.matching import match_job_intent

    profile = {
        "target_roles": ["后端开发工程师"],
        "must_have": ["Python", "分布式系统", "数据库"],
        "avoid": ["销售", "运营"],
    }
    job = {
        "title": "后端开发工程师",
        "duty": "负责服务端架构、接口开发、数据库性能优化",
        "requirement": "熟悉 Python/Go，了解分布式系统",
    }

    result = match_job_intent(job, profile)

    assert result["should_keep"] is True
```

- [ ] **Step 3: 写失败测试：销售噪声岗位应被排除**

```python
def test_avoid_terms_filter_sales_noise_for_any_profile():
    from src.matching import match_job_intent

    profile = {
        "target_roles": ["数据分析师"],
        "must_have": ["SQL"],
        "avoid": ["销售", "电话销售"],
    }
    job = {
        "title": "数据产品销售顾问",
        "duty": "负责电话销售和客户转化",
        "requirement": "有销售经验优先",
    }

    result = match_job_intent(job, profile)

    assert result["should_keep"] is False
```

- [ ] **Step 4: 运行测试确认失败**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_general_matching.py
```

Expected: 至少数据和研发用例失败，暴露当前 `TERM_GROUPS["product"]` 偏置。

- [ ] **Step 5: 改 `src/matching.py` 的输入模型**

新增 profile 读取函数：

```python
def profile_target_terms(profile: dict) -> dict:
    return {
        "target_roles": _as_terms(profile.get("target_roles") or [profile.get("name", "")]),
        "target_domains": _as_terms(profile.get("target_domains") or []),
        "must_have": _as_terms(profile.get("must_have") or profile.get("keywords") or []),
        "nice_to_have": _as_terms(profile.get("nice_to_have") or []),
        "avoid": _as_terms(profile.get("avoid") or profile.get("exclude_keywords") or []),
    }
```

原则：

- `target_roles` 决定核心岗位方向。
- `must_have` 是强证据，不等于关键词命中就高分。
- `avoid/dealbreakers` 是强排除。
- `TERM_GROUPS` 不再决定系统默认职业，只能作为可选 synonym helper。

- [ ] **Step 6: 改 intent fallback 评分**

fallback 只做通用粗判：

```python
score = 0
if title_or_core_text_hits(target_roles):
    score += 0.35
if core_text_hits(must_have):
    score += up_to_0.35
if domain_hits(target_domains):
    score += up_to_0.15
if nice_to_have_hits:
    score += up_to_0.1
if avoid_hits_in_title:
    score -= 0.6
elif avoid_hits:
    score -= 0.25
if evidence_is_title_only:
    score -= 0.15
```

返回结构保留兼容字段：

```python
{
  "should_keep": bool,
  "match_score": 0.0,
  "match_reasons": [],
  "concerns": [],
  "evidence": {},
  "fallback_quality": "coarse",
}
```

- [ ] **Step 7: 改 fit scoring**

`evaluate_job_fit()` 不再把 `core_role_fit` 绑定产品词，改为：

- `target_role_fit` 0-25
- `core_responsibility_fit` 0-25
- `resume_evidence_fit` 0-25
- `preference_fit` 0-10
- `evidence_quality` 0-10
- `risk_penalty` 0-20

为了兼容旧报告，短期可在输出中同时保留旧字段 alias：

```python
"core_role_fit": target_role_fit
```

- [ ] **Step 8: 改 profile parser**

`src/cli.py` 解析 profiles 时支持新版字段，并兼容旧字段：

- 旧 `keywords` -> 新 `must_have`
- 旧 `exclude_keywords` -> 新 `avoid`
- 旧 `job_type` -> 新 `employment_types`

- [ ] **Step 9: 改 resume parser 声明**

`src/resume_parser.py` 只声明：

```python
"""Extract raw text from resume files. Agent prompts build the structured candidate profile."""
```

不要再写“Claude Vision 解析图片简历”像是 Python 已经能解析。

- [ ] **Step 10: 测试**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_general_matching.py
pytest -q -p no:cacheprovider tests/test_profile_schema.py
pytest -q -p no:cacheprovider tests/test_matching.py
pytest -q -p no:cacheprovider tests/test_cli.py
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add config/matching_rubric.yaml src/matching.py src/cli.py src/resume_parser.py tests/test_general_matching.py tests/test_profile_schema.py tests/fixtures README.md README_CN.md
git commit -m "refactor: generalize matching fallback beyond product roles"
```

---

## 5. Task 4: 先固化 Agent/Python 边界

**Files:**
- Create: `docs/agent-platform-contract.md`
- Create: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `README_CN.md`

- [ ] **Step 1: 写真实架构契约文档**

在 `docs/agent-platform-contract.md` 写清楚：

```markdown
# SmartJobHunter Agent Platform Contract

## Product Position

SmartJobHunter is an agent-platform project, not a standalone autonomous Python bot.

## Agent Responsibilities

- Understand user requests such as "运行巡检", "健康巡检", "修复腾讯爬虫".
- Run the documented Python tools.
- Inspect health reports and network evidence.
- Use the current agent platform browser/network/search capability when deeper web analysis is needed.
- Modify `config/companies.yaml`, docs, or Python code when evidence supports the change.
- Run targeted tests and live official-site validation.
- Ask the user before committing or merging.

## Python Responsibilities

- Crawl configured company career pages.
- Apply deterministic filters, dedup, fallback scoring, and report rendering.
- Capture network evidence with Playwright.
- Generate health reports and repair task files.
- Validate config shape and run tests.

## Non-goals

- Python does not call external LLM APIs for analysis.
- Python does not silently rewrite crawler config after guessing.
- Health check is not proof that the whole application workflow is correct.
```

- [ ] **Step 2: 创建 Codex 入口 `AGENTS.md`**

`AGENTS.md` 要引用同一个契约，避免 Codex 不读 `.claude/skills` 时行为不稳定：

```markdown
# SmartJobHunter Agent Instructions

When the user asks for "运行巡检", run the job inspection workflow in `docs/agent-platform-contract.md` and `docs/agent-health-repair-runbook.md`.

When the user asks for "健康巡检", do not only explain. Run:

```bash
python -m src.health_monitor --check-all
```

If a crawler fails, collect evidence before proposing fixes:

```bash
python -m src.crawler_evidence --company <company_id> --keyword "产品经理" --job-type social
```

Python produces evidence. The current agent analyzes evidence and decides what to patch.
```

- [ ] **Step 3: 修改 `CLAUDE.md`**

把“自愈系统”改成“健康检测 + Agent 辅助修复”：

```markdown
## 健康巡检与修复边界

健康巡检不是 Python 自动修复。正确流程：

1. 运行 `python -m src.health_monitor --check <id>` 或 `--check-all`
2. 如果失败，运行 `python -m src.crawler_evidence --company <id> --keyword "产品经理" --job-type social`
3. Agent 读取 health report 和 evidence JSON
4. Agent 判断是 URL 失效、API pattern 变化、data_path 变化、字段映射变化、登录/反爬，还是网站暂无岗位
5. Agent 修改配置或代码
6. Agent 运行测试和官方站点验证
```

- [ ] **Step 4: 修改 README/README_CN 的过度承诺**

替换这些表述：

- “自动自愈系统” -> “健康检测与 Agent 辅助修复”
- “API 变化自动修复 ✅” -> “可生成证据包，由 Agent 分析并修复”
- “42 家已启用，API 已验证” -> 改成“配置中启用的公司以当前测试结果为准”，避免把历史验证当永久事实。

- [ ] **Step 5: 文档检查**

Run:

```bash
Select-String -Path README.md,README_CN.md,CLAUDE.md,AGENTS.md -Pattern "自动自愈|自动修复|重新分析 API|API 已验证"
```

Expected:

- 不再出现无条件承诺“Python 自动修复”的表述。
- 如果出现“自动修复”，上下文必须明确是 agent 辅助，不是 Python 自行分析和覆盖配置。

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md CLAUDE.md README.md README_CN.md docs/agent-platform-contract.md
git commit -m "docs: define agent platform boundaries"
```

---

## 6. Task 5: 把健康巡检改成证据优先

**Files:**
- Modify: `src/health_monitor.py`
- Modify: `src/crawler_factory.py`
- Modify: `src/scheduler.py`
- Modify: `src/health_check.py`
- Modify: `config/crawler_schema.py`
- Test: `tests/test_health_monitor_workflow.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_health_monitor_workflow.py`，先锁定新行为：

```python
def test_diagnosis_generates_agent_repair_task_without_auto_patch(tmp_path):
    from src.health_monitor import Diagnosis, FailureType, HealthMonitor

    monitor = HealthMonitor(config_path="config/companies.yaml", repair_dir=tmp_path)
    diagnosis = Diagnosis(
        company_id="tencent",
        failure_type=FailureType.API_CHANGED,
        reason="API response no longer matches data_path",
        agent_repairable=True,
        suggested_action="collect_network_evidence",
    )

    task = monitor.create_repair_task("tencent", diagnosis)

    assert task["company_id"] == "tencent"
    assert task["repair_owner"] == "agent"
    assert task["python_may_patch_config"] is False
    assert "python -m src.crawler_evidence" in task["next_commands"][0]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_health_monitor_workflow.py
```

Expected: FAIL because `create_repair_task` and new fields do not exist.

- [ ] **Step 3: 修改 `Diagnosis` 数据结构**

把 `can_auto_repair` 改成更准确的字段：

```python
@dataclass
class Diagnosis:
    company_id: str
    failure_type: FailureType
    reason: str
    agent_repairable: bool = False
    suggested_action: str = ""
```

兼容期可以保留只读 property：

```python
@property
def can_auto_repair(self) -> bool:
    return self.agent_repairable
```

- [ ] **Step 4: 增加 `create_repair_task()`**

`src/health_monitor.py` 新增：

```python
def create_repair_task(self, company_id: str, diagnosis: Diagnosis) -> dict:
    task = {
        "company_id": company_id,
        "failure_type": diagnosis.failure_type.value,
        "reason": diagnosis.reason,
        "repair_owner": "agent",
        "python_may_patch_config": False,
        "next_commands": [
            f'python -m src.crawler_evidence --company {company_id} --keyword "产品经理" --job-type social'
        ],
        "agent_instructions": [
            "Read the generated evidence JSON.",
            "Identify whether url, api.pattern, api.data_path, or field_mappings changed.",
            "Patch config only after evidence supports the change.",
            "Run targeted crawler validation after patching.",
        ],
    }
    return task
```

- [ ] **Step 5: 修改 `crawler_factory.py`**

当前 `_attempt_repair()` 会尝试 `monitor.auto_repair()` 并重试。改成：

```python
diagnosis = monitor.diagnose_failure(company_id, error)
task = monitor.create_repair_task(company_id, diagnosis)
monitor.save_repair_task(task)
notify_repair_failed(company_id, diagnosis.reason, task["next_commands"])
return []
```

保留参数名时，将默认值改成更准确：

```python
agent_repair_task: bool = True
```

如果为了兼容暂时保留 `auto_repair`，文档中注明它只生成 agent repair task。

- [ ] **Step 6: 修改 `scheduler.py`**

`--repair` 只生成 repair task，不再打印“自我修复已启动”。输出改成：

```text
已生成 Agent 修复任务: logs/repair_tasks.json
下一步：让 Claude/Codex 读取该文件，运行 crawler_evidence，并按证据修改配置。
```

- [ ] **Step 7: 修改 `health_check.py` 为兼容入口**

不要维护两套健康巡检。`health_check.py` 只调用 `HealthMonitor.check_all()`，并在文件头注释：

```python
"""Legacy compatibility entrypoint. Prefer python -m src.health_monitor."""
```

- [ ] **Step 8: 测试**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_health_monitor_workflow.py
pytest -q -p no:cacheprovider tests/test_cli.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/health_monitor.py src/crawler_factory.py src/scheduler.py src/health_check.py config/crawler_schema.py tests/test_health_monitor_workflow.py
git commit -m "refactor: make health checks generate agent repair tasks"
```

---

## 7. Task 6: 实现 Python 证据采集器，而不是 Python 大模型分析器

**Files:**
- Create: `src/crawler_evidence.py`
- Modify: `src/auto_analyzer.py`
- Test: `tests/test_crawler_evidence.py`

- [ ] **Step 1: 写纯函数测试**

`tests/test_crawler_evidence.py`：

```python
def test_find_job_array_candidates_scores_job_like_arrays():
    from src.crawler_evidence import find_job_array_candidates

    payload = {
        "data": {
            "job_post_list": [
                {"id": "1", "title": "AI 产品经理", "description": "负责大模型产品"}
            ]
        }
    }

    candidates = find_job_array_candidates(payload)

    assert candidates[0]["path"] == "data.job_post_list"
    assert candidates[0]["item_count"] == 1
    assert "title" in candidates[0]["field_hints"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_crawler_evidence.py
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: 实现 `find_job_array_candidates()`**

核心只做确定性启发式，不做 LLM 判断：

```python
JOB_FIELD_HINTS = {
    "id", "jobId", "postId", "positionId",
    "title", "name", "jobName", "RecruitPostName",
    "description", "requirement", "responsibility", "jobDuty",
    "city", "location", "workPlace",
}
```

递归扫描 dict/list，找“list of dict”，根据字段名和文本长度打分，返回候选路径和样例字段。

- [ ] **Step 4: 实现 Playwright 网络证据采集**

CLI:

```bash
python -m src.crawler_evidence --company tencent --keyword "产品经理" --job-type social
python -m src.crawler_evidence --url "https://careers.tencent.com/search.html?query=产品经理" --company tencent
python -m src.crawler_evidence --company tencent --keyword "产品经理" --job-type social --headful
```

输出文件：

```text
logs/crawler_evidence/tencent/20260506_153000/evidence.json
logs/crawler_evidence/tencent/20260506_153000/page.png
```

`evidence.json` 结构：

```json
{
  "company_id": "tencent",
  "company_name": "腾讯",
  "input_url": "...",
  "final_url": "...",
  "page_title": "...",
  "keyword": "产品经理",
  "captured_at": "2026-05-06T15:30:00+08:00",
  "responses": [
    {
      "url": "...",
      "status": 200,
      "resource_type": "xhr",
      "content_type": "application/json",
      "matched_existing_pattern": true,
      "job_array_candidates": [
        {"path": "Data.Posts", "score": 12, "item_count": 10}
      ],
      "sample_keys": ["PostId", "RecruitPostName", "Responsibility"]
    }
  ],
  "agent_next_steps": [
    "Compare top candidate paths with config.companies.<id>.api.data_path.",
    "Compare sample keys with field_mappings.",
    "Patch config only if evidence supports it."
  ]
}
```

- [ ] **Step 5: 处理敏感信息**

证据文件不得保存 cookie、authorization header、完整 token、个人身份信息。只保存 URL、status、content-type、JSON 样例键、候选路径和最多 3 条岗位样例的截断字段。

- [ ] **Step 6: 降级 `auto_analyzer.py`**

短期保留命令兼容，但文案必须改：

```text
auto_analyzer is deprecated. Use crawler_evidence to collect evidence, then let the agent analyze it.
```

不要再让 `auto_analyzer.py` 声称会自动搜索官网或自动分析 API。

- [ ] **Step 7: 测试**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_crawler_evidence.py
python -m src.crawler_evidence --company tencent --keyword "产品经理" --job-type social
```

Expected:

- 单元测试 PASS。
- 真实命令生成 `logs/crawler_evidence/.../evidence.json`。
- JSON 中至少记录页面信息；如果抓到 XHR/fetch，应包含候选 job array path。

- [ ] **Step 8: Commit**

```bash
git add src/crawler_evidence.py src/auto_analyzer.py tests/test_crawler_evidence.py
git commit -m "feat: collect crawler evidence for agent analysis"
```

---

## 8. Task 7: 完善 Claude/Codex 可执行工作流

**Files:**
- Create: `docs/agent-health-repair-runbook.md`
- Create: `.claude/skills/jobhunter/health.md`
- Create: `.claude/skills/jobhunter/repair_crawler.md`
- Create: `.claude/skills/jobhunter/prompts/analyze_crawler_failure.md`
- Create: `.claude/skills/jobhunter/prompts/propose_company_config.md`
- Modify: `.claude/skills/jobhunter/skill.md`
- Modify: `.claude/skills/jobhunter/run.md`
- Modify: `.claude/skills/jobhunter/tools/crawl.md`
- Modify: `.claude/skills/jobhunter/tools/load_config.md`

- [ ] **Step 1: 写 runbook**

`docs/agent-health-repair-runbook.md` 必须包含这三条入口：

```markdown
## 用户说：健康巡检

Run:

```bash
python -m src.health_monitor --check-all
```

If failures exist, run evidence collection for each failed enabled company:

```bash
python -m src.crawler_evidence --company <id> --keyword "产品经理" --job-type social
```

## 用户说：修复某家公司爬虫

1. Run health check for that company.
2. Collect crawler evidence.
3. Read `config/companies.yaml` for current config.
4. Compare evidence candidate paths and fields with current config.
5. Patch config or code.
6. Run targeted validation.

## 用户说：运行巡检

Run:

```bash
python -m src.cli
```

Then inspect `output/` report and summarize.
```

- [ ] **Step 2: 新增 `health.md` skill**

内容要直接给 Claude 可执行命令，不写空泛描述：

```markdown
---
name: health
description: 运行 SmartJobHunter 健康巡检并生成 agent 修复任务
user_invocable: true
---

# 健康巡检

Trigger when the user says "健康巡检", "检查爬虫", "哪些公司挂了".

Run:

```bash
python -m src.health_monitor --check-all
```

If any company fails, collect evidence:

```bash
python -m src.crawler_evidence --company <company_id> --keyword "产品经理" --job-type social
```

Do not claim Python fixed it. Analyze the evidence yourself as the agent.
```

- [ ] **Step 3: 新增 `repair_crawler.md` skill**

写清楚 agent 的判断步骤：

```markdown
1. Read current company config.
2. Run health check.
3. Run crawler_evidence.
4. Inspect evidence JSON:
   - final_url changed?
   - existing api.pattern captured?
   - better job_array_candidates path?
   - field names changed?
   - login/captcha/403?
5. Patch only the smallest supported config/code change.
6. Run live validation.
```

- [ ] **Step 4: 新增 failure analysis prompt**

`analyze_crawler_failure.md` 输出固定 JSON：

```json
{
  "failure_type": "api_pattern_changed | data_path_changed | field_mapping_changed | url_invalid | login_required | anti_crawl | no_jobs | unknown",
  "evidence": ["..."],
  "recommended_change": "...",
  "needs_user_action": false,
  "validation_commands": ["..."]
}
```

- [ ] **Step 5: 修改主 skill 触发分支**

`.claude/skills/jobhunter/skill.md` 增加：

```markdown
If the user asks for health check or crawler repair, route to `health.md` or `repair_crawler.md` instead of the normal job inspection flow.
```

- [ ] **Step 6: 文档检查**

Run:

```bash
Select-String -Path '.claude\skills\jobhunter\*.md','.claude\skills\jobhunter\prompts\*.md','docs\agent-health-repair-runbook.md' -Pattern 'python -m src.health_monitor|python -m src.crawler_evidence|Python .*自动修复'
```

Expected:

- 能搜到健康巡检和证据采集命令。
- 搜不到“Python 自动修复”的无边界承诺。

- [ ] **Step 7: Commit**

```bash
git add docs/agent-health-repair-runbook.md .claude/skills/jobhunter
git commit -m "docs: add agent health repair workflow"
```

---

## 9. Task 8: 清理双重爬虫入口和错误命名

**Files:**
- Modify: `src/crawler.py`
- Modify: `src/crawler_factory.py`
- Modify: `src/config_crawler.py`
- Modify: `tests/test_config_crawler.py`
- Modify: `tests/test_all_crawlers.py`
- Modify: `README.md`
- Modify: `README_CN.md`

- [ ] **Step 1: 确认当前默认路径**

Run:

```bash
Select-String -Path src\*.py,tests\*.py -Pattern "src\.crawler|from \.crawler|crawler_factory|crawl_company|get_enabled_companies"
```

Expected:

- `src.cli` 默认走 `crawler_factory`。
- `src.health_check` 旧入口走 `src.crawler`，需要改为 wrapper。
- `tests/test_all_crawlers.py` 如果仍走旧 `src.crawler`，要决定是否迁移到 `crawler_factory`。

- [ ] **Step 2: 确定 source of truth**

采用：

- `crawler_factory.py` + `config_crawler.py` 是默认运行路径。
- `crawler.py` 是 legacy/special-case fallback，只保留有明确价值的公司特化逻辑。
- README 不再说“添加新公司无需写代码”作为绝对承诺，改为“优先配置驱动；特殊站点可能需要代码适配”。

- [ ] **Step 3: 改测试入口**

`tests/test_all_crawlers.py` 默认调用：

```python
from src import crawler_factory

jobs = crawler_factory.crawl_company(company_id, keyword, max_jobs=max_jobs, job_type=job_type, headless=True)
```

如果需要测试 legacy crawler，单独标记：

```python
@pytest.mark.legacy
```

- [ ] **Step 4: 更新文档**

README/README_CN 中新增：

```markdown
### Crawler source of truth

The default crawler path is config-driven:

`src.cli` -> `src.crawler_factory` -> `src.config_crawler` -> `src.base_crawler` / `src.dom_crawler`

`src.crawler` contains legacy or special-case crawlers and should not be used for new company configs unless the config-driven crawler cannot support the site.
```

- [ ] **Step 5: 测试**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_config_crawler.py
pytest -q -p no:cacheprovider tests/test_cli.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crawler.py src/crawler_factory.py src/config_crawler.py tests/test_config_crawler.py tests/test_all_crawlers.py README.md README_CN.md
git commit -m "refactor: clarify config driven crawler path"
```

---

## 10. Task 9: 端到端验证真实 agent 工作流

**Files:**
- Modify: `tests/test_config_crawler.py`
- Modify: `docs/agent-health-repair-runbook.md`
- Modify: `README_CN.md`
- Modify: `README.md`

- [ ] **Step 1: 单元测试**

Run:

```bash
pytest -q -p no:cacheprovider tests/test_crawler_evidence.py
pytest -q -p no:cacheprovider tests/test_health_monitor_workflow.py
pytest -q -p no:cacheprovider tests/test_matching.py
pytest -q -p no:cacheprovider tests/test_cli.py
```

Expected: PASS.

- [ ] **Step 2: 非 integration 全量测试**

Run:

```bash
pytest -q -p no:cacheprovider -m "not integration"
```

Expected: PASS.

- [ ] **Step 3: 官方站点小规模验证**

Run:

```bash
python tests/test_all_crawlers.py --company tencent --keyword "产品经理" --max-jobs 3
python tests/test_all_crawlers.py --company bytedance --keyword "产品经理" --max-jobs 3
python tests/test_all_crawlers.py --company meituan --keyword "产品经理" --max-jobs 3
```

Expected:

- 每家公司命令能访问官方站点。
- 至少产生明确结果：抓到岗位、无岗位、登录/反爬、或 API 变化证据。
- 如果失败，必须生成 evidence 文件，而不是只输出异常字符串。

- [ ] **Step 4: 健康巡检验证**

Run:

```bash
python -m src.health_monitor --check tencent
python -m src.health_monitor --check-all
```

Expected:

- 成功公司显示 jobs_found。
- 失败公司输出 repair task 路径和下一步 `crawler_evidence` 命令。
- 输出不再声称 Python 已自动修复。

- [ ] **Step 5: Agent 修复干跑**

用临时配置制造一个 API pattern 错误，不能直接改真实 `config/companies.yaml`：

```bash
Copy-Item config\companies.yaml logs\companies.health-test.yaml
```

手动把临时文件中 `tencent.api.pattern` 改错，然后运行：

```bash
python -m src.health_monitor --config logs\companies.health-test.yaml --check tencent
python -m src.crawler_evidence --company tencent --keyword "产品经理" --job-type social
```

Expected:

- health monitor 报失败并生成 repair task。
- crawler evidence 抓到候选响应。
- Agent 能从 evidence 判断真实 pattern/data_path，并提出修复。

- [ ] **Step 6: 更新验证记录**

如果用户确认这是要执行的功能优化，再更新 `docs/optimization-log.md`，补：

```markdown
### 2026-05-06 Agent 平台边界与健康修复工作流收敛

**问题**
- ...

**方案**
- ...

**效果**
- ...

**后续**
- ...
```

- [ ] **Step 7: Commit**

```bash
git add tests docs README.md README_CN.md
git commit -m "test: validate agent health repair workflow"
```

---

## 11. 验收标准

最终完成后，必须满足：

- 用户说“健康巡检”时，Claude/Codex 有明确入口文档指导它运行健康检测，而不是靠猜。
- 健康检测失败时，Python 输出结构化 repair task 和 evidence 采集命令。
- Python 不声称自己能调用大模型分析，也不自动覆盖公司配置。
- Agent 能读取 evidence JSON，判断是 URL、API pattern、data_path、field mapping、登录/反爬还是暂无岗位问题。
- README/README_CN/CLAUDE/AGENTS 对项目能力边界描述一致。
- `auto_analyzer.py` 不再作为假的“自动分析 API”卖点。
- 默认爬虫路径明确，避免 `src.crawler.py` 和 `crawler_factory.py` 继续漂移。
- 单元测试和非 integration 测试通过。
- 至少腾讯、字节、美团三家公司完成一次官方站点小规模验证，结果按日期记录为快照，不当成永久事实。

---

## 12. 执行顺序建议

不要一次性大改。建议按下面顺序执行并分阶段 commit：

1. 先做 Task 1：文档和边界收敛。
2. 再做 Task 2：健康巡检不再自动修复，只生成 repair task。
3. 再做 Task 3：实现 evidence 采集。
4. 再做 Task 4：把 Claude/Codex 工作流写成可触发、可执行的 agent 指南。
5. 再做 Task 5：清理爬虫入口漂移。
6. 最后做 Task 6：测试和官方站点验证。

每个 Task 结束后都先运行对应测试，再 commit。全部完成后，再按仓库规则询问用户：

```text
这次改动准备收尾了，请确认：
1. merge 到 main
2. 用当前分支覆盖 main，先备份旧 main
```
