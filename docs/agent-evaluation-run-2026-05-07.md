# Agent 评估执行结果（2026-05-07）

## 评估框架是否参考了用户给出的三层说明

有。当前实现按用户给出的“三层 + 监控迭代”框架落地：

1. **覆盖全面的数据评测集**
   - 文件：`evals/jobhunter_agent_eval.yaml`
   - 覆盖：核心意图、核心业务流程、高频 bad case。
   - 当前是冷启动人工样例；后续应从每日真实巡检日志、飞书反馈和人工标注中持续沉淀真实样本。

2. **量化 Agent 做对和做好的指标**
   - 文件：`src/evaluation.py`
   - 指标：任务完成率、工具/动作准确率、匹配 precision/recall/F1、分模块通过率。
   - 工具/动作准确率当前主要评估策略路由：`crawl`、`collect_evidence`、`blocked` 是否正确。

3. **bad case 归因机制**
   - 归因类型：`crawler_strategy`、`matching_filtering`、`recommendation_quality`、`output_quality`、`instruction_drift`。
   - 首次运行曾抓到 `instruction_drift`：`.claude` skill 已更新到新流程，但 `AGENTS.md` / `CLAUDE.md` 还没显式写出 `URL_VALIDATED` 和 `PACKAGED` 状态。修复后评估全通过。

4. **自动化监控和持续迭代**
   - 当前已支持离线自动评估：`python -m src.evaluation`。
   - 后续建议把每日策略任务、抓取日志、飞书投递反馈回流成新的 eval cases。

## 行业参考

- OpenAI cookbook 的 tools evaluation 示例强调用 dataset + grader 衡量工具调用输出是否正确。
- LangSmith 的复杂 Agent 评估强调 trajectory，不只看最终答案，还看执行路径。
- SWE-bench Verified 用真实 GitHub issue + 测试结果衡量 Agent 是否真的完成任务。
- tau-bench 用真实业务域里的工具、用户和策略规则评估 Agent 是否能完成多步任务。
- Vertex AI Gen AI evaluation 强调数据集、指标、rubric、自定义函数和可解释结果。

## 离线评估数据

命令：

```powershell
python -m src.evaluation --fail-under 1.0
```

结果：

| 指标 | 结果 |
|:--|:--|
| Case 数 | 14 |
| 通过数 | 14 |
| 任务完成率 | 100.0% |
| 工具/动作准确率 | 100.0% |
| 匹配 precision | 100.0% |
| 匹配 recall | 100.0% |
| 匹配 F1 | 100.0% |

报告路径：

```text
output/evals/2026-05-07/20260507_175419/agent_eval_report.md
```

## 真实官网 3 公司验证

关键词：`AI产品经理`

| 公司 | 抓取结果 | 样本岗位 | 我对相关性的判断 |
|:--|:--|:--|:--|
| 腾讯 | 成功，返回 5 个样本，页面捕获 10 个岗位 | 金融AI产品经理、腾讯视频-AI 产品经理、PC应用宝-AI产品经理、AI产品经理-AI生成游戏、元宝- AI产品经理（教育方向） | 符合“AI产品经理 / AI应用产品”方向；但部分偏 C 端内容、游戏或教育，若 profile 强约束 ToB/SaaS，需要在推荐理由里提示业务场景偏差 |
| 字节跳动社招 | 成功，返回 5 个样本，页面捕获 10 个岗位 | AI产品经理、AI产品经理-火山方舟MaaS、AI产品经理（异构计算方向）-基础设施 | 火山方舟 MaaS 高度符合大模型平台 / AI 应用 / ToB 方向；异构计算方向更偏基础设施，适合技术产品，但应低于应用/解决方案类岗位 |
| 美团 | 成功，返回 5 个样本，页面捕获 10 个岗位 | AI产品经理、营销AI产品经理、协同办公AI产品经理、AI产品经理-商家方向 | 整体符合 AI 产品方向；协同办公和商家方向更接近企业/业务场景，营销 AI 产品需区分“产品经理”与“运营/增长”职责，避免关键词误判 |

额外观察：

- 阿里巴巴用同一关键词抓到过 `AI应用研发工程师`、`Agent Infra工程师` 等技术岗位。这类岗位标题含 AI，但不符合产品经理 profile。当前 eval 集已经包含“工程师噪声应该拒绝”的 bad case。
- 因此后续真实样本标注时，应优先沉淀“AI 关键词但角色不对”的负样本，这是目前最容易污染报告的类型。

## 当前结论

第一版评估体系已经可用，能回答三个问题：

1. Agent/Python 工具链有没有按正确流程走。
2. 岗位过滤和推荐有没有明显机械误判。
3. 失败时能不能归因到抓取策略、匹配过滤、推荐质量、输出质量或指令漂移。

但它还不是最终形态。下一步最关键的是把真实每日巡检结果转成评测数据，而不是长期依赖人工构造样例。
