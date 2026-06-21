---
name: profile
description: 从任意简历和求职目标生成候选人画像
user_invocable: true
---

# 候选人画像

当用户提供简历、要求分析简历、点击 Web“启动巡检”或要求判断岗位是否适合自己时，先执行本流程。

## 输入边界

- `config/resume_intents.yaml` 中的 `search_intent` 只是用户给出的搜索关键词、岗位类型和启用状态，不是正式 profile。
- 简历只支持 PDF、Markdown、TXT；DOCX 和其他格式不支持。
- 上传简历时不得创建正式 profile。只有当前 Agent 阅读完整简历后才能写入 `profiles/<profile_id>.md`。

## 执行步骤

1. 用 Python 读取简历原文并校验简历 fingerprint。
2. 读取对应 `search_intent`，把它作为求职目标输入，而不是候选人能力证据。
3. 使用 `prompts/build_candidate_profile.md` 分析角色、技能、领域、项目结果、约束和缺口。
4. 只使用简历证据，不得根据搜索关键词编造候选人能力。
5. 生成或更新 `profiles/<profile_id>.md`，然后才能进入岗位匹配。

正式 profile 必须服务于后续岗位匹配，不要写成泛泛的简历点评。
