# SmartJobHunter Agent 评估体系方案

## 参考的行业实践

这套评估体系不是凭空设计的，参考了几类已经在行业里常用的 Agent 评估方式：

1. **OpenAI Agent Evals / Tools Evaluation**
   官方示例强调为 agent 建立 dataset，用 graders 检查最终输出和工具调用是否符合预期；工具类任务不能只看最终回答，还要看 tool name、参数和调用结果。
   参考：[OpenAI Agent evals](https://platform.openai.com/docs/guides/agent-evals)、[OpenAI tools evaluation cookbook](https://cookbook.openai.com/examples/evaluation/use-cases/tools-evaluation)。

2. **LangSmith Agent Evaluation**
   LangSmith 的复杂 agent 评估把每次运行拆成 trace/trajectory，评估中间步骤、工具轨迹和最终答案。这个思路适合 SmartJobHunter，因为岗位巡检也有清晰轨迹：策略巡检、证据采集、抓取、过滤、评分、报告。
   参考：[LangSmith evaluate a complex agent](https://docs.langchain.com/langsmith/evaluate-complex-agent)。

3. **SWE-bench Verified**
   编程 Agent 的主流评估不是问“回答好不好”，而是看真实 GitHub issue 是否被修好、测试是否通过。这给本项目的启发是：每日巡检也要用可验证结果衡量，比如岗位链接是否真实可访问、策略任务是否生成、Top 3 投递包是否完整。
   参考：[SWE-bench](https://www.swebench.com/)。

4. **tau-bench**
   tau-bench 用零售/航空等真实业务场景评估工具型 Agent，重点看多轮任务后系统状态是否达成目标。这个思路对应本项目的“最终状态”：报告是否生成、错误公司是否被归因、飞书推送开关是否生效、memory 是否更新。
   参考：[tau-bench](https://github.com/sierra-research/tau-bench)。

5. **Vertex AI / 生产监控式评估**
   生产级 GenAI 评估通常会把离线评测和线上监控结合起来，持续看质量、失败率和归因。SmartJobHunter 也应该把离线 eval、每日运行日志、策略任务和用户反馈沉淀成长期数据。
   参考：[Vertex AI Gen AI evaluation](https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview)。

## 和用户给出的三层框架的对应关系

你的原始框架是这套方案的主线：

1. **高质量数据评测集**
   当前落地为 `evals/jobhunter_agent_eval.yaml`。第一版是冷启动人工样例，覆盖核心意图、核心业务流程和高频 bad case。后续应从每日真实运行中沉淀真实样本：用户 profile、公司链接、工具调用、抓取结果、过滤结果、最终报告和用户反馈。

2. **量化 Agent 做对和做好的指标**
   当前落地为 `src.evaluation`，核心指标包括：
   - `tool_call_accuracy`：策略类任务是否选择了正确动作，例如 crawl、collect_evidence、blocked。
   - `task_completion_rate`：整套评测 case 是否闭环通过。
   - `matching.precision / recall / f1`：岗位过滤是否既少误报又少漏报。
   - `by_metric`：按抓取策略、匹配过滤、推荐质量、输出质量、指令一致性拆开看。

3. **归因机制和优化方向**
   每个 case 都带 `attribution`，失败后归入 `crawler_strategy`、`matching_filtering`、`recommendation_quality`、`output_quality`、`instruction_drift`。这能直接回答“问题出在哪”：是网站策略、profile/过滤、评分推荐、交付物，还是 Agent 文档漂移。

4. **自动化监控和持续迭代**
   当前已支持离线自动评估；下一步要把每日巡检日志、strategy task、飞书反馈和人工标注回流成新的 eval cases。也就是说，第一版是冷启动评测集，长期目标是从真实业务数据持续生长。

## 本项目的评估目标

SmartJobHunter 的 Agent 不是聊天机器人，它是一个“官网岗位巡检与求职辅助代理”。所以评估不应只看文案质量，而要覆盖四个业务闭环：

1. **会不会抓**：公司链接变化、未知策略、登录/验证码/反爬时，能否正确进入策略巡检、证据采集或阻断归因。
2. **会不会筛**：岗位是否按 profile、简历和 JD 语义过滤，而不是关键词机械命中。
3. **会不会推荐**：评分、风险、简历证据和推荐等级是否稳定。
4. **会不会交付**：报告链接是否真实、日期归档是否正确、Top 3 投递包是否完整、Agent 指令是否没有漂移。

## 第一版落地

当前已经落地为离线回归评测：

```powershell
python -m src.evaluation
```

数据集：

```text
evals/jobhunter_agent_eval.yaml
```

输出：

```text
output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS}/
├── agent_eval_results.json
└── agent_eval_report.md
```

## 指标设计

| 指标 | 含义 |
|:--|:--|
| `task_completion_rate` | 所有 eval case 的通过率，衡量整体闭环是否稳定 |
| `tool_call_accuracy` | 策略类 case 中 action 是否正确，近似工具/动作准确率 |
| `matching.precision` | 保留下来的岗位中，有多少本来就应该保留 |
| `matching.recall` | 应该保留的岗位，有多少没有被漏掉 |
| `matching.f1` | 匹配精确率和召回率的综合指标 |
| `by_metric` | 按 crawler_strategy、matching_filtering、recommendation_quality、output_quality、instruction_alignment 拆分 |
| `bad_case_attribution` | 失败 case 的归因分类，用来指导下一步修复 |

## 评测集覆盖

第一版评测集覆盖：

- AI 产品经理 / AI 应用产品 / AI 解决方案产品经理应该被保留。
- AI 产品运营、工程师噪声、销售/运营/标注类岗位应该被拒绝。
- 数据分析 profile 也能工作，项目不锁死产品经理。
- 未知官网策略应该生成 evidence 任务。
- 已验证且 fingerprint 不变的策略可以直接 crawl。
- fingerprint 变化、登录要求、普通登录按钮误判等策略边界被覆盖。
- 空链接、404-like 链接不会进入报告。
- Top 3 投递包会生成 3 封 Cover Letter。
- `AGENTS.md`、`CLAUDE.md`、`.claude/skills/jobhunter/skill.md` 必须表达同一套流程。

## 后续增强

1. **加入真实运行 trace**
   每日任务保存每家公司实际 action、工具命令、结果、耗时、失败原因，形成线上评估数据。

2. **加入人工标注集**
   对真实抓到的岗位，人工标注“该投 / 可考虑 / 不该投”和原因，形成更有业务价值的 matching gold set。

3. **加入公司级 SLA**
   按公司统计连续失败天数、策略任务未关闭天数、登录/反爬占比、成功抓取率。

4. **加入 Agent 复核指标**
   对 Python fallback 的 Top N 岗位做 Agent 二次复核，比较 fallback 与 Agent 的分歧，定位机械评分问题。

5. **加入飞书结果闭环**
   如果用户在飞书里标记“已投递 / 不合适 / 链接无效 / 推荐错了”，这些反馈应回流到 eval dataset。
