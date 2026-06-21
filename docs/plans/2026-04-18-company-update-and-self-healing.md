# 公司列表更新与自愈系统实现计划

> 平台说明（2026-06-21）：本文中的 `web-access` 仅限 Claude Code。Claude Code 未安装时执行 `npx skills add eze-is/web-access`；Codex 不加载该 Skill，使用内置 Browser/Chrome control。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成两件事：1) 更新所有公司的招聘官网配置 2) 设计自愈系统实现新公司自动分析和爬虫健康检测

**Architecture:**
- 任务1：遍历所有 `enabled: false` 的公司，使用 web-access skill 搜索有效招聘官网并分析 API
- 任务2：在爬虫工厂中增加健康检测和自愈逻辑，当爬取失败时自动触发修复流程

**Tech Stack:** Python, Playwright, YAML, web-access skill (CDP)

---

## 任务 1：更新所有公司配置

### Task 1.1: 获取待更新公司列表

**Files:**
- Read: `config/companies.yaml`

**Step 1: 提取所有 enabled: false 且 pattern: null 的公司**

```python
import yaml

with open('config/companies.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

disabled = [c for c in config['companies']
            if not c.get('enabled', False)
            and c.get('api', {}).get('pattern') is None]

# 输出公司列表供后续处理
for c in disabled:
    print(f"{c['id']}: {c['name']} - {c.get('urls', {}).get('social', 'N/A')}")
```

**预期结果：** 约 40 家公司需要更新

---

### Task 1.2: 批量搜索公司招聘官网

**使用 web-access skill 并行搜索**

对于每家公司：
1. 用 WebSearch 搜索 "{公司名}招聘官网 2026"
2. 从搜索结果提取有效 URL
3. 用 CDP 访问页面，分析 API 请求
4. 更新配置

**优先处理的公司（按重要性排序）：**
1. 华为 - 已有部分配置
2. 比亚迪 - 需登录
3. 浪潮集团
4. 搜狐
5. 唯品会
6. 58同城
7. 蚂蚁集团
8. 菜鸟网络
9. 网易游戏
10. 完美世界
11. 微软中国
12. 英伟达
13. 特斯拉
14. Intel
15. AMD
16. 思科
17. SAP
18. 建设银行
19. 中国移动
20. 中国电信

---

### Task 1.3: 分析并更新每家公司

**对于每家公司执行：**

```yaml
分析流程:
  1. 访问招聘页面
  2. 监听 API 请求 (XHR/Fetch)
  3. 识别招聘系统类型:
     - 自建系统: 提取 API pattern
     - mokahr: 使用 mokahr 模板
     - Workday: 使用 Workday 模板
     - 需登录: 标记需登录态
     - 失效: 标记 URL 失效
  4. 更新 companies.yaml
```

---

## 任务 2：设计自愈系统

### Task 2.1: 设计健康检测模块

**Files:**
- Create: `src/health_monitor.py`

**功能设计：**

```python
class HealthMonitor:
    """爬虫健康监控与自愈系统"""

    def check_crawler(self, company_id: str) -> HealthReport:
        """检测单个爬虫健康状态"""
        # 1. 检查配置完整性
        # 2. 尝试爬取少量岗位
        # 3. 返回健康报告

    def diagnose_failure(self, company_id: str, error: Exception) -> Diagnosis:
        """诊断失败原因"""
        # 1. 网络问题？
        # 2. API 变化？
        # 3. URL 失效？
        # 4. 反爬拦截？

    def auto_repair(self, company_id: str, diagnosis: Diagnosis) -> bool:
        """尝试自动修复"""
        # 1. 如果 URL 失效 -> 搜索新 URL
        # 2. 如果 API 变化 -> 重新分析 API
        # 3. 如果反爬 -> 调整策略
```

---

### Task 2.2: 实现新公司自动分析

**Files:**
- Create: `src/auto_analyzer.py`

**流程设计：**

```python
class AutoAnalyzer:
    """新公司自动分析器"""

    def analyze_new_company(self, company_name: str) -> CompanyConfig:
        """分析新公司并生成配置"""
        # 1. 搜索招聘官网
        official_url = self.search_official_site(company_name)

        # 2. 访问并分析
        with CDPBrowser() as browser:
            page = browser.new_page(official_url)

            # 3. 拦截 API 请求
            apis = page.capture_api_requests()

            # 4. 识别系统类型
            system_type = self.identify_system(apis)

            # 5. 生成配置
            config = self.generate_config(company_name, official_url, apis, system_type)

        return config

    def identify_system(self, apis: list) -> str:
        """识别招聘系统类型"""
        # mokahr: 包含 mokahr.com
        # workday: 包含 myworkdayjobs.com
        # zhiye: 包含 zhiye.com
        # self-built: 其他
```

---

### Task 2.3: 集成到爬虫工厂

**Files:**
- Modify: `src/crawler_factory.py`

**修改点：**

```python
def crawl_company(company_id: str, ...) -> List[dict]:
    """爬取单个公司，带自愈逻辑"""
    crawler = create_crawler(company_id)

    if crawler is None:
        # 触发自动分析
        analyzer = AutoAnalyzer()
        config = analyzer.analyze_new_company(company_id)
        if config:
            save_config(company_id, config)
            crawler = create_crawler(company_id)

    try:
        return crawler.crawl(...)
    except Exception as e:
        # 触发健康检测
        monitor = HealthMonitor()
        diagnosis = monitor.diagnose_failure(company_id, e)

        if monitor.auto_repair(company_id, diagnosis):
            # 重试
            return crawler.crawl(...)
        else:
            # 告知用户
            notify_user(f"无法修复 {company_id}: {diagnosis.reason}")
            return []
```

---

### Task 2.4: 创建配置模板

**Files:**
- Create: `config/system_templates.yaml`

**模板定义：**

```yaml
# 招聘系统模板 - 自动分析时使用

mokahr:
  api:
    pattern: "jobs"
    data_path: "data.jobs"
    type: "intercept"
  field_mappings:
    id: { source: "id" }
    title: { source: "name" }
    location: { source: "location" }
    category: { source: "category" }
  url_template: "https://app.mokahr.com/jobs/{id}"

workday:
  api:
    type: "dom"
  selectors:
    title: "[data-automation-id='jobTitle']"
    location: "[data-automation-id='locations']"
    posted: "[data-automation-id='postedOn']"

zhiye:
  api:
    type: "dom"
  selectors:
    job_list: ".job-list li"
    title: ".job-name"
    location: ".job-area"

self_built:
  # 需要手动分析
  api:
    type: "intercept"
```

---

### Task 2.5: 创建用户通知机制

**Files:**
- Create: `src/notifier.py`

**功能：**

```python
class Notifier:
    """用户通知器"""

    def notify_repair_failed(self, company_id: str, reason: str):
        """通知用户修复失败"""
        message = f"""
⚠️ 爬虫自愈失败

公司: {company_id}
原因: {reason}

建议操作:
1. 检查招聘网站是否变更
2. 手动更新配置文件
3. 联系开发者
"""
        # 写入日志
        self.write_log(message)
        # 可选：发送到飞书/邮件
```

---

## 执行顺序

1. **Task 1.1** - 获取待更新公司列表
2. **Task 1.2** - 批量搜索公司招聘官网（并行）
3. **Task 1.3** - 分析并更新每家公司
4. **Task 2.1** - 设计健康检测模块
5. **Task 2.2** - 实现新公司自动分析
6. **Task 2.3** - 集成到爬虫工厂
7. **Task 2.4** - 创建配置模板
8. **Task 2.5** - 创建用户通知机制

---

## 验收标准

- [ ] 所有 `enabled: false` 的公司都被检查并更新
- [ ] 新增自愈系统代码
- [ ] 爬虫失败时自动尝试修复
- [ ] 无法修复时告知用户原因
- [ ] 新公司可以自动分析并生成配置
