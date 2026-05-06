---
name: profile
description: 从任意简历和求职目标生成候选人画像
user_invocable: true
---

# 候选人画像

当用户提供简历、要求分析简历、或要求判断岗位是否适合自己时，先执行本流程。

1. 用 Python 读取简历原文。
2. 使用 `prompts/build_candidate_profile.md` 生成 candidate profile。
3. 只使用简历证据，不要编造能力。
4. 如果简历是图片且 Python 只能返回占位符，使用当前 agent 平台的视觉能力读取图片。

候选人画像必须服务于后续岗位匹配，不要写成泛泛的简历点评。
