# Evaluation Grader Rubrics

> **文档用途**
> 本文档用于说明 SmartJobHunter 评估体系中 grader 的判分规则、适用边界和输出结构。
> 主要读者是维护 eval case、调整评估 harness、排查评估失败的开发者和 Agent。
> 不用于描述日常巡检流程，也不用于替代 `docs/smartjobhunter-agent-design.md` 的整体架构说明。

SmartJobHunter uses graders to turn an eval case into a reproducible pass/fail
decision. The offline runner is deterministic by default: code graders are active,
while model and human graders are represented in the schema but skipped unless a
future workflow explicitly enables them.

## Grader Types

| Type | Status | Best For | Notes |
|:--|:--|:--|:--|
| `code` | Active | Objective facts: files, URLs, action names, score ranges, counts, required/forbidden text | Fast, cheap, repeatable. Use this whenever possible. |
| `model` | Schema only | Semantic quality: cover letter fit, recommendation explanation, evidence quality | Must use a rubric and should be calibrated by human review before gating releases. |
| `human` | Schema only | High-risk or ambiguous samples, final gold-set labels | Used to define and audit standards, not for every run. |

## Code Grader Contract

Each code grader result has this shape:

```json
{
  "name": "should_keep",
  "type": "code",
  "passed": true,
  "expected": true,
  "actual": true,
  "message": "",
  "skipped": false
}
```

The eval case passes only when all non-skipped graders pass.

## Model Grader Schema

Model graders can be declared in YAML but are skipped in the current offline
runner:

```yaml
graders:
  - type: model
    name: cover_letter_quality
    enabled: false
    rubric: cover_letter_quality_v1
```

### `cover_letter_quality_v1`

Use this rubric when evaluating generated cover letters:

1. **Factual accuracy**: The letter must not invent companies, roles, tools,
   dates, metrics, or candidate experiences.
2. **JD alignment**: The letter must reference concrete duties or requirements
   from the target job description.
3. **Resume evidence**: Claims must map to evidence in the resume or profile.
4. **Specificity**: The letter should not read like a generic template that could
   apply to any company or role.
5. **Risk honesty**: If a major skill or domain gap exists, the letter should not
   disguise it as a strong match.

Suggested output shape for a future model grader:

```json
{
  "score": 4,
  "max_score": 5,
  "passed": true,
  "reasons": ["Uses JD evidence", "Uses resume evidence"],
  "uncertain": false
}
```

## Human Grader Schema

Human graders mark samples that need manual judgment:

```yaml
graders:
  - type: human
    name: final_recommendation_review
    required_for: high_risk
```

Human labels should use a small, stable set:

| Label | Meaning |
|:--|:--|
| `should_apply` | Strong enough to recommend applying. |
| `maybe` | Worth manual review or depends on user preference. |
| `should_reject` | Should not enter the main recommendation report. |
| `invalid_link` | Job link is missing, expired, or unusable. |
| `unclear` | The evidence is insufficient or ambiguous. |

## When To Promote A Case To Regression

Promote a case to `evals/regression/jobhunter_core.yaml` when:

- It came from a real bug or user-visible failure.
- The desired behavior is now clear.
- A fix has been implemented.
- The case should never regress.

Keep exploratory, ambiguous, or capability-boundary cases in
`evals/capability/jobhunter_hard_cases.yaml`.
