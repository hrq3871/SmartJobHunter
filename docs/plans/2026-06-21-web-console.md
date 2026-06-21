# SmartJobHunter 本地可视化管理控制台 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个零依赖本地 Web 控制台，可视化管理系统配置、简历、任务开关、巡检结果和健康状态。

**Architecture:** FastAPI 后端（一个文件，读写现有 YAML/MD/JSON 文件） + 单 HTML SPA 前端（内联 CSS/JS，浏览器直接打开，零 npm）。

**Tech Stack:** Python FastAPI + uvicorn + python-multipart；前端 HTML5 + 原生 JS + CSS Grid

**Port:** 8080

---

## 数据流总览

```
浏览器 (localhost:8080)
  │
  ├─ GET  /api/companies        ← config/companies.yaml
  ├─ PUT  /api/companies/{id}   → config/companies.yaml (写回)
  ├─ POST /api/companies/{id}/test → crawler_factory.test_crawler()
  │
  ├─ GET  /api/profiles         ← profiles/*.md (解析 YAML frontmatter)
  ├─ PUT  /api/profiles/{id}    → profiles/{id}.md (写回 enable/disable)
  │
  ├─ GET  /api/resumes          ← resumes/ 目录列表
  ├─ POST /api/resumes          → resumes/ 上传新文件
  ├─ DELETE /api/resumes/{name} → resumes/{name} 删除
  │
  ├─ GET  /api/config           ← config/agent.yaml (或 agent.sample.yaml)
  ├─ PUT  /api/config           → config/agent.yaml
  │
  ├─ GET  /api/reports          ← output/ 目录扫描 + 报告摘要提取
  ├─ GET  /api/reports/{file}   → 完整 Markdown 渲染
  │
  ├─ GET  /api/health           ← logs/strategy_tasks/ 聚合
  └─ GET  /api/health/{company} ← 单个公司 task + evidence
```

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/web_ui.py` | **Create** | FastAPI 后端，~350行 |
| `templates/index.html` | **Create** | 单页 SPA 前端，~550行 |
| `requirements-web.txt` | **Create** | Web 依赖声明 |
| `config/agent.yaml` | **Read/Write** | 已有，读写飞书开关等 |
| `config/companies.yaml` | **Read/Write** | 已有，读写公司配置 |

---

## Task 1: 项目骨架 — 后端入口 + 静态文件服务

**Files:**
- Create: `src/web_ui.py`
- Create: `requirements-web.txt`

**Step 1: 创建依赖文件**

```bash
cat > requirements-web.txt << 'EOF'
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
python-multipart>=0.0.5
pyyaml>=6.0
EOF
pip install -r requirements-web.txt
```

**Step 2: 创建 FastAPI 骨架**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SmartJobHunter Web Console — 本地可视化管理控制台."""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / "templates"

app = FastAPI(title="SmartJobHunter Console", version="0.1.0")

@app.get("/")
async def index():
    return FileResponse(TEMPLATES / "index.html")

# 后续 Task 在此追加路由
```

**Step 3: 启动验证**

```bash
python -m uvicorn src.web_ui:app --reload --port 8080
# 浏览器打开 http://localhost:8080 → 应显示 404 (尚未创建 index.html)
```

**Step 4: Commit**

```bash
git add src/web_ui.py requirements-web.txt
git commit -m "feat: add web console skeleton with FastAPI"
```

---

## Task 2: 公司配置 API — 列表 + 编辑 + 测试

**Files:**
- Modify: `src/web_ui.py` (追加路由)

**API 设计:**

```
GET  /api/companies
  → 返回所有公司列表 (解析 companies.yaml, 含 enabled/strategy/urls)

PUT  /api/companies/{company_id}
  → body: {enabled: bool, urls: {social, campus, internship}, note: str}
  → 写回 companies.yaml (仅允许修改 enabled/urls/note, 不动 api/strategy)

POST /api/companies/{company_id}/test
  → body: {keyword: "产品经理", job_type: "social"}
  → 异步执行 crawler_factory.test_crawler(), 返回 {ok, jobs_count, sample_titles}
```

**Step 1: 实现 GET /api/companies**

调用 `crawler_factory.get_enabled_companies()` + 补充 disabled 公司，返回统一列表。每条包含 `id, name, enabled, urls, strategy_type, strategy_status, note`。

**Step 2: 实现 PUT /api/companies/{id}**

只允许修改 `enabled`, `urls.*`, `note` 三个字段。使用正则定位 YAML 中目标公司块并替换（类似 `strategy_applier._replace_company_block`）。

**Step 3: 实现 POST /api/companies/{id}/test**

```python
from src.crawler_factory import test_crawler as _test
# 返回 {ok: bool, jobs_count: int, sample_titles: [...]}
```

**Step 4: 手动 curl 验证**

```bash
curl http://localhost:8080/api/companies | python -m json.tool | head -30
curl -X PUT http://localhost:8080/api/companies/tencent -H "Content-Type: application/json" -d '{"enabled":true}'
```

**Step 5: Commit**

---

## Task 3: 简历管理 API — 列表 + 上传 + 删除

**Files:**
- Modify: `src/web_ui.py` (追加路由)

**API 设计:**

```
GET  /api/resumes
  → 列出 resumes/ 目录下所有文件 (名称、大小、修改时间、格式)

POST /api/resumes
  → multipart/form-data 上传文件到 resumes/
  → 限制: 仅允许 .txt .md .docx .pdf .png .jpg, 最大 10MB

DELETE /api/resumes/{filename}
  → 删除指定文件, 同时检查 profiles 中是否引用 (返回警告)
```

**Step 1: 实现 GET**

```python
@app.get("/api/resumes")
async def list_resumes():
    resume_dir = ROOT / "resumes"
    files = []
    for f in resume_dir.iterdir():
        if f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "format": f.suffix.lstrip("."),
            })
    return sorted(files, key=lambda x: x["modified"], reverse=True)
```

**Step 2: 实现 POST (上传)**

使用 `UploadFile` + `python-multipart`。上传后检查 profiles 中哪些引用了这个文件名。

**Step 3: 实现 DELETE**

删除前扫描所有 profile YAML frontmatter，返回被引用的 profile 列表作为警告。

**Step 4: Commit**

---

## Task 4: 任务配置 API — agent.yaml 读写

**Files:**
- Modify: `src/web_ui.py` (追加路由)

**API 设计:**

```
GET  /api/config
  → 返回 agent.yaml 完整内容 (如不存在则返回 agent.sample.yaml)
  → 输出: {decision_level, threshold_score, feishu: {enabled, ...}, profiles: [...]}

PUT  /api/config
  → body: {feishu: {enabled: bool}, profiles: [{name, enabled}]}
  → 写回 agent.yaml (只写 agent.yaml, 不回退到 sample)
```

**Step 1: 实现 GET**

读取 `config/agent.yaml`，如不存在读 `config/agent.sample.yaml`。额外扫描 `profiles/` 目录，在返回中加入 `profiles` 数组 (name + enabled 状态)。

**Step 2: 实现 PUT**

如果 `config/agent.yaml` 不存在，从 sample 复制创建。然后更新 feishu.enabled、飞书凭证等字段。**不提交真实凭证到 Git。**

同时处理 profile enable/disable：修改对应 `profiles/*.md` 的 YAML frontmatter 中 `enabled` 字段。

**Step 3: Commit**

---

## Task 5: 结果浏览 API — 报告列表 + 渲染

**Files:**
- Modify: `src/web_ui.py` (追加路由)

**API 设计:**

```
GET  /api/reports
  → 扫描 output/ 目录, 返回报告列表
  → 每条: {date, profile_name, path, job_count, top_score, file_url}

GET  /api/reports/{filename}
  → 返回完整 Markdown 内容 (用于前端渲染)
  → URL 参数: ?download=true 触发下载
```

**Step 1: 实现报告扫描**

```python
@app.get("/api/reports")
async def list_reports():
    output_dir = ROOT / "output"
    reports = []
    for f in sorted(output_dir.rglob("*.md"), reverse=True):
        if "evals" in f.parts or "application_packages" in f.parts:
            continue
        if f.name == "example_report.md":
            continue
        # 解析报告标题行提取 profile 和 job count
        text = f.read_text(encoding="utf-8")[:2000]
        profile = _extract_field(text, "Profile")
        job_count = _extract_field(text, "Jobs Found")
        top_score = _extract_top_score(text)
        reports.append({
            "filename": str(f.relative_to(output_dir)),
            "date": _extract_date(f),
            "profile": profile,
            "job_count": int(job_count) if job_count else 0,
            "top_score": top_score,
            "size": f.stat().st_size,
        })
    return reports
```

**Step 2: 实现报告内容获取**

返回原始 Markdown 文本，前端用简易 Markdown 渲染器或 `<pre>` 展示。

**Step 3: Commit**

---

## Task 6: 健康面板 API

**Files:**
- Modify: `src/web_ui.py` (追加路由)

**API 设计:**

```
GET  /api/health
  → 扫描 logs/strategy_tasks/ 目录
  → 聚合每条 task 的 company/status/decision/created_at
  → 返回: {summary: {total, pending, blocked, failed}, tasks: [...]}
```

**Step 1: 实现健康数据聚合**

```python
@app.get("/api/health")
async def health_overview():
    task_root = ROOT / "logs" / "strategy_tasks"
    tasks = []
    for task_dir in sorted(task_root.iterdir()):
        if not task_dir.is_dir():
            continue
        for ts_dir in sorted(task_dir.iterdir(), reverse=True):
            task_file = ts_dir / "task.json"
            if task_file.exists():
                data = json.loads(task_file.read_text(encoding="utf-8"))
                tasks.append({
                    "company_id": data["company"]["id"],
                    "company_name": data["company"]["name"],
                    "status": data["status"],
                    "reason": data.get("decision", {}).get("reason", ""),
                    "created_at": data["created_at"],
                    "evidence_dir": data.get("evidence_dir"),
                })
    # 按公司聚合，只保留最新状态
    latest = {}
    for t in tasks:
        cid = t["company_id"]
        if cid not in latest or t["created_at"] > latest[cid]["created_at"]:
            latest[cid] = t
    return {
        "summary": {
            "total": len(latest),
            "pending": sum(1 for t in latest.values() if t["status"] == "pending"),
            "blocked": sum(1 for t in latest.values() if t["status"] == "blocked"),
            "failed": sum(1 for t in latest.values() if t["status"] == "failed"),
        },
        "tasks": sorted(latest.values(), key=lambda x: x["created_at"], reverse=True),
    }
```

**Step 2: Commit**

---

## Task 7: 前端 SPA — HTML 骨架 + Tab 导航

**Files:**
- Create: `templates/index.html`

**Step 1: 创建 HTML 骨架**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SmartJobHunter Console</title>
<style>
  /* 内联 CSS — 暗色主题, CSS Grid 布局 */
  :root { --bg: #1a1a2e; --card: #16213e; --accent: #0f3460; --text: #e0e0e0; --green: #4caf50; --red: #f44336; --yellow: #ff9800; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  header { background: var(--card); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; }
  nav { display: flex; gap: 4px; }
  nav button { background: transparent; color: #888; border: none; padding: 10px 20px; cursor: pointer; border-radius: 6px; font-size: 14px; transition: all .2s; }
  nav button.active { background: var(--accent); color: #fff; }
  nav button:hover:not(.active) { color: #ccc; }
  main { max-width: 1400px; margin: 24px auto; padding: 0 24px; }
  .card { background: var(--card); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  .status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
  .status-ok { background: var(--green); color: #fff; }
  .status-warn { background: var(--yellow); color: #000; }
  .status-err { background: var(--red); color: #fff; }
  /* 公司列表表格、表单等样式后续任务补充 */
</style>
</head>
<body>
<header>
  <h1>🎯 SmartJobHunter Console</h1>
  <nav id="tabs">
    <button class="active" data-tab="companies">📋 公司配置</button>
    <button data-tab="resumes">📄 简历管理</button>
    <button data-tab="config">⚙️ 任务配置</button>
    <button data-tab="reports">📊 巡检结果</button>
    <button data-tab="health">🩺 健康面板</button>
  </nav>
</header>
<main id="content"></main>
<script>
  // Tab 切换 + API 调用 + DOM 渲染 (后续任务逐模块实现)
  document.querySelectorAll('nav button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadTab(btn.dataset.tab);
    });
  });
  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: {'Content-Type': 'application/json'}, ...opts });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
  }
  function loadTab(tab) { /* 委派到各模块渲染函数 */ }
  loadTab('companies');
</script>
</body>
</html>
```

**Step 2: 浏览器打开验证**

```bash
python -m uvicorn src.web_ui:app --port 8080
# 打开 http://localhost:8080 → 应看到暗色主题 + 5 个 Tab
```

**Step 3: Commit**

---

## Task 8: 前端 — 公司配置 Tab

**Files:**
- Modify: `templates/index.html` (追加 JS 渲染逻辑)

**功能:**
1. 表格列出所有公司（名称、ID、策略类型、状态、开关）
2. 点击行展开编辑面板（URL 编辑、启用/禁用切换）
3. 每行一个"测试"按钮 → 调用 POST /api/companies/{id}/test
4. 测试结果显示在行下方（岗位数 + 前 3 个标题）

**Step 1: 实现渲染函数**

```javascript
async function renderCompanies() {
  const data = await api('/api/companies');
  const html = data.map(c => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <strong>${c.name}</strong>
          <code style="margin-left:8px;color:#888">${c.id}</code>
          <span class="status-badge ${c.strategy_type === 'config_intercept' ? 'status-ok' : 'status-warn'}">${c.strategy_type || 'unknown'}</span>
        </div>
        <div>
          <label><input type="checkbox" ${c.enabled ? 'checked' : ''} onchange="toggleCompany('${c.id}', this.checked)"> 启用</label>
          <button onclick="testCompany('${c.id}')" style="margin-left:12px">🧪 测试</button>
        </div>
      </div>
      <div style="margin-top:8px;font-size:13px;color:#888">
        ${Object.entries(c.urls || {}).map(([k,v]) => `<span style="margin-right:12px">${k}: ${v}</span>`).join('')}
      </div>
      <div id="test-${c.id}" style="margin-top:8px"></div>
    </div>
  `).join('');
  document.getElementById('content').innerHTML = html;
}

async function toggleCompany(id, enabled) {
  await api(`/api/companies/${id}`, {method: 'PUT', body: JSON.stringify({enabled})});
}

async function testCompany(id) {
  const el = document.getElementById(`test-${id}`);
  el.innerHTML = '⏳ 测试中...';
  const result = await api(`/api/companies/${id}/test`, {method: 'POST', body: JSON.stringify({keyword:'产品经理', job_type:'social'})});
  el.innerHTML = result.ok
    ? `✅ ${result.jobs_count} 个岗位: ${(result.sample_titles||[]).slice(0,3).join(', ')}`
    : `❌ 抓取失败`;
}
```

**Step 2: 接入 loadTab 路由**

```javascript
function loadTab(tab) {
  const renderers = { companies: renderCompanies, resumes: ()=>content.innerHTML='<div class=card>简历管理 (开发中)</div>', config: ()=>content.innerHTML='<div class=card>任务配置 (开发中)</div>', reports: ()=>content.innerHTML='<div class=card>巡检结果 (开发中)</div>', health: ()=>content.innerHTML='<div class=card>健康面板 (开发中)</div>' };
  renderers[tab]();
}
```

**Step 3: Commit**

---

## Task 9: 前端 — 简历管理 Tab

**Files:**
- Modify: `templates/index.html` (追加渲染函数)

**功能:**
1. 文件上传区域（拖拽或点击上传）
2. 已上传文件列表（文件名、大小、时间）
3. 每行删除按钮（带确认）

**Step 1: 实现渲染函数**

```javascript
async function renderResumes() {
  const data = await api('/api/resumes');
  const html = `
    <div class="card">
      <h3>上传简历</h3>
      <input type="file" id="resumeUpload" accept=".txt,.md,.docx,.pdf,.png,.jpg" multiple style="margin:12px 0">
      <div id="uploadStatus"></div>
    </div>
    <div class="card">
      <h3>已上传 (${data.length} 个文件)</h3>
      ${data.map(f => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #333">
          <div>
            <span>📄 ${f.name}</span>
            <span style="margin-left:12px;color:#888;font-size:12px">${formatSize(f.size)} · ${f.modified?.slice(0,10)}</span>
          </div>
          <button onclick="deleteResume('${f.name}')" style="color:var(--red);background:none;border:1px solid var(--red);padding:4px 12px;border-radius:4px;cursor:pointer">删除</button>
        </div>
      `).join('')}
    </div>`;
  content.innerHTML = html;
  // 上传事件绑定
  document.getElementById('resumeUpload').addEventListener('change', uploadResume);
}

async function uploadResume(e) {
  const files = e.target.files;
  for (const f of files) {
    const form = new FormData(); form.append('file', f);
    const res = await fetch('/api/resumes', {method:'POST', body:form});
    document.getElementById('uploadStatus').innerHTML = res.ok ? '✅ 上传成功' : '❌ 上传失败';
  }
  if (files.length) setTimeout(renderResumes, 500);
}

async function deleteResume(name) {
  if (!confirm('删除 ${name}?')) return;
  await fetch('/api/resumes/${encodeURIComponent(name)}', {method:'DELETE'});
  renderResumes();
}

function formatSize(bytes) { return bytes < 1024*1024 ? Math.round(bytes/1024)+'KB' : (bytes/(1024*1024)).toFixed(1)+'MB'; }
```

**Step 2: 接入 loadTab**

**Step 3: Commit**

---

## Task 10: 前端 — 任务配置 Tab

**Files:**
- Modify: `templates/index.html` (追加渲染函数)

**功能:**
1. 飞书推送开关（大号 toggle）
2. Profile 列表（名称 + 启用/禁用开关）
3. 基础配置展示（decision_level, threshold_score — 只读）

**Step 1: 实现渲染函数**

```javascript
async function renderConfig() {
  const data = await api('/api/config');
  const html = `
    <div class="card">
      <h3>🤖 基础配置</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
        <div><label>决策级别</label><br><strong>${data.decision_level}</strong></div>
        <div><label>评分阈值</label><br><strong>${data.threshold_score}</strong></div>
        <div><label>时间过滤(天)</label><br><strong>${data.time_filter_days}</strong></div>
        <div><label>每报告最多岗位</label><br><strong>${data.output?.max_jobs_per_report || '-'}</strong></div>
      </div>
    </div>
    <div class="card">
      <h3>📡 飞书推送</h3>
      <div style="display:flex;align-items:center;gap:16px;margin-top:12px">
        <label class="toggle"><input type="checkbox" ${data.feishu?.enabled ? 'checked' : ''} onchange="toggleFeishu(this.checked)"><span>${data.feishu?.enabled ? '已开启' : '已关闭'}</span></label>
      </div>
    </div>
    <div class="card">
      <h3>📋 求职意向</h3>
      ${(data.profiles||[]).map(p => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #333">
          <span>📌 ${p.name} <code style="color:#888;margin-left:8px">${p.job_type||''}</code></span>
          <label><input type="checkbox" ${p.enabled ? 'checked' : ''} onchange="toggleProfile('${p.name}', this.checked)"> 启用</label>
        </div>
      `).join('')}
    </div>`;
  content.innerHTML = html;
}

async function toggleFeishu(enabled) {
  await api('/api/config', {method:'PUT', body:JSON.stringify({feishu:{enabled}})});
}

async function toggleProfile(name, enabled) {
  await api('/api/config', {method:'PUT', body:JSON.stringify({profiles:[{name,enabled}]})});
}
```

**Step 2: Commit**

---

## Task 11: 前端 — 巡检结果 Tab

**Files:**
- Modify: `templates/index.html` (追加渲染函数)

**功能:**
1. 报告列表（按日期倒序，显示日期/意向/岗位数/最高分）
2. 点击展开报告详情（简易 Markdown 渲染）
3. 按意向筛选

**Step 1: 实现渲染函数**

```javascript
async function renderReports() {
  const data = await api('/api/reports');
  const profiles = [...new Set(data.map(r => r.profile).filter(Boolean))];
  const html = `
    <div class="card" style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="filter-btn active" onclick="filterReports('all')">全部</button>
      ${profiles.map(p => `<button class="filter-btn" onclick="filterReports('${p}')">${p}</button>`).join('')}
    </div>
    ${data.map(r => `
      <div class="card report-item" data-profile="${r.profile || ''}" style="cursor:pointer" onclick="viewReport('${r.filename}')">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>📅 ${r.date}</strong>
            <span style="margin-left:12px;color:#888">${r.profile || '未知意向'} · ${r.job_count} 个岗位 · 最高 ${r.top_score} 分</span>
          </div>
          <span style="color:#888;font-size:13px">${formatSize(r.size)}</span>
        </div>
      </div>
    `).join('') || '<div class="card" style="color:#888">暂无报告</div>'}
    <div id="reportDetail"></div>`;
  content.innerHTML = html;
}

function filterReports(profile) {
  document.querySelectorAll('.report-item').forEach(el => {
    el.style.display = (profile === 'all' || el.dataset.profile === profile) ? '' : 'none';
  });
}

async function viewReport(filename) {
  const res = await fetch('/api/reports/' + encodeURIComponent(filename));
  const md = await res.text();
  document.getElementById('reportDetail').innerHTML = '<div class="card"><h3>📄 ' + filename + '</h3><pre style="white-space:pre-wrap;font-size:13px;line-height:1.6;max-height:70vh;overflow-y:auto">' + escapeHtml(md) + '</pre></div>';
  document.getElementById('reportDetail').scrollIntoView();
}

function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
```

**Step 2: Commit**

---

## Task 12: 前端 — 健康面板 Tab

**Files:**
- Modify: `templates/index.html` (追加渲染函数)

**功能:**
1. 摘要卡片（总数/待处理/阻塞/失败）
2. 任务列表（公司、状态、原因、时间）

**Step 1: 实现渲染函数**

```javascript
async function renderHealth() {
  const data = await api('/api/health');
  const s = data.summary;
  const html = `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px">
      <div class="card" style="text-align:center"><div style="font-size:32px">${s.total}</div><div style="color:#888">总异常</div></div>
      <div class="card" style="text-align:center;border-left:3px solid var(--yellow)"><div style="font-size:32px">${s.pending}</div><div style="color:#888">待处理</div></div>
      <div class="card" style="text-align:center;border-left:3px solid var(--red)"><div style="font-size:32px">${s.blocked}</div><div style="color:#888">阻塞</div></div>
      <div class="card" style="text-align:center;border-left:3px solid #666"><div style="font-size:32px">${s.failed}</div><div style="color:#888">失败</div></div>
    </div>
    ${data.tasks.map(t => `
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>${t.company_name}</strong>
            <span class="status-badge ${t.status==='blocked'?'status-err':t.status==='pending'?'status-warn':'status-ok'}" style="margin-left:8px">${t.status}</span>
          </div>
          <span style="color:#888;font-size:12px">${t.created_at?.slice(0,16)||''}</span>
        </div>
        <div style="margin-top:8px;color:#888;font-size:13px">${t.reason || '无详细信息'}</div>
        ${t.evidence_dir ? `<div style="margin-top:4px;font-size:12px;color:#666">📁 ${t.evidence_dir}</div>` : ''}
      </div>
    `).join('') || '<div class="card" style="color:#888">✅ 暂无异常</div>'}`;
  content.innerHTML = html;
}
```

**Step 2: Commit**

---

## Task 13: 集成测试 & 收尾

**Step 1: 全功能冒烟测试**

```bash
# 启动
python -m uvicorn src.web_ui:app --port 8080 &

# 测试所有 API
curl -s http://localhost:8080/api/companies | python -c "import sys,json;d=json.load(sys.stdin);print(f'Companies: {len(d)}')"
curl -s http://localhost:8080/api/resumes | python -c "import sys,json;d=json.load(sys.stdin);print(f'Resumes: {len(d)}')"
curl -s http://localhost:8080/api/config | python -c "import sys,json;d=json.load(sys.stdin);print(f'Feishu: {d.get(\"feishu\",{}).get(\"enabled\")}')"
curl -s http://localhost:8080/api/reports | python -c "import sys,json;d=json.load(sys.stdin);print(f'Reports: {len(d)}')"
curl -s http://localhost:8080/api/health | python -c "import sys,json;d=json.load(sys.stdin);print(f'Health tasks: {d[\"summary\"]}')"
```

**Step 2: 浏览器手动验证 5 个 Tab 渲染正常**

**Step 3: Commit**

```bash
git add src/web_ui.py templates/ requirements-web.txt
git commit -m "feat: add local web console with 5 management modules"
```

---

## 完成后

启动命令：
```bash
pip install -r requirements-web.txt
python -m uvicorn src.web_ui:app --reload --port 8080
```

访问: `http://localhost:8080`

