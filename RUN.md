# SmartJobHunter Agent 使用指南

## 目录结构

```
D:\ccworkplace\Smarthunter\
├── config.yaml              # 主配置文件（求职意向、关键词）
├── companies.yaml           # 公司列表配置（爬虫目标）
├── spider.py                # 爬虫模块（从companies.yaml读取）
├── main.py                  # Agent主程序入口
├── scheduler.py             # 调度器（定时任务+健康检测+自动推送）
├── health_check.py          # 爬虫健康检测模块
├── git_auto_push.py         # Git自动提交推送
├── setup_git.bat            # Git初始化脚本
├── setup_schedule.bat       # 设置Windows定时任务
├── run_scheduled.bat        # 定时任务启动脚本
├── .gitignore               # Git忽略文件
├── CLAUDE.md                # Agent行为指南
├── RUN.md                   # 本文档
│
├── resumes/                 # 简历文件目录 (Git忽略)
│   └── pm_tob.txt
│
├── data/                    # 数据目录 (Git忽略)
│   ├── seen_jobs.jsonl      # 去重数据库
│   └── *.json               # 爬虫抓取的原始数据
│
├── output/                  # 输出目录 (Git忽略)
│   └── YYYYMMDD_意向名称.md # 评估报告
│
└── logs/                    # 日志目录 (Git忽略)
    ├── health_check.jsonl   # 健康检测日志
    └── repair_tasks.json    # 修复任务记录
```

## 快速开始

### 1. 初始化 Git 仓库

```bash
# Windows - 双击运行
setup_git.bat

# 或手动执行
git init
git add -A
git commit -m "init: SmartJobHunter 初始化"
```

### 2. 连接 GitHub

```bash
# 1. 在 GitHub 创建新仓库 (Private)
#    https://github.com/new

# 2. 连接远程仓库
git remote add origin https://github.com/你的用户名/SmartJobHunter.git
git branch -M main
git push -u origin main
```

### 3. 查看公司列表

```bash
python spider.py --list
```

### 4. 执行巡检

```bash
# 社招岗位
python main.py -t social

# 实习岗位
python main.py -t internship
```

### 5. 设置定时任务（每天20:00）

```bash
# Windows - 以管理员身份运行
setup_schedule.bat
```

## Git 自动推送

每次巡检成功后，系统会自动提交并推送到 GitHub：

```
[巡检] 开始求职巡检...
[OK] 巡检完成
[Git] 自动推送更新...
[Git] 推送成功!
```

### 手动推送

```bash
python git_auto_push.py --push -m "更新配置"
```

### .gitignore 说明

以下文件/目录不会被提交到 Git：

```
resumes/      # 简历文件
output/       # 输出报告
logs/         # 日志文件
data/*.json   # 抓取数据
data/*.jsonl  # 去重数据库
debug_*.png   # 调试截图
```

## 公司配置 (companies.yaml)

```yaml
companies:
  # 腾讯
  - id: tencent
    name: 腾讯
    enabled: true
    urls:
      social: "https://careers.tencent.com/search.html?query={keyword}"
      campus: "https://careers.tencent.com/search.html?query={keyword}"

  # 字节跳动 - 校招/实习
  - id: bytedance
    name: 字节跳动
    enabled: true
    urls:
      campus: "https://jobs.bytedance.com/campus/position?keyword={keyword}"

  # 字节跳动 - 社招
  - id: bytedance_social
    name: 字节跳动(社招)
    enabled: true
    urls:
      social: "https://jobs.bytedance.com/experienced/position?keyword={keyword}"

  # 阿里巴巴（待开发）
  - id: alibaba
    name: 阿里巴巴
    enabled: false
    note: "需要分析API结构"
```

### 添加新公司

1. 在 `companies.yaml` 中添加配置
2. 设置 `enabled: false` 直到爬虫实现
3. 在 `spider.py` 中实现爬虫函数
4. 测试通过后设置 `enabled: true`

## 快速开始

### 1. 查看公司列表

```bash
python spider.py --list
```

### 2. 立即执行巡检

```bash
# 社招岗位
python main.py -t social

# 实习岗位
python main.py -t internship

# 校招岗位
python main.py -t campus
```

### 3. 健康检测

```bash
# 检测所有启用的公司
python scheduler.py --check
```

### 4. 设置定时任务（每天20:00）

```bash
# Windows - 以管理员身份运行
setup_schedule.bat
```

## 命令参考

### spider.py - 爬虫

| 命令 | 说明 |
|------|------|
| `python spider.py --list` | 列出所有公司配置 |
| `python spider.py tencent "关键词"` | 抓取指定公司 |
| `python spider.py --all "关键词"` | 抓取所有启用的公司 |

### main.py - 主程序

| 命令 | 说明 |
|------|------|
| `python main.py` | 运行完整巡检 |
| `python main.py -t social` | 社招岗位 |
| `python main.py -t internship` | 实习岗位 |
| `python main.py -t campus` | 校招岗位 |
| `python main.py --list-profiles` | 列出所有求职意向 |

### scheduler.py - 调度器

| 命令 | 说明 |
|------|------|
| `python scheduler.py --run` | 立即执行巡检 |
| `python scheduler.py --check` | 健康检测 |
| `python scheduler.py --repair` | 触发修复流程 |
| `python scheduler.py --schedule` | 定时模式（由系统调用） |

## 执行流程

```
Step 1: 抓取岗位数据
  └─ 从 companies.yaml 读取启用的公司

Step 2: 时间过滤（最近3天）
Step 3: 去重过滤
Step 4: 关键词过滤
Step 5: 岗位性质过滤（社招/校招/实习）
Step 6: 数据清洗
Step 7: AI评估（0-100分）
Step 8: 生成报告
Step 9: 更新去重数据库
```

## 自我修复机制

当爬虫失败时，系统会：

1. **检测问题** - 健康检测发现爬虫异常
2. **记录任务** - 写入 `logs/repair_tasks.json`
3. **输出提示** - 显示修复步骤

## 定时任务管理

### Windows

```bash
# 查看任务
schtasks /query /tn "SmartJobHunter"

# 立即运行
schtasks /run /tn "SmartJobHunter"

# 删除任务
schtasks /delete /tn "SmartJobHunter"
```

### Linux/Mac (crontab)

```bash
# 编辑crontab
crontab -e

# 添加定时任务（每天20:00）
0 20 * * * cd /path/to/Smarthunter && python scheduler.py --schedule
```
