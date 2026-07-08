# SmartJobHunter Evaluation Design

> 本文档定义 SmartJobHunter 的评估体系。README 只保留简要说明；Agent 自动加载规则仍以 `CLAUDE.md` / `AGENTS.md` 为准。

## 目标

SmartJobHunter 的 eval 分两层：

1. **跑前回归**：使用固定 YAML 假数据，防止抓取策略、匹配过滤、报告输出和 Agent 指令退化。
2. **跑后实测**：使用真实巡检报告和人工标注，衡量真实推荐质量、误杀、链接质量和产出完整性。

两层使用同一套质量维度，但数据来源不同。回归评估用于开发门禁；实测评估用于产品质量复盘和简历项目指标。

## 维度

| 维度 | 回归数据 | 实测数据 | 主要 Grader |
|:--|:--|:--|:--|
| 语义过滤 | `matching_intent` cases | 全量审计记录中被过滤/保留的岗位 | code + human |
| 岗位匹配 | `job_fit` cases | 推荐岗位、候选高分岗位 | code + human |
| 策略路由 | `strategy_action` cases | 策略任务、阻断公司、修复验证结果 | code |
| 链接校验 | `url_filter` cases | 报告中原始 URL、URL 拒绝记录 | code |
| 产出完整性 | `workflow_outcome` cases | 报告、投递包、memory、审计附录 | code |
| 文档一致性 | `instruction_alignment` case | Agent 文档、README、Skillmap | code |

## 当前回归评估

命令：

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

输出：

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/
├── agent_eval_results.json
├── agent_eval_report.md
├── transcripts/<case_id>.jsonl
├── artifacts/
└── wf/
```

回归 eval 的 `code` grader 默认启用；`model` 和 `human` grader 目前只作为 schema，不作为离线门禁。

## 真实巡检评估

真实巡检评估不重新抓取网页，只读取已经生成的巡检报告。报告必须包含：

- 推荐岗位区。
- `全量抓取与判断记录`。
- 每条记录的原始 URL、处理状态、判断来源、最终结论、总分与评分拆解。

命令：

```powershell
# 第一次：解析真实报告并生成待人工标注文件
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<report>.md"

# 标注后：读取人工标注并生成完整指标报告
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<report>.md" --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml"
```

输出：

```text
output/evals/real_runs/{YYYY-MM-DD}/{report_stem}_{HHMMSS}/
├── real_run_samples.json
├── human_labels.yaml
├── real_run_eval_results.json
└── real_run_eval_report.md
```

## 自动判定项

这些项由代码自动判断，不需要人工标注：

| 项 | 自动规则 |
|:--|:--|
| URL 是否格式有效 | 空 URL、非 HTTP(S)、包含 `...` / `…` 判为无效 |
| URL 是否被报告过滤 | `处理状态` 包含 `url_rejected` |
| 是否进入推荐区 | `处理状态` 为 `recommended` |
| 是否被过滤 | `处理状态` 以 `filtered_out` 开头 |
| 报告是否存在 | 文件存在且可读 |
| 全量审计是否存在 | 包含 `## 全量抓取与判断记录` |
| 投递包是否存在 | 同日期 `application_packages/<report_stem>/` 或相近目录存在 |
| 是否需要人工复核 | 推荐岗位、高分但未推荐岗位、最终结论为 `apply` / `strong_apply` 但未进入推荐区 |

## 人工只标什么

人工只标语义质量，不标客观事实。也就是说，不需要人工判断“文件是否存在”“URL 是否为空”“有没有投递包”。

人工标注文件只需要改 `human_label` 和必要时补 `review_notes`：

```yaml
labels:
  - record_id: "001"
    company: "美团"
    title: "支付平台AI智能产品经理"
    system_decision: "recommended"
    final_decision: "apply"
    score: 82
    review_reason: "recommended"
    human_label: null
    severity: medium
    review_notes: ""
```

标签集合固定为：

| 标签 | 含义 | 计入方式 |
|:--|:--|:--|
| `should_apply` | 明确值得投，推荐成立 | 正例 |
| `maybe` | 可以考虑，但需要用户偏好或简历策略确认 | 弱正例 |
| `should_reject` | 不应进入推荐区 | 负例 |
| `invalid_link` | 链接不可用；一般由代码自动判断，人工只在页面实际打不开时补 | 链接失败 |
| `unclear` | JD 信息不足或证据不够 | 不计入精确率/召回率，单独统计 |

建议标注顺序：

1. 先标所有 `review_reason: recommended` 的岗位，用来算推荐精确率。
2. 再标 `review_reason: high_confidence_filtered` 的岗位，用来发现被报告数量上限或阈值误杀的好岗位。
3. 最后抽查 `review_reason: spot_check_filtered`，用于发现低分过滤里的系统性漏判。

默认工具不会让人工标所有岗位；低分、最终结论为 `skip`、URL 客观无效的记录由自动指标处理或留作抽查。

## 指标定义

| 指标 | 公式 | 含义 |
|:--|:--|:--|
| `label_completion_rate` | 已填人工标签 / 需人工标签 | 标注完成度 |
| `recommendation_precision` | 推荐且正例或弱正例 / 已标推荐岗位 | 推荐区质量 |
| `strict_recommendation_precision` | 推荐且 `should_apply` / 已标推荐岗位 | 严格推荐质量 |
| `reviewed_recall` | 已推荐正例 / 已标正例 | 在人工复核范围内的召回 |
| `reviewed_false_negative_rate` | 未推荐正例 / 已标正例 | 人工复核范围内的误杀率 |
| `invalid_url_rate` | 自动无效链接 / 全量记录 | 链接质量 |
| `recommended_invalid_url_rate` | 推荐区无效链接 / 推荐记录 | 推荐区链接质量 |
| `maybe_rate` | `maybe` / 已标记录 | 需要用户判断的模糊比例 |
| `unclear_rate` | `unclear` / 已标记录 | 证据不足比例 |
| `recommendation_volume` | 推荐记录数 / 全量记录数 | 推荐收敛度 |

当人工标注未完成时，报告会显示 partial metrics，并把缺失标签列出来。只有 `label_completion_rate = 100%` 时，才把人工相关指标视为完整实测指标。

## Bad Case 处理

实测评估发现 bad case 后按三步处理：

1. **候选沉淀**：写入 `evals/candidates/{YYYY-MM-DD}/candidate_cases.yaml`，保留报告路径、record_id、人工标签、系统判断和原因。
2. **归因**：归到 `matching_filtering`、`recommendation_quality`、`crawler_strategy`、`output_quality` 或 `instruction_drift`。
3. **提升为回归**：修复后，把明确、稳定、不可再退化的 case 提升到 `evals/regression/jobhunter_core.yaml`；边界样本放入 `evals/capability/jobhunter_hard_cases.yaml`。

## 社招实测操作方案

后续要跑真实数据时，建议使用社招，因为岗位量更大：

```powershell
# 1. 用 Web 控制台或 CLI 跑社招巡检
python -m src.cli -t social -p "<profile_id_or_name>"

# 2. 对生成的报告创建标注文件
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<profile_id>_<YYYYMMDD_HHMM>.md"

# 3. 只编辑 human_labels.yaml 里 human_label: null 的样本
#    不要改 real_run_samples.json；那是机器解析产物。

# 4. 重新计算完整实测指标
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<profile_id>_<YYYYMMDD_HHMM>.md" --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml"
```

如果只想先少量标注，可以先标推荐区和高分未推荐区。报告会明确显示标注覆盖率，避免把部分指标误当成完整指标。

## 可写进简历的指标来源

可直接来自回归 eval：

- 回归 case 数、通过率、pass@k、pass^k。
- 策略路由、匹配过滤、输出质量、文档一致性的分组通过率。

需要真实标注后再写：

- 推荐精确率。
- 严格推荐精确率。
- 人工复核召回率。
- 误杀率。
- 无效链接率。
- 平均每次巡检覆盖岗位数和推荐收敛率。

## 维护规则

- 修改 eval harness、grader、数据集、报告解析或标注格式后，必须运行：

```powershell
python -m pytest tests/test_evaluation.py tests/test_eval_real_runs.py -v
python -m src.evaluation --fail-under 1.0
```

- 如果修改 Agent 定义、Skillmap 或状态机描述，还必须同步 `CLAUDE.md`、`AGENTS.md`、`.claude/skills/jobhunter/skill.md` 和 `docs/smartjobhunter-agent-design.md`。
