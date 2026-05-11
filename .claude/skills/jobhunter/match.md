---
name: match
description: 通用候选人-岗位匹配判断
user_invocable: true
---

# 通用岗位匹配

当用户要求评估岗位、运行巡检、或判断岗位是否适合时，按以下流程：

1. 如果还没有 candidate profile，先执行 `profile.md`。
2. 对每个 JD 使用 `prompts/analyze_job.md` 生成 job profile。
3. 使用 `prompts/match_candidate_job.md` 进行匹配。
4. 输出必须包含 JD 证据、简历证据、风险、缺口和投递建议。
5. Python fallback 只能作为粗筛，最终判断由 agent 完成。

不要默认用户是产品经理；目标岗位来自 `profiles/*.md` 的 `target_roles`。
