# Agent Eval Upgrade Implementation Plan

> **For Claude/Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after user approval.

**Goal:** 把当前 SmartJobHunter 的函数级离线回归评测，升级为更接近 Anthropic `Demystifying evals for AI agents` 所描述的 Agent eval：显式 grader、可回放 transcript、端到端 outcome、多 trial、regression/capability 分层，并能持续吸收真实失败样本。

**Architecture:** 保留当前 `src/evaluation.py` 作为轻量 eval harness，但拆出 grader 层和 transcript 记录层；新增 workflow/outcome case 类型，用临时目录跑最小业务闭环。评测集分为 regression 和 capability，当前 14 个 case 迁移为 regression 基线，后续真实失败进入 capability 或 regression。

**Tech Stack:** Python、PyYAML、pytest、现有 `JobHunter` / `matching` / `strategy_planner` / `site_inspector` 模块。

---

## 1. 背景

当前评估体系已经具备基础离线回归能力：

- 数据集：`evals/jobhunter_agent_eval.yaml`
- 执行入口：`python -m src.evaluation`
- 输出：`output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS}/agent_eval_results.json`
- 报告：`output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS}/agent_eval_report.md`

它能覆盖：

- 岗位意图过滤：`matching_intent`
- 简历与岗位匹配评分：`job_fit`
- 抓取策略动作：`strategy_action`
- URL 过滤：`url_filter`
- Top 3 投递包：`application_package`
- Agent 指令一致性：`instruction_alignment`

但从 Wiki 文章 `AI/实践/Demystifying-evals-for-AI-agents.md` 的标准看，当前体系更接近“函数级 regression tests”，还没有完整达到“把 Agent 当成会行动的软件系统来测试”的程度。

---

## 2. 当前差距对照

| 文章概念 | 当前实现 | 差距 | 优化目标 |
|:--|:--|:--|:--|
| Task | YAML case 有输入和 `expected` | 缺少 `goal`、`constraints`、`source`、`success_criteria` | 扩展 case schema |
| Trial | 每 case 跑一次 | 无稳定性统计 | 加 `--trials`、`pass@k`、`pass^k` |
| Grader | 内联在 `_run_*_case` 里 | 没有显式 grader；只有 code-based grader | 抽象 `graders` 模块 |
| Code grader | 已有 | 不可复用、不可组合 | 标准化 grader result |
| Model grader | 没有 | 不能评语义质量 | 先设计接口，默认关闭 |
| Human grader | 没有 | 缺少人工 gold set 校准 | 加人工标注字段和导出格式 |
| Transcript | 只有 `details.actual/checks` | 不能回放过程 | 每 case 写 `transcript.jsonl` |
| Outcome | 少量 case 生成文件 | 大部分只测函数输出 | 新增端到端 workflow outcome |
| Eval harness | `run_dataset()` | 只调函数，不记录 trial/transcript | 升级 runner |
| Agent harness | 当前基本没有 | 没真正让 Agent 执行任务 | 先补 workflow trace，后续再接 Agent 复核 |
| Eval suite | 单一 YAML | regression/capability 混在一起 | 拆分数据集目录 |
| 活数据 | 人工构造 14 case | 未吸收真实巡检失败 | 新增 case collector 草案 |

---

## 3. 设计原则

1. **先代码判分，再语义判分**
   能用 Python 确认的事实优先用 code-based grader，例如文件是否生成、链接是否被过滤、action 是否正确、分数是否在区间内。

2. **Outcome 优先，Transcript 用于诊断**
   分数主要看最终业务状态是否达成；transcript 记录过程，用于失败回放和定位问题。

3. **Regression 和 Capability 分开**
   Regression eval 用来防倒退，应该稳定通过；Capability eval 用来测能力边界，可以失败，但必须清楚归因。

4. **从真实失败中生长**
   手工样例只作为冷启动。后续真实巡检失败、飞书反馈、人工标注应该沉淀成新 eval cases。

5. **不一次性引入外部 LLM 依赖**
   Model grader 先定义 schema 和 rubric，默认 disabled，避免评估命令变慢、变贵、变不稳定。

---

## 4. 目标目录结构

```text
evals/
├── regression/
│   └── jobhunter_core.yaml
├── capability/
│   └── jobhunter_hard_cases.yaml
└── candidates/
    └── {YYYY-MM-DD}/candidate_cases.yaml

src/
├── evaluation.py
├── eval_graders.py
└── eval_transcript.py

docs/
├── evaluation-grader-rubrics.md
├── eval-case-feedback-loop.md
└── plans/
    └── 2026-05-11-agent-eval-upgrade-implementation.md
```

---

## 5. 任务拆解

### Task 1: 拆分评测集目录

**Files:**

- Create: `evals/regression/jobhunter_core.yaml`
- Create: `evals/capability/jobhunter_hard_cases.yaml`
- Modify: `src/evaluation.py`
- Modify: `tests/test_evaluation.py`

**Purpose:** 把当前单一评测集拆成 regression 和 capability，明确“防倒退”和“测上限”的不同用途。

**Steps:**

1. 将当前 `evals/jobhunter_agent_eval.yaml` 内容复制到 `evals/regression/jobhunter_core.yaml`。
2. 保留旧路径兼容，或将 `DEFAULT_DATASET` 指向新 regression 文件。
3. 新建 `evals/capability/jobhunter_hard_cases.yaml`。
4. capability 文件先放 2-3 个难例：
   - 标题含 AI，但职责是工程/研发。
   - 营销 AI 产品经理，需区分产品与运营增长。
   - 页面有普通登录按钮，但职位列表公开，不应误判为 `login_required`。
5. 更新测试，确认默认 regression 数据集仍 100% 通过。

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add evals src/evaluation.py tests/test_evaluation.py
git commit -m "refactor: split evaluation suites"
```

---

### Task 2: 定义显式 Grader 层

**Files:**

- Create: `src/eval_graders.py`
- Modify: `src/evaluation.py`
- Modify: `tests/test_evaluation.py`

**Purpose:** 当前 grader 隐藏在各个 `_run_*_case` 的 `checks` 字典里。需要抽成显式 grader，方便复用、报告、扩展 model/human grader。

**Target Result Shape:**

```python
{
    "name": "should_keep",
    "type": "code",
    "passed": True,
    "expected": True,
    "actual": True,
    "message": "",
}
```

**Steps:**

1. 新建 `src/eval_graders.py`。
2. 实现轻量 helper：

```python
def code_grader(name, passed, expected=None, actual=None, message=""):
    return {
        "name": name,
        "type": "code",
        "passed": bool(passed),
        "expected": expected,
        "actual": actual,
        "message": message,
    }
```

3. 把以下 case handler 的 `checks` 迁移为 grader result list：
   - `matching_intent`
   - `job_fit`
   - `strategy_action`
   - `url_filter`
   - `application_package`
   - `instruction_alignment`
4. `passed = all(grader["passed"] for grader in graders if not grader.get("skipped"))`。
5. JSON 报告里保留 `graders`。
6. Markdown 报告里失败 case 展示失败 grader 名称和 message。

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add src/eval_graders.py src/evaluation.py tests/test_evaluation.py
git commit -m "refactor: add explicit eval graders"
```

---

### Task 3: 增加 Transcript 记录

**Files:**

- Create: `src/eval_transcript.py`
- Modify: `src/evaluation.py`
- Modify: `tests/test_evaluation.py`

**Purpose:** 当前结果里只有 `actual` 和 `checks`，失败时不能回放 Agent/工具链是怎么走到这个结果的。需要为每个 case 记录可读的过程轨迹。

**Output:**

```text
output/evals/{YYYY-MM-DD}/{run_id}/transcripts/{case_id}.jsonl
```

**Event Examples:**

```json
{"event": "case_started", "case_id": "match_ai_solution_pm_should_keep", "type": "matching_intent"}
{"event": "function_called", "name": "match_job_intent", "input_summary": {"title": "AI解决方案产品经理"}}
{"event": "function_result", "name": "match_job_intent", "output_summary": {"should_keep": true, "match_score": 0.87}}
{"event": "grader_result", "name": "should_keep", "passed": true}
{"event": "case_finished", "passed": true}
```

**Steps:**

1. 新建 `TranscriptRecorder`。
2. 支持 `record(event, **payload)`。
3. `run_case()` 为每个 case 创建 recorder。
4. 每个 handler 至少记录：
   - 输入摘要
   - 调用目标
   - actual 摘要
   - grader 结果
   - 输出文件路径
   - 异常信息
5. JSON report 中每个 result 增加 `transcript_path`。
6. Markdown report 中失败 case 显示 transcript 路径。

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
Get-ChildItem output\evals -Recurse -Filter *.jsonl | Select-Object -First 5
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add src/eval_transcript.py src/evaluation.py tests/test_evaluation.py
git commit -m "feat: record evaluation transcripts"
```

---

### Task 4: 增加多 Trial 与稳定性指标

**Files:**

- Modify: `src/evaluation.py`
- Modify: `tests/test_evaluation.py`

**Purpose:** 文章强调 Agent 有随机性，同一个 task 不能只跑一次。即使当前多数逻辑是确定性 Python，也需要把 trial 概念提前设计好，为后续 Agent/LLM grader 做准备。

**CLI:**

```powershell
python -m src.evaluation --trials 5
```

**Metrics:**

```json
{
  "trial_count": 5,
  "pass_at_k": 1.0,
  "pass_all_k": 1.0
}
```

**Definitions:**

- `pass@k`：同一个 case 跑 k 次，只要一次成功就算成功。
- `pass^k` / `pass_all_k`：同一个 case 跑 k 次，每次都成功才算成功。

**Decision:** SmartJobHunter 是日常求职巡检工具，比起“偶尔成功”，更需要稳定可靠，所以默认最终通过率应按 `pass_all_k` 统计。

**Steps:**

1. `run_dataset()` 增加 `trials=1` 参数。
2. `run_case()` 或上层 runner 循环运行 N 次。
3. 每个 result 保存 `trials` 明细。
4. case 顶层 result 保存：
   - `passed`
   - `pass_at_k`
   - `pass_all_k`
   - `trial_count`
5. metrics 增加全局 `pass_at_k` 和 `pass_all_k`。
6. CLI 增加 `--trials`。
7. 测试 `--trials 3` 的结构和指标。

**Verification:**

```powershell
python -m src.evaluation --trials 3 --fail-under 1.0
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add src/evaluation.py tests/test_evaluation.py
git commit -m "feat: add multi-trial evaluation metrics"
```

---

### Task 5: 增加端到端 Outcome Case

**Files:**

- Modify: `src/evaluation.py`
- Modify: `evals/regression/jobhunter_core.yaml`
- Modify: `tests/test_evaluation.py`

**New Case Type:** `workflow_outcome`

**Purpose:** 当前大多数 case 测的是函数输出，不是完整业务状态。需要增加最小端到端 outcome case，验证“报告和投递包真的生成、无效链接真的被排除、memory 真的更新”。

**Success Criteria:**

- 报告 Markdown 生成。
- Top 3 application packages 生成。
- 无效链接不进入报告。
- `jobs` 与 `evaluations` 过滤后仍对齐。
- 临时 `memory/seen_jobs.md` 被更新。
- 输出路径符合 `output/{YYYY-MM-DD}/`。

**Implementation Notes:**

- 使用 `TemporaryDirectory()` 隔离 output/memory。
- 不访问真实网络。
- 通过 fixture jobs/evaluations 和 mock URL availability 运行最小业务闭环。
- 优先复用 `JobHunter` 已有方法。

**Example YAML:**

```yaml
- id: workflow_should_generate_report_package_and_memory
  type: workflow_outcome
  attribution: output_quality
  profile:
    name: "AI产品经理"
    _profile_id: "eval_ai_pm"
    _resume_content: "5年 ToB SaaS 产品经验，主导 AI 助手从0到1上线。"
  jobs:
    - title: "AI产品经理"
      company: "A公司"
      url: "https://example.com/a"
      mock_available: true
    - title: "失效岗位"
      company: "B公司"
      url: "https://example.com/404"
      mock_available: false
  evaluations:
    - score: 95
      recommendation: "strong_apply"
    - score: 88
      recommendation: "apply"
  expected:
    report_exists: true
    package_top_n: 1
    excluded_titles: ["失效岗位"]
    memory_contains: ["AI产品经理"]
```

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add src/evaluation.py evals/regression/jobhunter_core.yaml tests/test_evaluation.py
git commit -m "feat: add workflow outcome evaluation"
```

---

### Task 6: 预留 Model/Human Grader Schema

**Files:**

- Modify: `evals/regression/jobhunter_core.yaml`
- Modify: `src/eval_graders.py`
- Create: `docs/evaluation-grader-rubrics.md`

**Purpose:** 当前只能做 code-based grader。Cover Letter 质量、推荐理由可信度、JD 与简历证据是否真的闭环，这类语义质量后续需要 model/human grader。但第一版不应默认调用外部 LLM。

**Schema Example:**

```yaml
graders:
  - type: code
    name: cover_letter_contains_evidence
  - type: model
    name: cover_letter_quality
    enabled: false
    rubric: cover_letter_quality_v1
  - type: human
    name: final_recommendation_review
    required_for: high_risk
```

**Model Grader Rubric Draft:**

`cover_letter_quality_v1`:

1. 事实准确性：不得编造公司、岗位、项目经历。
2. JD 贴合度：必须引用岗位职责或要求中的具体点。
3. 简历证据：必须对应候选人简历中的真实经历。
4. 非模板化：不能只有通用表达。
5. 风险提示：如有明显技能缺口，不应强行包装成强匹配。

**Steps:**

1. 在 `src/eval_graders.py` 中支持 `skipped` grader result。
2. 遇到 `enabled: false` 的 model grader，记录 skipped，不影响通过率。
3. 遇到 human grader，记录 `requires_human_review`。
4. 报告增加 skipped grader 统计。
5. 写 `docs/evaluation-grader-rubrics.md`。

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add src/eval_graders.py evals/regression/jobhunter_core.yaml docs/evaluation-grader-rubrics.md
git commit -m "docs: define model and human grader schema"
```

---

### Task 7: 真实失败样本回流设计

**Files:**

- Create: `docs/eval-case-feedback-loop.md`
- Optional later create: `scripts/collect_eval_candidates.py`

**Purpose:** 让 eval suite 从真实业务失败中生长，而不是长期依赖人工构造样例。

**Candidate Sources:**

- `logs/strategy_tasks/`
- `logs/crawler_evidence/`
- `output/{YYYY-MM-DD}/`
- 飞书“链接无效 / 不合适 / 已投递 / 推荐错了”反馈
- 人工复核标注

**Candidate Output:**

```text
evals/candidates/{YYYY-MM-DD}/candidate_cases.yaml
```

**Candidate Fields:**

```yaml
- id: candidate_20260511_001
  source: logs/strategy_tasks/...
  raw_evidence_path: logs/crawler_evidence/...
  suggested_type: matching_intent
  suggested_suite: capability
  severity: high
  human_label: null
  reason: "标题含 AI，但实际是研发岗位，污染产品经理报告"
```

**Promotion Rules:**

- 真实 bug 修复后，必须沉淀到 regression。
- 能力边界和探索样本先进入 capability。
- 未经人工确认的候选样本不能直接进入 regression。
- 过时或歧义 case 要定期删除或修正。

**Verification:**

文档 review 即可；如果后续实现 collector，再补 pytest。

**Commit:**

```powershell
git add docs/eval-case-feedback-loop.md
git commit -m "docs: design eval feedback loop"
```

---

### Task 8: 文档同步

**Files:**

- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/skills/jobhunter/skill.md`
- Modify: `README.md`
- Modify: `README_CN.md`

**Purpose:** 项目要求 `AGENTS.md`、`CLAUDE.md`、`.claude/skills/jobhunter/skill.md` 表达同一套流程。评估体系变化后必须同步，避免不同 Agent 读到不同指令。

**Docs Must Mention:**

```powershell
python -m src.evaluation
python -m src.evaluation --trials 3
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

**Docs Must Explain:**

- regression vs capability
- grader 类型：code/model/human
- transcript 输出路径
- outcome case 的作用
- 真实失败样本如何回流

**Verification:**

```powershell
python -m src.evaluation --fail-under 1.0
python -m pytest tests/test_evaluation.py -v
```

**Commit:**

```powershell
git add AGENTS.md CLAUDE.md .claude/skills/jobhunter/skill.md README.md README_CN.md
git commit -m "docs: update evaluation workflow"
```

---

## 6. Final Verification

实施完成后运行：

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
python -m pytest tests/test_evaluation.py -v
python -m src.evaluation
git status -sb
```

Expected:

- Regression suite 通过率 100%。
- `--trials 3` 输出 `pass@k` 和 `pass^k` / `pass_all_k`。
- 每个 case 有 transcript 文件。
- Markdown 报告显示 grader breakdown。
- Capability suite 可以不满分，但报告要清楚显示失败归因。
- 没有误提交 `output/evals/` 运行产物。

---

## 7. Recommended Implementation Phases

### Phase 1: Harness Upgrade

必做：

1. 拆分 regression/capability suite。
2. 显式 grader。
3. transcript。
4. multi-trial。
5. workflow outcome。

Phase 1 完成后，当前体系会从“函数级回归测试”升级为“可回放、可稳定性度量、能看 outcome 的 eval harness”。

### Phase 2: Long-Term Quality System

增强：

1. model/human grader schema。
2. 真实失败样本回流。
3. 文档全量同步。

Phase 2 完成后，评估体系会更接近 Wiki 文章中说的长期 Agent 质量系统：真实任务、真实结果、可追踪过程、稳定性、持续回归。

---

## 8. Open Questions Before Implementation

1. `evals/jobhunter_agent_eval.yaml` 是否保留为兼容入口，还是直接迁移后删除？
2. Capability suite 的失败是否允许 CI 返回 0，只作为诊断报告？
3. Model grader 是否只预留 schema，还是接入本地/当前 Agent 人工执行的半自动评审？
4. 真实失败样本回流第一版是否只写文档，还是同步实现 `scripts/collect_eval_candidates.py`？

