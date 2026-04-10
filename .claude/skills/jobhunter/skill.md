---
name: jobhunter
description: 智能求职巡检 Agent
---

# SmartJobHunter Agent

## 状态机流程

INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE

---

### INIT
**目标**: 初始化并加载所有配置
**执行动作**: 调用 load_config 工具，读取 profiles, resumes, companies, agent config
**状态转换**: → LOADED

### LOADED
**目标**: 抓取岗位数据
**执行动作**: 调用 crawl 工具
**状态转换**: → CRAWLED

### CRAWLED
**目标**: 过滤岗位（确定性 + 语义）
**执行动作**: filter_by_time → dedup → semantic_filter
**状态转换**: → FILTERED

### FILTERED
**目标**: 深度评估匹配岗位
**执行动作**: clean_data → analyze_resume → evaluate
**状态转换**: → EVALUATED

### EVALUATED
**目标**: 生成报告
**执行动作**: report prompt → save_report
**状态转换**: → REPORTED

### REPORTED
**目标**: 更新 Memory
**执行动作**: update_memory
**状态转换**: → DONE

### DONE
**输出**: ✅ 巡检完成

---

## 执行日志格式
[INIT] 开始加载配置...
[LOADED] ✓ 配置加载完成
...

## 错误处理
[ERROR] 状态: XXX, 错误: ...
