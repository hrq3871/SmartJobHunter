---
name: load_config
description: 加载所有配置文件
---

# load_config 工具

## 功能
加载求职意向、简历、公司列表、Agent配置

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| profile_name | string | 否 | 指定意向名称，为空则加载所有启用的 |

## 输出
```json
{
  "profiles": [
    {
      "name": "产品经理-TOB方向",
      "enabled": true,
      "job_type": "社招",
      "resume": "resumes/pm_tob.md",
      "keywords": ["产品经理", "TOB", "SaaS"],
      "intent": "寻找 TOB SaaS 产品经理岗位..."
    }
  ],
  "agent_config": {
    "decision_level": "moderate",
    "time_filter_days": 3,
    "threshold_score": 70
  },
  "companies": [...]
}
```

## 实现位置
`src/cli.py` → `load_config()`
