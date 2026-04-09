# SmartJobHunter Agent 操作指南

## Agent 工作流程

当用户请求运行求职巡检时，Agent 应按以下步骤执行：

### Step 1: 读取配置
```
1. 读取 config.yaml 获取求职意向配置
2. 读取 resumes/ 目录下的简历文件
3. 读取 data/seen_jobs.jsonl 获取已处理岗位的hash列表
```

### Step 2: 抓取岗位数据
```
调用 spider.py 爬虫抓取各大厂岗位：
- python spider.py tencent "关键词" --max-jobs 30
- python spider.py bytedance "关键词" --max-jobs 30
```

### Step 3: 三层过滤
```
第一层 - 时间过滤：只保留最近N天的岗位（默认3天）
第二层 - 去重过滤：排除 seen_jobs.jsonl 中已有的岗位
第三层 - 关键词过滤：匹配标题/职责中的关键词
```

### Step 4: AI 评估
```
对每个通过过滤的岗位，Agent 进行深度评估：
1. 匹配度评分 (0-100)
2. 匹配理由
3. 缺失技能/风险
4. 公司背调（可选）
```

### Step 5: 生成报告
```
将评估结果写入 output/ 目录的 Markdown 文件
格式：{日期}_{意向名称}.md
```

### Step 6: 更新去重数据库
```
将处理过的岗位 hash 追加到 data/seen_jobs.jsonl
```

## 常用命令

```bash
# 立即执行巡检
python main.py -t social      # 社招
python main.py -t internship  # 实习
python main.py -t campus      # 校招

# 健康检测
python scheduler.py --check

# 触发修复
python scheduler.py --repair

# 设置定时任务（Windows管理员）
setup_schedule.bat
```

## 自我修复机制

当爬虫失败时：

1. 运行 `python scheduler.py --check` 检测问题
2. 查看错误信息，分析原因
3. 使用浏览器F12检查网站API变化
4. 更新 spider.py 中的相关代码
5. 运行测试验证修复

## Bug修复流程

每次修复bug必须遵循：

1. **出计划** - 分析问题，制定方案
2. **Review** - 检查方案合理性
3. **执行测试** - 验证修复效果

## 支持的公司

| 公司 | 标识 | 社招 | 校招 |
|------|------|------|------|
| 腾讯 | tencent | ✅ | ✅ |
| 字节跳动 | bytedance | ✅ | ✅ |
