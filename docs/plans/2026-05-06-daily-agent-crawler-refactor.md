# Daily Agent Crawler Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SmartJobHunter 重构成“每日主动巡检公司官网链接、采集证据、由当前 Agent 分析抓取策略、再把可复用策略固化到配置或 Python”的 agent-platform 项目。

**Architecture:** Python 负责读取用户配置的官网链接、执行可复现抓取、采集页面/网络/DOM 证据、运行已固化策略和测试；Claude/Codex Agent 负责判断新链接或失效链接应该怎么抓、是否需要打开浏览器操作、以及把稳定策略写回 `config/companies.yaml` 或专用 Python strategy。每日任务必须先做链接/策略巡检，再进入岗位抓取和匹配，不等用户发现爬取失败后才分析。

**Tech Stack:** Python 3, Playwright, YAML, pytest, current Claude/Codex agent platform, existing `src.crawler_factory`, `src.config_crawler`, `src.crawler_evidence`, `src.matching`.

---

## 0. 当前问题结论

1. `src.cli` 现在是“按 profile 第一个 keyword 直接跑已启用公司”，不是“每天读取公司链接并主动分析策略”。
2. `crawler_factory.py`、`health_monitor.py` 仍使用“自愈/自动修复”命名，但真实能力不完整。
3. `auto_analyzer.py` 声称搜索官网和捕获 API，但 `search_official_site()` 返回 `None`，`_capture_api_requests()` 返回 `[]`。
4. `health_check.py` 仍走旧 `src.crawler`，并提示修改不存在的 `spider.py`。
5. `run_scheduled.bat` 调用不存在的根目录 `scheduler.py`。
6. `AGENTS.md` / `CLAUDE.md` 已一致，但 `.claude/skills/jobhunter/tools/crawl.md` 仍指向旧 `src.crawler.py`。
7. README/README_CN 暂不更新；等本计划确认并实现后统一更新。

## 1. 目标运行逻辑

### 1.1 用户配置阶段

用户可以在 `config/companies.yaml` 中配置公司和官网链接，最小配置只需要：

```yaml
companies:
  - id: example
    name: 示例公司
    enabled: true
    links:
      career_home: "https://example.com/careers"
      social: "https://example.com/jobs"
      campus: ""
      internship: ""
    strategy:
      status: unknown
      type: unknown
      owner: agent
      last_verified_at: null
      evidence_dir: null
```

### 1.2 每日巡检阶段

每日任务不应直接假设策略可用，而是先做策略巡检：

1. 读取所有启用公司及其 `links`。
2. 对每个链接做轻量预检：能否打开、是否跳转、是否登录/反爬、页面标题/关键 DOM 是否变化。
3. 如果公司没有固化策略，或链接新增/变化/失效，运行证据采集。
4. Agent 读取证据包，决定采用：
   - `config_intercept`：配置 API pattern + data_path + field_mappings。
   - `config_dom`：配置 DOM selectors。
   - `custom_python`：站点特殊，固化到 Python strategy。
   - `browser_operation`：只能通过浏览器交互抓取，生成可复用操作步骤。
   - `unsupported`：登录、验证码、强反爬或信息不足。
5. 将策略写入 `config/companies.yaml` 或 `src/site_strategies/*.py`。
6. 对该公司跑最小验证：抓到岗位数组，字段齐全，URL 可打开。
7. 进入岗位抓取、过滤、匹配、报告。

### 1.3 Agent 和 Python 的边界

- Python 不调用外部 LLM API。
- Python 可以采集证据、执行 Playwright、运行测试、保存策略。
- 当前 Claude/Codex Agent 负责分析证据和改代码/配置。
- 如果每日任务要无人值守地“让 AI 自动分析并改代码”，必须由 Claude/Codex 这类 agent 平台调度，而不是只靠 Windows `schtasks` 跑 Python。
- Python-only 定时任务只能做到：用已有策略抓取、发现异常、生成 evidence 和 repair task。

---

## 2. 文件结构设计

### 新增文件

- `src/company_registry.py`
  - 读取/校验 `config/companies.yaml` 中用户配置的链接和策略状态。
  - 兼容旧字段 `urls`，新字段使用 `links`。

- `src/site_inspector.py`
  - 对公司链接做轻量巡检。
  - 输出 link status、redirect、title、network availability、login/captcha signals、fingerprint。

- `src/strategy_planner.py`
  - 根据公司配置、链接巡检结果、已有 strategy 状态，决定是否需要 agent 分析。
  - 生成 `logs/strategy_tasks/<company>/<timestamp>/task.json`。

- `src/site_strategies/__init__.py`
  - custom Python strategy 包入口。

- `src/site_strategies/base.py`
  - 定义 custom strategy 接口，避免随意堆特殊代码。

- `tests/test_company_registry.py`
  - 覆盖新旧 config 字段兼容、最小公司链接配置。

- `tests/test_strategy_planner.py`
  - 覆盖新链接、失效链接、未知策略、已验证策略等场景。

- `tests/test_site_inspector.py`
  - 用离线 fixture 测试 login/captcha/empty/list 页面信号识别。

- `tests/test_health_workflow.py`
  - 锁定新每日巡检流程，不再走旧 `health_check.py`。

### 修改文件

- `config/companies.yaml`
  - 增加 `links` 和 `strategy` 字段，保留旧 `urls/api/field_mappings`。

- `config/crawler_schema.py`
  - 增加链接配置和策略状态 dataclass。

- `src/crawler_evidence.py`
  - 从“单次 evidence 工具”升级为“策略发现证据包生成器”。
  - 支持从 `company.links` 自动选择 URL。
  - 保存 page HTML、screenshot、network log、XHR JSON sample、DOM text sample、candidate arrays。

- `src/crawler_factory.py`
  - 默认使用 `strategy.type` 路由。
  - 移除假的自动修复路径；失败时生成 strategy task，不声称自动完成。

- `src/health_monitor.py`
  - 改名语义为“策略健康巡检 + evidence task 生成”。
  - 不再调用不存在或空壳的 auto analyzer 修复路径。

- `src/health_check.py`
  - 改为 legacy wrapper：调用 `health_monitor` 或新 daily inspector。

- `src/scheduler.py`
  - 调用新的 daily workflow。
  - 输出“需要 agent 分析的任务路径”，而不是提示改 `spider.py`。

- `.claude/skills/jobhunter/tools/crawl.md`
  - 改为 `src.crawler_factory` 和新 strategy workflow。

- `.claude/skills/jobhunter/run.md`
  - 加入每日任务中的“链接巡检 -> evidence -> agent 分析 -> 固化策略 -> 验证 -> 抓取”。

- `AGENTS.md` / `CLAUDE.md`
  - 继续保持完全一致。
  - 补充每日策略巡检命令和 agent 决策规则。

- `run_scheduled.bat`
  - 改成 `python -m src.scheduler --schedule`。

### 删除文件

- `EXPAND_PLAN.md`
  - 已过期的爬虫扩展计划，用户确认删除。

- `RUN.md`
  - 仍引用 `main.py`、`spider.py`、根目录 `scheduler.py`，用户确认删除。

### 暂不修改

- `README.md`
- `README_CN.md`

等用户确认本计划并完成代码重构后统一更新。

---

## 3. 任务拆分

### Task 1: 清理已确认删除文件

**Files:**
- Delete: `EXPAND_PLAN.md`
- Delete: `RUN.md`

- [ ] **Step 1: 确认删除状态**

Run:

```powershell
git status -sb
```

Expected:

```text
 D EXPAND_PLAN.md
 D RUN.md
```

- [ ] **Step 2: 运行文档无关测试**

Run:

```powershell
pytest -q -p no:cacheprovider -m "not integration"
```

Expected:

```text
34 passed, 3 deselected
```

- [ ] **Step 3: Commit**

```powershell
git add EXPAND_PLAN.md RUN.md
git commit -m "docs: remove obsolete run plans"
```

### Task 2: 定义公司链接与策略状态 schema

**Files:**
- Create: `src/company_registry.py`
- Modify: `config/crawler_schema.py`
- Test: `tests/test_company_registry.py`

- [ ] **Step 1: 写失败测试**

Test cases:

```python
def test_load_company_with_minimal_user_links():
    raw = {
        "id": "example",
        "name": "示例公司",
        "enabled": True,
        "links": {"career_home": "https://example.com/careers"},
    }
    company = normalize_company(raw)
    assert company["links"]["career_home"] == "https://example.com/careers"
    assert company["strategy"]["status"] == "unknown"


def test_old_urls_are_compatible_with_links():
    raw = {
        "id": "legacy",
        "name": "旧配置",
        "enabled": True,
        "urls": {"social": "https://legacy.example/jobs?keyword={keyword}"},
        "api": {"type": "intercept", "pattern": "jobs", "data_path": "data"},
        "field_mappings": {"title": {"source": "title"}},
    }
    company = normalize_company(raw)
    assert company["links"]["social"] == raw["urls"]["social"]
    assert company["strategy"]["type"] == "config_intercept"
```

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_company_registry.py
```

Expected: import/function missing.

- [ ] **Step 3: 实现 `company_registry.py`**

Responsibilities:

```python
def normalize_company(raw: dict) -> dict:
    """Return a company dict with links and strategy fields populated."""

def load_companies(config_path: str | Path = None, enabled_only: bool = True) -> list[dict]:
    """Load normalized companies from config/companies.yaml."""

def company_needs_strategy(company: dict) -> bool:
    """True when strategy is missing, unknown, failed, or stale."""
```

- [ ] **Step 4: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_company_registry.py
```

Expected: pass.

### Task 3: 增加每日链接巡检器

**Files:**
- Create: `src/site_inspector.py`
- Test: `tests/test_site_inspector.py`

- [ ] **Step 1: 写离线信号识别测试**

Test cases:

```python
def test_detect_login_required_from_html():
    result = inspect_html_signals("<html>请登录后查看职位</html>")
    assert "login_required" in result["signals"]


def test_detect_captcha_from_html():
    result = inspect_html_signals("<html>captcha 验证码</html>")
    assert "captcha" in result["signals"]


def test_fingerprint_changes_when_title_or_dom_changes():
    a = build_page_fingerprint("Jobs", "产品经理 北京")
    b = build_page_fingerprint("Careers", "暂无岗位")
    assert a != b
```

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_site_inspector.py
```

- [ ] **Step 3: 实现离线信号函数**

Functions:

```python
def inspect_html_signals(html: str, text: str = "") -> dict:
    """Detect login, captcha, no jobs, blocked, and job-like signals."""

def build_page_fingerprint(title: str, body_text: str, network_patterns: list[str] = None) -> str:
    """Stable fingerprint for daily change detection."""
```

- [ ] **Step 4: 增加 Playwright link inspector**

Function:

```python
def inspect_link(url: str, headless: bool = True, timeout_ms: int = 30000) -> dict:
    """Open a link, collect status/url/title/text snippet/signals/fingerprint."""
```

Implementation notes:

- Use Playwright.
- Capture final URL after redirects.
- Do not require login bypass.
- Do not write config.

- [ ] **Step 5: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_site_inspector.py
```

### Task 4: 升级 evidence 包生成

**Files:**
- Modify: `src/crawler_evidence.py`
- Test: `tests/test_crawler_evidence.py`

- [ ] **Step 1: 写 evidence manifest 测试**

Test cases:

```python
def test_evidence_manifest_contains_agent_inputs(tmp_path):
    manifest = build_evidence_manifest(
        company_id="example",
        company_name="示例公司",
        url="https://example.com/jobs",
        keyword="产品经理",
        job_type="social",
        output_dir=tmp_path,
        network_requests=[{"url": "https://api.example.com/jobs", "method": "GET"}],
        candidates=[{"path": "data.jobs", "count": 3}],
    )
    assert manifest["agent_next_step"] == "analyze_strategy"
    assert manifest["company"]["id"] == "example"
    assert manifest["artifacts"]["network_log"].endswith("network.json")
```

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_crawler_evidence.py
```

- [ ] **Step 3: 实现 manifest builder**

Expected evidence directory:

```text
logs/crawler_evidence/<company_id>/<YYYYMMDD_HHMMSS>/
  evidence.json
  network.json
  page.html
  page.txt
  page.png
  xhr_samples/
```

- [ ] **Step 4: 增加 company link mode**

Command:

```powershell
python -m src.crawler_evidence --company tencent --keyword "产品经理" --job-type social
```

Behavior:

- Reads company links from config.
- Chooses `links.social`, fallback `urls.social`, fallback `links.career_home`.
- Writes evidence manifest.
- Prints evidence path for agent.

- [ ] **Step 5: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_crawler_evidence.py
```

### Task 5: 策略任务规划器

**Files:**
- Create: `src/strategy_planner.py`
- Test: `tests/test_strategy_planner.py`

- [ ] **Step 1: 写策略决策测试**

Test cases:

```python
def test_unknown_strategy_requires_agent_analysis():
    company = {"id": "x", "strategy": {"status": "unknown"}}
    inspection = {"signals": [], "fingerprint": "abc"}
    decision = plan_strategy_action(company, inspection)
    assert decision["action"] == "collect_evidence"
    assert decision["requires_agent"] is True


def test_verified_unchanged_strategy_can_crawl():
    company = {
        "id": "x",
        "strategy": {"status": "verified", "fingerprint": "abc", "type": "config_intercept"},
    }
    inspection = {"signals": [], "fingerprint": "abc"}
    decision = plan_strategy_action(company, inspection)
    assert decision["action"] == "crawl"


def test_login_required_blocks_auto_strategy():
    company = {"id": "x", "strategy": {"status": "unknown"}}
    inspection = {"signals": ["login_required"], "fingerprint": "abc"}
    decision = plan_strategy_action(company, inspection)
    assert decision["action"] == "blocked"
```

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_strategy_planner.py
```

- [ ] **Step 3: 实现 planner**

Functions:

```python
def plan_strategy_action(company: dict, inspection: dict) -> dict:
    """Return crawl/collect_evidence/blocked/manual_review decision."""

def write_strategy_task(company: dict, decision: dict, evidence_dir: str | None = None) -> Path:
    """Write logs/strategy_tasks/<company>/<timestamp>/task.json."""
```

- [ ] **Step 4: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_strategy_planner.py
```

### Task 6: 重构健康巡检为“每日策略巡检”

**Files:**
- Modify: `src/health_monitor.py`
- Modify: `src/health_check.py`
- Test: `tests/test_health_workflow.py`

- [ ] **Step 1: 写新行为测试**

Expected behavior:

- `health_monitor` loads companies via `company_registry`.
- It inspects links before crawl.
- Unknown/new/changed strategies produce strategy tasks.
- It does not call `AutoAnalyzer.analyze_company()`.
- `health_check.py` is a wrapper and no longer imports `src.crawler`.

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_health_workflow.py
```

- [ ] **Step 3: Modify `health_monitor.py`**

New public methods:

```python
def inspect_company_strategy(company_id: str, keyword: str = "产品经理", job_type: str = "social") -> dict:
    """Run link inspection and strategy planning for one company."""

def inspect_all_strategies(keyword: str = "产品经理", job_type: str = "social") -> dict:
    """Run daily strategy inspection for all enabled companies."""
```

- [ ] **Step 4: Modify CLI for health monitor**

Commands:

```powershell
python -m src.health_monitor --inspect-strategies
python -m src.health_monitor --inspect-company tencent --keyword "产品经理" --job-type social
python -m src.health_monitor --check-all
```

`--check-all` remains for compatibility but should internally call the new strategy-aware path or clearly label old behavior.

- [ ] **Step 5: Modify `health_check.py`**

Make it a legacy wrapper:

```python
"""Legacy compatibility entrypoint. Prefer `python -m src.health_monitor`."""
```

Remove direct import:

```python
from src.crawler import crawl_company, get_enabled_companies
```

- [ ] **Step 6: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_health_workflow.py
pytest -q -p no:cacheprovider -m "not integration"
```

### Task 7: 策略路由与固化方式

**Files:**
- Create: `src/site_strategies/__init__.py`
- Create: `src/site_strategies/base.py`
- Modify: `src/crawler_factory.py`
- Test: `tests/test_config_crawler.py`

- [ ] **Step 1: 写 strategy routing 测试**

Test cases:

```python
def test_config_intercept_strategy_uses_config_crawler():
    company = {"strategy": {"type": "config_intercept"}, "api": {"type": "intercept"}}
    assert select_strategy_type(company) == "config"


def test_custom_python_strategy_requires_registered_strategy():
    company = {"id": "special", "strategy": {"type": "custom_python", "module": "special"}}
    assert select_strategy_type(company) == "custom_python"
```

- [ ] **Step 2: Run failing test**

```powershell
pytest -q -p no:cacheprovider tests/test_config_crawler.py
```

- [ ] **Step 3: Implement base custom strategy**

```python
class SiteStrategy:
    company_id: str

    def crawl(self, keyword: str, max_jobs: int, job_type: str, headless: bool = True) -> list[dict]:
        raise NotImplementedError
```

- [ ] **Step 4: Modify `crawler_factory.py`**

Rules:

- `strategy.type in [config_intercept, config_dom, legacy_config]` -> existing config crawler.
- `strategy.type == custom_python` -> load `src.site_strategies.<module>`.
- `strategy.type == browser_operation` -> fail with clear task requiring agent/browser execution unless implemented.
- `strategy.status in [unknown, failed]` -> do not pretend repaired; generate task.

- [ ] **Step 5: Run tests**

```powershell
pytest -q -p no:cacheprovider tests/test_config_crawler.py
```

### Task 8: Agent 工作流文档同步

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/skills/jobhunter/run.md`
- Modify: `.claude/skills/jobhunter/skill.md`
- Modify: `.claude/skills/jobhunter/tools/crawl.md`
- Create: `.claude/skills/jobhunter/prompts/analyze_crawler_strategy.md`

- [ ] **Step 1: Update `AGENTS.md` and copy to `CLAUDE.md`**

Add exact workflow:

```text
每日巡检顺序：
1. 读取 config/companies.yaml 中用户配置的 links。
2. 运行 python -m src.health_monitor --inspect-strategies。
3. 对 unknown/new/changed/failed 链接运行 crawler_evidence。
4. Agent 读取 evidence.json、network.json、page.html、page.png。
5. Agent 判断策略类型并修改 config 或 src/site_strategies。
6. 运行单公司抓取测试。
7. 通过后进入岗位抓取、过滤、匹配和报告。
```

- [ ] **Step 2: Add strategy prompt**

Prompt must require:

- Evidence path.
- Observed network requests.
- Candidate job arrays.
- DOM selectors.
- Recommended strategy type.
- Exact config or Python patch.
- Verification commands.
- `unsupported` reason if blocked.

- [ ] **Step 3: Update crawl tool docs**

Change implementation path from `src.crawler.py` to `src.crawler_factory.py`.

- [ ] **Step 4: Verify AGENTS/CLAUDE hash equality**

Run:

```powershell
$claude = Get-FileHash -Algorithm SHA256 CLAUDE.md
$agents = Get-FileHash -Algorithm SHA256 AGENTS.md
$claude.Hash -eq $agents.Hash
```

Expected:

```text
True
```

### Task 9: Scheduler and Windows task correction

**Files:**
- Modify: `src/scheduler.py`
- Modify: `run_scheduled.bat`
- Test: `tests/test_health_workflow.py`

- [ ] **Step 1: Modify scheduler daily order**

New order:

```text
1. inspect strategies
2. if strategy tasks require agent: print task paths and stop Python-only run
3. if all verified: run job hunt
4. push/report/update memory
```

- [ ] **Step 2: Remove fake repair wording**

Remove:

```text
更新spider.py
python health_check.py
```

Replace with:

```text
读取 logs/strategy_tasks/.../task.json
运行 python -m src.crawler_evidence ...
由当前 Agent 修改 config/companies.yaml 或 src/site_strategies
运行 python tests/test_all_crawlers.py --company <id> --keyword "<keyword>" --max-jobs 3
```

- [ ] **Step 3: Fix `run_scheduled.bat`**

Use:

```bat
python -m src.scheduler --schedule
```

- [ ] **Step 4: Run help checks**

```powershell
python -m src.scheduler --help
python -m src.health_monitor --help
```

### Task 10: Profile/config hygiene

**Files:**
- Modify: `profiles/pm_tob.md`
- Modify: `profiles/产品经理-TOB方向.md`
- Optional Modify: `profiles/AI产品经理.md`
- Test: `tests/test_profile_schema.py`

- [ ] **Step 1: Resolve duplicate enabled profile names**

Current issue:

- `profiles/pm_tob.md` enabled true, name `产品经理-TOB方向`, resume `resumes/pm_tob.md` missing.
- `profiles/产品经理-TOB方向.md` enabled true, same name, resume `resumes/pm_tob.txt` local ignored file exists.

Decision options:

1. Keep `profiles/产品经理-TOB方向.md` enabled and disable `profiles/pm_tob.md`.
2. Merge them into one profile and delete the duplicate.

- [ ] **Step 2: Make example profiles honest**

Disabled profiles may reference missing files, but enabled profiles must not.

- [ ] **Step 3: Run profile tests**

```powershell
pytest -q -p no:cacheprovider tests/test_profile_schema.py
python -m src.cli --list-profiles
```

Expected:

- No duplicate enabled names.
- Enabled profile resume exists or is clearly user-provided local file.

### Task 11: Live validation with 3 companies

**Files:**
- No code files unless fixes are discovered.

- [ ] **Step 1: Run non-integration suite**

```powershell
pytest -q -p no:cacheprovider -m "not integration"
```

- [ ] **Step 2: Run official-site integration tests**

```powershell
pytest -q -p no:cacheprovider tests/test_config_crawler.py -m integration
```

- [ ] **Step 3: Run three live company checks**

Use at least:

```powershell
python tests/test_all_crawlers.py --company tencent --keyword "AI产品经理" --max-jobs 3
python tests/test_all_crawlers.py --company bytedance_social --keyword "AI产品经理" --max-jobs 3
python tests/test_all_crawlers.py --company meituan --keyword "AI产品经理" --max-jobs 3
```

- [ ] **Step 4: Agent manual evaluation**

For each company sample:

- List titles found.
- Judge whether any job actually matches target profile.
- If no matching job exists, success means correctly rejecting bad roles, not forcing a recommendation.

### Task 12: README update after user confirmation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`

Only do this after user confirms implementation behavior.

Required doc corrections:

- Replace “自动自愈系统” with “每日策略巡检 + Agent 辅助策略固化”。
- Explain two modes:
  - Agent-run daily workflow: can analyze evidence and patch config/code.
  - Python-only scheduled workflow: can inspect/crawl/report and generate strategy tasks, but cannot perform AI analysis alone.
- Update company counts from live config.
- Remove stale references to `RUN.md`, `main.py`, `spider.py`, root `scheduler.py`.
- Explain `auto_analyzer.py` if kept as deprecated/compat wrapper.
- Document config `links` and `strategy`.

---

## 4. Acceptance Criteria

- 用户可以只配置公司官网链接，系统每日先巡检链接和策略状态。
- 新链接、链接变化、策略未知、策略失败都会生成 evidence + strategy task。
- Agent 有明确证据包和 prompt 来分析如何抓取，并能选择 YAML 配置、custom Python、浏览器操作或 unsupported。
- 已固化策略会被 `crawler_factory` 使用并可测试。
- `health_check.py`、`scheduler.py` 不再引用 `spider.py` 或旧根目录入口。
- `auto_analyzer.py` 不再作为假的“自动 API 分析”卖点。
- `AGENTS.md` 和 `CLAUDE.md` 保持完全一致。
- `README.md` / `README_CN.md` 等实现确认后再更新。
- 非集成测试通过。
- 至少 3 家官网真实验证通过，并由 Agent 人工评估样本岗位是否符合目标。

## 5. Open Decisions for User

1. Python-only Windows 定时任务遇到新链接/失效链接时，是停止并生成 strategy task，还是继续跳过该公司抓取其他公司？
2. 是否允许每日 agent 平台任务自动修改 `config/companies.yaml` 和 `src/site_strategies/*.py`，还是每次策略固化前都要用户确认？
3. `profiles/pm_tob.md` 和 `profiles/产品经理-TOB方向.md` 两个同名启用 profile，采用禁用一个还是合并删除一个？
4. `auto_analyzer.py` 是直接删除，还是保留为 deprecated wrapper 指向 `crawler_evidence + agent prompt`？
5. `src/crawler.py` 旧特化爬虫是保留 legacy，还是逐步迁移后删除？
