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

# 可选：初始化飞书标注表和 badcase 文档
python -m src.eval_lark_sync setup

# 可选：把待标注样本同步到飞书标注表
python -m src.eval_lark_sync export-labels --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml" --run-id "<run_id>"

# 可选：标完后从飞书拉回标签、重算指标，并同步 badcase 文档
python -m src.eval_lark_sync score-from-lark --report "output/YYYY-MM-DD/<report>.md" --run-id "<run_id>" --sync-badcases
```

输出：

```text
output/evals/real_runs/{YYYY-MM-DD}/{report_stem}_{HHMMSS}/
├── real_run_samples.json
├── human_labels.yaml
├── real_run_eval_results.json
├── real_run_eval_report.md
└── bad_cases.md
```

`real_run_eval_report.md` 是本次指标报告；`bad_cases.md` 是本地 badcase 分析文档，可同步到飞书文档作为复盘入口。

## 自动判定项

这些项由代码自动判断，不需要人工标注：

| 项 | 自动规则 |
|:--|:--|
| URL 是否格式有效 | 空 URL、非 HTTP(S)、包含 `...` / `…` 判为无效 |
| URL 是否被报告过滤 | `处理状态` 包含 `url_rejected` |
| 是否进入推荐区 | `处理状态` 为 `recommended` |
| 是否被过滤 | `处理状态` 以 `filtered_out`、`time_filtered`、`deduplicated`、`semantic_rejected` 开头 |
| 报告是否存在 | 文件存在且可读 |
| 全量审计是否存在 | 包含 `## 全量抓取与判断记录` |
| 投递包是否存在 | 同日期 `application_packages/<report_stem>/` 或相近目录存在 |
| 是否需要人工复核 | 推荐岗位、`agent_maybe` 备选观察岗位、高分但未推荐岗位、最终结论为 `apply` / `strong_apply` 但未进入推荐区 |

## 人工只标什么

人工只标语义质量，不标客观事实。也就是说，不需要人工判断“文件是否存在”“URL 是否为空”“有没有投递包”。

人工标注可以在本地 `human_labels.yaml` 里改，也可以在飞书多维表格的标注表里改。无论入口在哪里，人工只改语义判断字段；客观项仍由代码自动计算。

本地标注文件会带少量证据摘要，不复制完整 JD：

```yaml
labels:
  - record_id: "001"
    company: "美团"
    title: "支付平台AI智能产品经理"
    system_decision: "recommended"
    final_decision: "apply"
    score: 82
    review_reason: "recommended"
    evidence_summary:
      system_reason: "JD 明确要求 AI 产品规划和 Agent 工作流设计"
      resume_evidence: "Agent 项目、AI 产品评估体系"
      risks:
        - "商业化指标经验不足"
    scoring_breakdown:
      目标岗位匹配: 22
      核心职责匹配: 20
      简历证据: 17
    human_label: null
    human_scores:
      role_fit: null
      skill_match: null
      seniority_fit: null
      jd_quality: null
      risk_level: null
      apply_priority: null
    severity: medium
    review_notes: ""
```

标签集合固定为：

| 标签 | 含义 | 计入方式 |
|:--|:--|:--|
| `should_apply` | 明确值得投，推荐成立 | 正例 |
| `maybe` | 可以考虑，但需要用户偏好或简历策略确认；不要求进入主推荐区 | 弱正例 / 备选观察 |
| `should_reject` | 不应进入推荐区 | 负例 |
| `invalid_link` | 链接不可用；一般由代码自动判断，人工只在页面实际打不开时补 | 链接失败 |
| `unclear` | JD 信息不足或证据不够 | 不计入精确率/召回率，单独统计 |

可选维度分使用 1-5 分，留空则不参与该维度指标：

| 字段 | 中文名 | 什么时候填 | 含义 |
|:--|:--|:--|:--|
| `role_fit` | 岗位方向分 | 推荐、边界和 badcase | 岗位核心方向是否符合目标角色 |
| `skill_match` | 技能匹配分 | 推荐、边界和 badcase | JD 要求与简历/项目证据是否匹配 |
| `seniority_fit` | 职级匹配分 | 年限、职级不确定时 | 年限、资历、职责层级是否合适 |
| `jd_quality` | JD质量分 | JD 信息少或像标题党时 | JD 是否足够具体、真实、可判断 |
| `risk_level` | 风险等级分 | 有明显缺口时 | 5 表示风险高，1 表示风险低 |
| `apply_priority` | 投递优先级分 | 你愿不愿意投时 | 人类最终投递优先级 |

建议标注顺序：

1. 先标所有 `review_reason: recommended` 的岗位，用来算推荐精确率。
2. 再标 `review_reason: maybe_observation` 的岗位，用来判断 Agent 放进备选观察区是否合理。
3. 再标 `review_reason: high_confidence_filtered` 的岗位，用来发现被阈值、语义过滤或候选池上限挡住的好岗位。
4. 最后抽查 `review_reason: spot_check_filtered`，用于发现低分过滤里的系统性漏判。

默认工具不会让人工标所有岗位；低分、最终结论为 `skip`、URL 客观无效的记录由自动指标处理或留作抽查。

## 指标定义

| 指标 | 公式 | 含义 |
|:--|:--|:--|
| `label_completion_rate` | 已填人工标签 / 需人工标签 | 标注完成度 |
| `agent_reviewed_recommendation_rate` | `判断来源=agent` 的推荐岗位 / 推荐岗位 | 推荐区是否由 Agent 完成语义复核 |
| `recommendation_precision` | 推荐且正例或弱正例 / 已标推荐岗位 | 推荐区质量 |
| `strict_recommendation_precision` | 系统 `strong_apply` 且人工 `should_apply` / 已标 `strong_apply` 推荐岗位 | 强推荐质量 |
| `reviewed_recall` | 已推荐或进入 `agent_maybe` 的正/弱正例 / 非上限截断的已标正/弱正例 | 在人工复核范围内的语义覆盖，不把候选池/报告上限截断计入分母 |
| `reviewed_false_negative_rate` | 未推荐且未进入 `agent_maybe` 的正/弱正例 / 非上限截断的已标正/弱正例 | 人工复核范围内的误杀率；仅统计过滤、阈值或语义判断导致的漏推 |
| `candidate_limit_omission_rate` | 上限截断正例 / 已标正例 | 因 Agent 复核池或最终报告数量上限未展示的比例 |
| `invalid_url_rate` | 自动无效链接 / 全量记录 | 链接质量 |
| `recommended_invalid_url_rate` | 推荐区无效链接 / 推荐记录 | 推荐区链接质量 |
| `maybe_rate` | `maybe` / 已标记录 | 需要用户判断的模糊比例 |
| `unclear_rate` | `unclear` / 已标记录 | 证据不足比例 |
| `recommendation_volume` | 推荐记录数 / 全量记录数 | 推荐收敛度 |

报告里会显示中文指标名、英文键、数值和说明。维度分会额外产生 `role_fit_avg`、`skill_match_avg`、`seniority_fit_avg`、`jd_quality_avg`、`risk_level_avg`、`apply_priority_avg` 等人工平均分指标。

标注影响关系：

| 人工标注/分数 | 直接影响 |
|:--|:--|
| 推荐岗位标 `should_apply` | 提高推荐精确率；如果系统最终结论是 `strong_apply`，同时提高严格推荐精确率 |
| 推荐岗位标 `maybe` | 提高推荐精确率，不提高严格推荐精确率 |
| 推荐岗位标 `should_reject` | 形成“推荐误报” badcase，降低推荐精确率；如果系统最终结论是 `strong_apply`，同时影响严格推荐精确率 |
| `agent_maybe` 岗位标 `maybe` | 视为备选观察命中，不进入主推荐精确率，也不形成误杀 |
| `agent_maybe` 岗位标 `should_apply` | 说明系统保守了，形成“过滤误杀” badcase，降低召回率、提高误杀率 |
| 未推荐岗位标 `should_apply` / `maybe`，且不是 `agent_maybe` 或上限截断 | 形成“过滤误杀” badcase，降低召回率、提高误杀率 |
| 未推荐岗位标 `should_apply` / `maybe`，但处理状态为 `candidate_limit_omitted` / `report_limit_omitted` 或旧报告里的高分 `score_below_threshold_or_report_limit` | 形成“候选池截断” badcase，只影响候选池截断率，不计入误杀率 |
| 标 `invalid_link` | 形成链接坏例，影响链接质量指标 |
| 标 `unclear` | 不进入精确率/召回率，进入证据不足统计 |
| 推荐岗位 `判断来源` 不是 `agent` | 自动形成“缺少Agent语义复核” badcase，降低推荐区Agent复核率 |
| `role_fit` 低但系统推荐 | 倾向归因到语义过滤或岗位匹配 |
| `skill_match` 低但系统高分 | 倾向归因到推荐质量 |
| `jd_quality` 低但系统强推荐 | 倾向归因到证据不足或风险降权 |
| `risk_level` 高但系统未降权 | 倾向归因到风险惩罚逻辑 |
| `apply_priority` 高但系统没推荐 | 先区分是过滤/阈值问题还是候选池/报告上限问题，再分别归因 |

当人工标注未完成时，报告会显示 partial metrics，并把缺失标签列出来。只有 `label_completion_rate = 100%` 时，才把人工相关指标视为完整实测指标。

## Bad Case 处理

`src.eval_real_runs` 会在指标报告中生成 `Bad Cases / 坏案例` 表，并单独写出 `bad_cases.md`。飞书同步开启后，`bad_cases.md` 会覆盖同步到托管的飞书文档，方便集中复盘。

badcase 类型：

| 类型 | 触发条件 | 归因 | 影响指标 |
|:--|:--|:--|:--|
| 推荐误报 | 系统推荐，但人工标 `should_reject` | `recommendation_quality` | `recommendation_precision`；若系统为 `strong_apply`，还影响 `strict_recommendation_precision` |
| 缺少Agent语义复核 | 推荐岗位 URL 有效，但 `判断来源` 不是 `agent` | `recommendation_quality` | `agent_reviewed_recommendation_rate` |
| 过滤误杀 | 系统未推荐、不是 `agent_maybe`、也不是上限截断，但人工标 `should_apply` 或 `maybe`；或系统 `agent_maybe` 但人工标 `should_apply` | `matching_filtering` | `reviewed_recall`、`reviewed_false_negative_rate` |
| 候选池截断 | 系统未推荐，但原因是 Agent 复核池或最终报告数量上限 | `candidate_routing` | `candidate_limit_omission_rate` |
| 推荐区坏链接 | 推荐岗位 URL 自动判为无效 | `output_quality` | `recommended_invalid_url_rate`、`invalid_url_rate` |
| 人工确认坏链接 | 人工标 `invalid_link` | `output_quality` | 链接质量指标 |
| 证据不足 | 人工标 `unclear` | `recommendation_quality` | `unclear_rate` |

分析处理按五步：

1. 在 `real_run_eval_report.md` 或飞书 badcase 文档中看 badcase 表，定位 `record_id`。
2. 回到源报告的 `全量抓取与判断记录`，核对完整职责、完整任职要求、系统推荐理由、评分拆解、风险和人工备注。
3. 按 attribution 定位修复入口：`matching_filtering` 修语义过滤，`recommendation_quality` 修评分/风险/Prompt，`output_quality` 修链接、报告、投递包或 memory。
4. 修复代码、配置、Prompt 或 Agent 文档后，重跑 `python -m src.evaluation --fail-under 1.0` 和真实巡检评估。
5. 对稳定、明确、值得防退化的样本，写入 `evals/candidates/{YYYY-MM-DD}/candidate_cases.yaml`；修复后晋升到 regression 或 capability。

沉淀流程：

1. **候选沉淀**：写入 `evals/candidates/{YYYY-MM-DD}/candidate_cases.yaml`，保留报告路径、record_id、人工标签、系统判断和原因。
2. **归因**：归到 `matching_filtering`、`recommendation_quality`、`crawler_strategy`、`output_quality` 或 `instruction_drift`。
3. **提升为回归**：修复后，把明确、稳定、不可再退化的 case 提升到 `evals/regression/jobhunter_core.yaml`；边界样本放入 `evals/capability/jobhunter_hard_cases.yaml`。

## 飞书标注工作流

飞书只做人工输入和复盘镜像，本地仍然是可复现事实源。

初始化一次：

```powershell
# 首次使用或遇到 need_user_authorization 时先授权 Base
lark-cli auth login --domain base

python -m src.eval_lark_sync setup
```

该命令会在 `config/agent.yaml` 指向的岗位追踪多维表格中创建或复用 `SmartHunter真实评估标注` 表，并创建或复用 `SmartHunter真实评估BadCases` 文档。生成的 `eval_annotation_table_id`、`eval_badcase_doc_id` 和 `eval_badcase_doc_url` 只写入本地 `config/agent.yaml`，不提交 Git。

每次真实巡检后：

```powershell
# 1. 生成本地标注模板
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<report>.md"

# 2. 把模板同步到飞书标注表
python -m src.eval_lark_sync export-labels --labels "output/evals/real_runs/YYYY-MM-DD/<run_id>/human_labels.yaml" --run-id "<run_id>"

# 3. 在飞书标注表里只填人工标签、1-5 分和备注

# 4. 标完后拉回飞书标签、重算指标、同步 badcase 文档
python -m src.eval_lark_sync score-from-lark --report "output/YYYY-MM-DD/<report>.md" --run-id "<run_id>" --sync-badcases
```

飞书标注表字段分三类：

| 字段类型 | 字段 |
|:--|:--|
| 自动上下文 | 标注ID、评估运行ID、源报告、记录ID、公司、岗位、岗位链接、系统判断、最终结论、AI总分、复核原因 |
| 证据摘要 | 系统推荐理由、简历证据摘要、风险摘要、评分拆解摘要 |
| 人工输入 | 人工标签、岗位方向分、技能匹配分、职级匹配分、JD质量分、风险等级分、投递优先级分、人工备注 |

标注表不保存完整职责和完整任职要求，只保存证据摘要与源报告路径，避免冗余。完整事实以源报告和 `real_run_samples.json` 为准。

## 社招实测操作方案

后续要跑真实数据时，建议使用社招，因为岗位量更大：

```powershell
# 1. 用 Web 控制台或 CLI 跑社招巡检
python -m src.cli -t social -p "<profile_id_or_name>"

# 2. 对生成的报告创建标注文件
python -m src.eval_real_runs --report "output/YYYY-MM-DD/<profile_id>_<YYYYMMDD_HHMM>.md"

# 3. 只编辑 human_labels.yaml 里 human_label: null 的样本
#    或者同步到飞书标注表后在飞书填写人工标签和维度分。

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
- 推荐区 Agent 复核率。
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
