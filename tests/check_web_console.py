"""Render the real console with isolated demo API responses; never touch user data."""
from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import fitz
import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "ui-checks"
ASSETS = ROOT / "docs" / "assets"
REPORT_PATH = "2026-11-25/demo_ai_pm_20261125_0900.md"
REPORT = """# 岗位推荐 · AI 产品经理

> 演示报告 · 下列内容仅用于展示界面

## 本次搜索

覆盖 4 家公司，推荐 8 个岗位。优先查看职责与项目经历直接相关的机会。

| 推荐岗位 | 匹配分数 | 投递建议 |
| --- | --- | --- |
| 示例公司 A — AI 产品经理 | 91 | 优先投递 |
| 示例公司 B — Agent 产品经理 | 88 | 建议投递 |
| 示例公司 C — ToB 产品经理 | 85 | 建议投递 |

### 匹配依据

- **JD 证据**：需求分析、产品规划、项目推进与效果评估。
- **简历证据**：AI 产品落地与 ToB 项目协作经历。
- **风险提示**：投递前确认岗位年限与具体业务范围。

岗位链接：[https://example.com/careers/ai-product](https://example.com/careers/ai-product)

## 投递准备

准备 `项目经历` 与成果指标。

```text
项目背景 → 关键行动 → 结果与证据
```
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main(screenshots=False):
    OUT.mkdir(parents=True, exist_ok=True)
    resumes = [
        dict(resume_id="demo-ai", filename="demo-ai-product.md", display_name="AI 产品经理", format="md", size=42000, modified="2026-11-25T09:00:00", enabled=True, keywords=["AI 产品", "Agent", "ToB"], job_types=["社招"]),
        dict(resume_id="demo-data", filename="demo-data-analyst.pdf", display_name="数据分析师", format="pdf", size=103000, modified="2026-11-24T09:00:00", enabled=True, keywords=["数据分析", "商业分析", "SQL"], job_types=["校招"]),
    ]
    config = dict(profiles=[dict(name="demo-ai-profile", resume="resumes/demo-ai-product.md", enabled=True),dict(name="demo-data-profile",resume="resumes/demo-data-analyst.pdf",enabled=True)], feishu=dict(enabled=False), schedule=dict(enabled=False, time="09:00", job_type="social", keyword="AI 产品经理", feishu_push=True, git_push=False), feishu_meta={key:dict(label=label, desc=desc) for key,label,desc in [
        ("app_id", "应用 ID", "飞书开放平台 → 应用凭证"),
        ("app_secret", "应用密钥", "飞书开放平台 → 应用凭证"),
        ("wiki_node_token", "知识库节点", "用于归档巡检报告的知识库节点"),
        ("bitable_token", "多维表格 Token", "用于同步岗位追踪记录"),
        ("bitable_table_id", "数据表 ID", "岗位追踪数据表"),
    ]})
    companies = [
        dict(id="tencent", name="腾讯", enabled=True, strategy_type="config_intercept", urls=dict(social="https://careers.tencent.com/",campus="https://join.qq.com/"), note="覆盖社招与校招，按求职意向筛选岗位。"),
        dict(id="bytedance", name="字节跳动", enabled=True, strategy_type="custom_python", urls=dict(social="https://jobs.bytedance.com/",internship="https://jobs.bytedance.com/campus/"), note="按岗位类型、关键词和发布时间抓取。"),
        dict(id="alibaba", name="阿里巴巴", enabled=True, strategy_type="config_dom", urls=dict(social="https://talent.alibaba.com/",campus="https://campus.alibaba.com/"), note="页面策略待验证，可在策略健康中查看。"),
        dict(id="xiaomi", name="小米", enabled=False, strategy_type="config_intercept", urls=dict(social="https://hr.xiaomi.com/"), note="暂时停用；启用后加入下一轮巡检。"),
    ]
    health = dict(summary=dict(total=2,pending=1,blocked=1,failed=0), tasks=[
        dict(company_id="alibaba",company_name="阿里巴巴",status="pending",reason_label="页面结构变化，等待策略复核",created_at="2026-11-25 09:05"),
        dict(company_id="xiaomi",company_name="小米",status="blocked",reason_label="需要人工确认访问状态",created_at="2026-11-25 09:08"),
    ])
    reports = [dict(profile="demo-ai-profile",relpath=REPORT_PATH,generated="2026-11-25 09:00",job_count=8,top_score=91,size=28000,duration_str="6m 12s"),dict(profile="demo-ai-profile",relpath="2026-11-24/demo_ai_pm_20261124_0900.md",generated="2026-11-24 09:00",job_count=5,top_score=88,size=22000,duration_str="5m 48s")]
    reports.extend([dict(profile="demo-ai-profile",relpath="2026-11-23/demo_ai.md",generated="2026-11-23 09:00",job_type="social",job_count=3,top_score=86,size=15000),dict(profile="demo-data-profile",relpath="2026-11-25/demo_data.md",generated="2026-11-25 11:30",job_type="campus",job_count=4,top_score=84,size=16000)])
    for report in reports:report.setdefault("job_type","social")
    pdf = fitz.open()
    pdf.new_page().insert_text((60,70), "Demo Resume - Data Analyst\nSkills: SQL, Python, Analytics", fontsize=16)
    pdf_bytes = pdf.tobytes()
    pdf.close()
    calls = []
    held_reports={"enabled":False,"routes":[]}

    def api_route(route):
        request = route.request
        path = unquote(urlsplit(request.url).path)
        body = request.post_data_json if request.post_data and "application/json" in request.headers.get("content-type","") else {}
        calls.append(dict(method=request.method,path=path,body=body))
        if path == "/api/config":
            if request.method == "PUT":
                for key,value in body.items():
                    if isinstance(value,dict):
                        config.setdefault(key,{}).update(value)
            data=config
        elif path == "/api/resumes/analyze":
            data=dict(ok=True,filename="uploaded.md")
        elif path == "/api/resumes/confirm":
            resume=dict(resume_id="demo-upload",filename=body["filename"],display_name=body["display_name"],format="md",size=40,enabled=True,modified="2026-11-25T12:00:00",keywords=body["keywords"],job_types=body["job_types"])
            resumes.append(resume);data=resume
        elif path == "/api/resumes":
            data=dict(resumes=resumes,unsupported_files=[])
        elif path.endswith("/intent"):
            resume=next(r for r in resumes if r["filename"] in path)
            resume.update(body)
            data=resume
        elif path == "/api/reports":
            data=reports
        elif path.startswith("/api/reports/"):
            if held_reports["enabled"]:held_reports["routes"].append(route);return
            route.fulfill(status=200,content_type="text/markdown; charset=utf-8",body=REPORT.replace("AI 产品经理","数据分析师") if "demo_data" in path else REPORT)
            return
        elif path == "/api/companies":
            data=companies
        elif path.startswith("/api/companies/") and path.endswith("/test"):
            data=dict(ok=True,jobs_count=3)
        elif path.startswith("/api/health/") and request.method=="DELETE":
            data=dict(ok=True)
        elif path.startswith("/api/companies/"):
            company=next(c for c in companies if c["id"] == path.rsplit("/",1)[-1])
            company.update(body)
            data=company
        elif path == "/api/health":
            data=health
        elif path == "/api/run":
            data=dict(status="launched",pid=1234,run_id="demo")
        else:
            raise AssertionError(f"Unexpected API: {request.method} {path}")
        route.fulfill(status=200,content_type="application/json; charset=utf-8",body=json.dumps(data,ensure_ascii=False))

    def assert_fits(page, context):
        overflow=page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not overflow, (context,page.evaluate("({width:innerWidth,actual:document.documentElement.scrollWidth})"))

    server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(ROOT / "templates")))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport=dict(width=1440,height=960),device_scale_factor=1)
            errors=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.route("**/api/**",api_route)
            page.route(f"http://127.0.0.1:{server.server_port}/resumes/**",lambda route:route.fulfill(status=200,content_type="application/pdf" if route.request.url.endswith(".pdf") else "text/markdown; charset=utf-8",body=pdf_bytes if route.request.url.endswith(".pdf") else "# Demo resume\n\nAI product management and analytics."))
            # Serve the existing external dependencies from an in-memory cache.
            for url in ["https://cdn.jsdelivr.net/npm/marked/marked.min.js","https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js","https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js"]:
                response=requests.get(url,timeout=25)
                response.raise_for_status()
                page.route(url,lambda route,_request,body=response.content:route.fulfill(status=200,content_type="text/javascript",body=body))
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html",wait_until="networkidle")
            screenshot_dir=ASSETS if screenshots else OUT
            def tab(name):
                page.locator(f'[data-tab="{name}"]').click()
                if name=='tasks':expect(page.locator('.object-header h1')).to_be_visible()
                elif name=='strategy':expect(page.locator('#coSearch')).to_be_visible()
                elif name=='health':expect(page.locator('#batchBtn')).to_be_visible()
                elif name=='feishu':expect(page.locator('#fAppId')).to_be_visible()
                elif name=='schedule':expect(page.locator('#scKeyword')).to_be_visible()

            expect(page.locator('.nav-item:visible')).to_have_count(5)
            expect(page.locator('.resume-option')).to_have_count(2)
            expect(page.locator('.object-header h1')).to_have_text('AI 产品经理')
            expect(page.locator('.report-card')).to_have_count(3)
            assert_fits(page,'desktop tasks')
            page.mouse.move(1400,930)
            page.screenshot(path=str(screenshot_dir/'web-console-resumes-reports.png'))
            page.locator('[data-resume-id="demo-data"]').click()
            expect(page.locator('.object-header h1')).to_have_text('数据分析师')
            expect(page.locator('.intent-tags')).to_contain_text('SQL')
            expect(page.locator('.intent-tags')).not_to_contain_text('Agent')
            expect(page.locator('.report-card')).to_have_count(1)
            expect(page.locator('.metric-count')).to_have_text('4')
            page.get_by_role('button',name='修改意向').click()
            expect(page.locator('#intentKw')).to_have_value('数据分析, 商业分析, SQL')
            page.locator('#intentKw').fill('数据分析, SQL, Python')
            page.locator('.modal-overlay').get_by_role('button',name='保存',exact=True).click()
            expect(page.locator('.intent-tags')).to_contain_text('Python')
            assert any(c['path']=='/api/resumes/demo-data-analyst.pdf/intent' and c['body'].get('keywords')==['数据分析','SQL','Python'] for c in calls)
            page.locator('[data-resume-id="demo-ai"]').click()
            expect(page.locator('.intent-tags')).not_to_contain_text('Python')
            expect(page.locator('.report-card')).to_have_count(3)

            # Report content is the original Markdown, in a centered modal.
            page.locator('.report-card').first.click()
            expect(page.locator('.report-modal .markdown-body table')).to_be_visible()
            expect(page.locator('.report-modal pre code')).to_be_visible()
            link=page.locator('.report-modal .markdown-body a').first
            assert link.inner_text()==link.get_attribute('href')
            assert page.locator('.report-modal td').first.evaluate('el=>getComputedStyle(el).color')=='rgb(240, 237, 229)'
            box=page.locator('.report-modal').bounding_box()
            assert abs(box['x']+box['width']/2-720)<2,box
            page.screenshot(path=str(OUT/'report-modal.png'))
            page.keyboard.press('Escape')
            expect(page.locator('.report-modal')).to_have_count(0)
            assert page.evaluate('document.activeElement.matches(".report-card")')

            # Closing before an older response arrives must not replace another resume's view.
            held_reports['enabled']=True
            page.locator('.report-card').first.click()
            expect(page.locator('.report-modal')).to_be_visible()
            page.keyboard.press('Escape')
            page.locator('[data-resume-id="demo-data"]').click()
            for route in held_reports['routes']:
                route.fulfill(status=200,content_type='text/markdown; charset=utf-8',body=REPORT)
            held_reports['enabled']=False
            expect(page.locator('.object-header h1')).to_have_text('数据分析师')
            expect(page.locator('.report-card')).to_have_count(1)
            expect(page.locator('.report-modal')).to_have_count(0)
            page.locator('[data-resume-id="demo-ai"]').click()

            # The unchanged launch endpoint gets exactly one selected-resume request.
            before=sum(c['path']=='/api/run' for c in calls)
            page.evaluate('runInspect();runInspect()')
            expect(page.locator('.toast').last).to_contain_text('任务已启动')
            assert sum(c['path']=='/api/run' for c in calls)==before+1
            assert next(c for c in reversed(calls) if c['path']=='/api/run')['body']==dict(resume_id='demo-ai')

            page.get_by_role('button',name='管理简历',exact=True).click()
            page.locator('.modal-overlay').get_by_role('button',name='编辑意向',exact=True).first.click()
            expect(page.locator('#intentKw')).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.locator('.modal-overlay')).to_have_count(0)
            assert page.evaluate('document.body.style.overflow')!='hidden'
            page.get_by_role('button',name='管理简历',exact=True).click()
            page.locator('.modal-overlay .toggle-track').first.click()
            expect(page.locator('.resume-option').first).to_contain_text('已暂停')
            page.locator('.modal-overlay .toggle-track').first.click()
            page.locator('.modal-overlay').get_by_role('button',name='预览',exact=True).first.click()
            expect(page.locator('.modal-overlay').last.locator('.markdown-body h1')).to_have_text('Demo resume')
            page.keyboard.press('Escape')
            page.locator('.modal-overlay').get_by_role('button',name='预览',exact=True).nth(1).click()
            expect(page.locator('#pv img')).to_be_visible(timeout=20000)
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            expect(page.locator('.modal-overlay')).to_have_count(0)

            tab('strategy')
            expect(page.locator('.company-row')).to_have_count(4)
            page.wait_for_timeout(2700)
            page.mouse.move(1400,930)
            page.screenshot(path=str(screenshot_dir/'web-console-company-management.png'))
            page.locator('#coSearch').fill('腾讯')
            expect(page.locator('.company-row')).to_have_count(1)
            page.locator('#coStatus').select_option('disabled')
            expect(page.locator('.company-row')).to_have_count(0)
            page.locator('#coStatus').select_option('all')
            expect(page.locator('.company-row')).to_have_count(1)
            page.locator('#coSearch').fill('')
            page.locator('[data-cid="tencent"] .toggle-track').click()
            expect(page.locator('[data-cid="tencent"]')).to_have_class('company-row company-disabled')
            page.locator('[data-cid="tencent"] .toggle-track').click()
            page.locator('[data-cid="tencent"]').get_by_role('button',name='编辑',exact=True).click()
            expect(page.locator('#eName')).to_have_value('腾讯')
            page.locator('.modal-overlay').get_by_role('button',name='取消',exact=True).click()
            page.locator('[data-cid="tencent"]').get_by_role('button',name='测试',exact=True).click()
            expect(page.locator('#test-tencent')).to_contain_text('3岗')
            tab('health')
            page.get_by_role('button',name='全选',exact=True).click()
            expect(page.locator('#batchBtn')).to_have_text('策略巡检 (2)')
            page.get_by_role('button',name='取消',exact=True).click()
            expect(page.locator('#batchBtn')).to_be_disabled()
            tab('feishu')
            page.locator('.toggle-track').click()
            expect(page.locator('#content')).to_contain_text('推送已开启')
            page.locator('#fAppId').fill('demo-app')
            page.get_by_role('button',name='保存配置',exact=True).click()
            assert any(c['path']=='/api/config' and c['body'].get('feishu',{}).get('app_id')=='demo-app' for c in calls)
            tab('schedule')
            page.locator('#scJobType').select_option('campus')
            page.locator('#scKeyword').fill('数据分析')
            page.locator('#scKeyword').press('Tab')
            expect(page.locator('.toast').last).to_have_text('已保存')
            assert any(c['body'].get('schedule',{}).get('keyword')=='数据分析' for c in calls)

            # Real upload/confirm UI, isolated fixture responses and no private files.
            tab('tasks')
            page.get_by_role('button',name='+ 添加简历',exact=True).click()
            page.locator('#resumeInput').set_input_files(dict(name='uploaded.md',mimeType='text/markdown',buffer=b'# Demo upload'))
            expect(page.locator('#cfmKw')).to_be_visible()
            page.locator('#cfmKw').fill('AI 产品')
            page.locator('#cfmBtn').click()
            expect(page.locator('.object-header h1')).to_have_text('uploaded')
            expect(page.locator('.report-card')).to_have_count(0)
            expect(page.locator('.object-meta')).to_contain_text('待 Agent 建档')
            page.locator('[data-resume-id="demo-ai"]').click()

            for width in (1440,1024,768,390,320):
                print(f'Checking {width}px',flush=True)
                page.set_viewport_size(dict(width=width,height=960 if width>768 else 844))
                for name in ('tasks','strategy','health','feishu','schedule'):
                    tab(name)
                    expect(page.locator('.nav-item:visible')).to_have_count(5)
                    assert_fits(page,f'{width}px {name}')
                    if width==390:page.screenshot(path=str(OUT/f'mobile-{name}.png'),full_page=True)
                tab('tasks')
                page.locator('.report-card').first.click()
                expect(page.locator('.report-modal .markdown-body table')).to_be_visible()
                box=page.locator('.report-modal').bounding_box()
                assert abs(box['x']+box['width']/2-width/2)<2,(width,box)
                assert page.locator('.report-modal .modal-body').evaluate('el=>el.scrollWidth<=el.clientWidth'),width
                assert_fits(page,f'{width}px report')
                page.keyboard.press('Escape')
            assert not errors,errors
            result=dict(status='passed',widths=[1440,1024,768,390,320],tabs=5,api_calls=len(calls),script_errors=errors)
            (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False))
            browser.close()

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots",action="store_true",help="Refresh the two README screenshots with demo data")
    main(screenshots=parser.parse_args().screenshots)
