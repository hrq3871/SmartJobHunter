# Eval Case Feedback Loop

> **文档用途**
> 本文档用于说明如何把真实巡检失败、策略任务、用户反馈和人工复核沉淀成新的 eval case。
> 主要读者是负责扩充 regression/capability 评测集、维护 bad case 闭环的开发者和 Agent。
> 不用于定义 grader 判分细则，也不用于替代每日巡检报告或一次性运行记录。

SmartJobHunter evals should grow from real daily runs, not only from hand-written
examples. This document defines how runtime failures and user feedback become
candidate eval cases, then stable regression coverage.

## Feedback Sources

```mermaid
flowchart LR
    A["Daily run output"] --> E["Candidate eval cases"]
    B["Strategy tasks"] --> E
    C["Crawler evidence"] --> E
    D["Feishu feedback"] --> E
    H["Human review"] --> F["Regression or capability suite"]
    E --> H
```

Primary sources:

- `logs/strategy_tasks/`: strategy changes, blocked companies, fingerprint drift.
- `logs/crawler_evidence/`: page snapshots, API candidates, field samples.
- `output/{YYYY-MM-DD}/`: reports, application packages, unexpected empty runs.
- `output/evals/real_runs/{YYYY-MM-DD}/`: real-run evaluation reports, `human_labels.yaml`, and `bad_cases.md`.
- Feishu feedback: annotation table labels, invalid link, not a fit, already applied, recommendation wrong.
- Human review: explicit labels for whether a role should be recommended.

## Candidate Case Format

Candidate cases should be written to:

```text
evals/candidates/{YYYY-MM-DD}/candidate_cases.yaml
```

Example:

```yaml
- id: candidate_20260511_001
  source: logs/strategy_tasks/example/task.json
  raw_evidence_path: logs/crawler_evidence/example/
  suggested_type: matching_intent
  suggested_suite: capability
  severity: high
  human_label: null
  reason: "Title contains AI, but the job is actually an engineering role."
```

真实巡检评估的 `human_labels.yaml`、飞书标注表和 `bad_cases.md` 可以直接作为 candidate 来源。只把人工标为 `should_apply` / `maybe` 但系统未推荐、或人工标为 `should_reject` 但系统推荐的样本沉淀为语义 bad case；客观 URL / 文件落盘问题归入 `output_quality`。人工维度分用于归因：岗位方向低偏 `matching_filtering`，技能匹配低偏 `recommendation_quality`，JD 质量低偏证据不足，风险等级高偏风险惩罚。

## Promotion Rules

| Destination | Use When | Expected Pass Rate |
|:--|:--|:--|
| `evals/regression/jobhunter_core.yaml` | A real bug is fixed and must never regress | Should stay near 100% |
| `evals/capability/jobhunter_hard_cases.yaml` | The case probes a hard boundary or known weakness | Diagnostic, not a release blocker |
| `evals/candidates/...` | Evidence exists but the desired label is not confirmed | Not executed as a gate |

## Review Checklist

Before promoting a candidate:

- The input contains enough evidence to judge the expected behavior.
- The expected result is unambiguous to a domain reviewer.
- The case includes a clear `attribution`.
- The case uses a stable grader, preferably code-based.
- Any model/human grader is marked as skipped unless a calibrated judge exists.

## Attribution Map

| Attribution | Failure Means |
|:--|:--|
| `crawler_strategy` | The system chose the wrong crawl/evidence/block action. |
| `matching_filtering` | The system kept a bad job or dropped a good job. |
| `recommendation_quality` | Score, recommendation, risk, or evidence is wrong. |
| `output_quality` | Report, URL validation, package, or memory output is wrong. |
| `instruction_drift` | Agent-facing documents no longer describe the same workflow. |

## Minimum Maintenance Rhythm

- After every user-visible bug fix: add or promote one regression case.
- Weekly during active use: review candidate cases and delete duplicates.
- Monthly: review capability failures and decide which ones deserve product work.
- Before major prompt/tool/model changes: run regression with `--trials 3`.
