# Agent-Led Review Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SmartJobHunter's final recommendation workflow Agent-led instead of Python-fallback-led, and document the scoring boundary clearly.

**Architecture:** Python remains the deterministic tool layer for crawling, cleaning, deduplication, URL checks, output persistence, and eval aggregation. Python generates an Agent review queue and validates Agent review results; final semantic scores and recommendation decisions come from Agent-authored review results. Reports and evals must surface when a formal recommendation lacks Agent judgment.

**Tech Stack:** Python, pytest, Markdown Agent/Skill docs, YAML eval datasets.

---

### Task 1: Define Agent Review Schema And Queue Helpers

**Files:**
- Create: `src/agent_review.py`
- Test: `tests/test_agent_review.py`

- [ ] **Step 1: Write failing tests**
  - Validate that queue records include job facts, Python mechanical facts, fallback hints, and scoring instructions.
  - Validate that Agent results normalize to report evaluation schema.
  - Validate that missing Agent review keeps candidates in `needs_agent_review` state.

- [ ] **Step 2: Run red tests**
  - Run: `python -m pytest tests/test_agent_review.py -v`
  - Expected: fail because `src.agent_review` does not exist.

- [ ] **Step 3: Implement minimal helper module**
  - Add constants for Agent-owned scores: `role_fit`, `core_responsibility_fit`, `domain_fit`, `resume_evidence_fit`, `seniority_fit`, `risk_level`, `apply_priority`, `agent_score`, `agent_decision`.
  - Add Python-owned fact fields: URL validity, publish time status, duplicate state, JD completeness, crawl evidence quality.
  - Add queue writer and result loader/validator.

- [ ] **Step 4: Run green tests**
  - Run: `python -m pytest tests/test_agent_review.py -v`
  - Expected: pass.

### Task 2: Make CLI Generate Agent Review Queue And Require Agent Results For Formal Recommendations

**Files:**
- Modify: `src/cli.py`
- Modify: `src/run_records.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_run_records.py`

- [ ] **Step 1: Write failing tests**
  - `run_profile()` writes `agent_review_queue.json` after Python fallback ranking.
  - Without Agent review results, ranked jobs become `needs_agent_review` and do not enter the formal recommended list when `agent_review.required_for_recommendation=true`.
  - With Agent review results, report jobs use `source=agent`, Agent score, Agent decision, and Agent scoring breakdown.

- [ ] **Step 2: Run red tests**
  - Run: `python -m pytest tests/test_agent_review.py tests/test_run_records.py tests/test_cli.py -v`
  - Expected: new CLI tests fail.

- [ ] **Step 3: Implement CLI integration**
  - Add config section `agent_review`.
  - After fallback ranking, write review queue to `output/{date}/agent_review_queues/<profile>_<run_id>.json`.
  - Load review results from configured path or default sibling path when present.
  - If Agent results are missing and formal Agent review is required, report zero formal recommendations but keep the audit trail and queue path.
  - If Agent results exist, merge them into `run_records` with `source=agent`, rank by Agent score, then URL validate.

- [ ] **Step 4: Run green tests**
  - Run: `python -m pytest tests/test_agent_review.py tests/test_run_records.py tests/test_cli.py -v`
  - Expected: pass.

### Task 3: Gate Reports And Real-Run Eval On Agent-Led Recommendations

**Files:**
- Modify: `src/reporting.py`
- Modify: `src/eval_real_runs.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_eval_real_runs.py`

- [ ] **Step 1: Write failing tests**
  - Reports include Agent review queue path and warn when no formal Agent review was applied.
  - Real-run eval surfaces formal recommended records with `judgment_source=python_fallback` as an output/process badcase.

- [ ] **Step 2: Run red tests**
  - Run: `python -m pytest tests/test_reporting.py tests/test_eval_real_runs.py -v`
  - Expected: new assertions fail.

- [ ] **Step 3: Implement report/eval gates**
  - Add report metadata for queue/results paths.
  - Add real-run metric/badcase for fallback recommendations in formal recommendation section.

- [ ] **Step 4: Run green tests**
  - Run: `python -m pytest tests/test_reporting.py tests/test_eval_real_runs.py -v`
  - Expected: pass.

### Task 4: Strengthen Agent/Skill/Prompt Scoring Instructions

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `.claude/skills/jobhunter/skill.md`
- Modify: `.claude/skills/jobhunter/prompts/semantic_filter.md`
- Modify: `.claude/skills/jobhunter/prompts/match_candidate_job.md`
- Modify: `docs/smartjobhunter-agent-design.md`
- Modify: `docs/smartjobhunter-evaluation-design.md`
- Modify: `config/agent.sample.yaml`

- [ ] **Step 1: Update docs and prompts**
  - State that Python produces candidates and mechanical checks only.
  - State that Agent owns semantic scoring and final recommendation.
  - Include the Agent scoring rubric and JSON schema.
  - Include explicit non-product-role examples: AI product PR/communications, AI product frontend engineer, AI Agent backend engineer.

- [ ] **Step 2: Run instruction alignment eval**
  - Run: `python -m src.evaluation --fail-under 1.0`
  - Expected: pass.

### Task 5: Add Regression Cases For 135/141

**Files:**
- Modify: `evals/regression/jobhunter_core.yaml`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Add regression cases**
  - `AI产品公关传播经理` should not be `strong_apply`/`apply`.
  - `AI产品前端工程师` should not be `strong_apply`/`apply`.

- [ ] **Step 2: Run eval tests**
  - Run: `python -m pytest tests/test_evaluation.py -v`
  - Expected: pass.

### Task 6: Enrich Badcase Root Cause Analysis

**Files:**
- Modify: `src/eval_real_runs.py`
- Modify: `output/evals/real_runs/2026-07-09/胡睿琪-AI产品经理-26_6_18_20260709_2129_213254/bad_cases.md`
- Test: `tests/test_eval_real_runs.py`

- [ ] **Step 1: Write failing test**
  - Badcase markdown includes a flow-level root cause when a recommended record is `python_fallback`.

- [ ] **Step 2: Implement renderer additions**
  - Add explanation that Python fallback overreached into semantic scoring.
  - Add exact module/prompt fixes.

- [ ] **Step 3: Sync Feishu badcase document**
  - Run: `python -m src.eval_lark_sync sync-badcases --badcases "<latest bad_cases.md>"`

### Task 7: Full Verification

- [ ] Run targeted tests:
  - `python -m pytest tests/test_agent_review.py tests/test_run_records.py tests/test_cli.py tests/test_reporting.py tests/test_eval_real_runs.py tests/test_evaluation.py -v`
- [ ] Run project eval:
  - `python -m src.evaluation --fail-under 1.0`
- [ ] Inspect `git diff`.
- [ ] Commit local branch for user review.
