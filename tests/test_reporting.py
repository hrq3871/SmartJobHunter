from pathlib import Path

from src.reporting import render_full_crawl_audit, validate_original_url
from src.run_records import attach_evaluation, create_run_records, update_record_stage


def _record_with_evaluation(url: str):
    records = create_run_records(
        [
            {
                "id": "job-1",
                "hash": "hash-1",
                "title": "AI 产品经理",
                "company": "示例公司",
                "location": "北京",
                "category": "产品",
                "duty": "负责 Agent 产品规划与落地",
                "requirement": "具备 ToB 产品和大模型应用经验",
                "publish_time": "2026-06-20",
                "work_years": "3 年",
                "url": url,
                "source": "example",
            }
        ],
        run_id="run-report",
    )
    update_record_stage(records, {records[0]["run_record_id"]}, "recommended")
    attach_evaluation(
        records[0],
        {
            "score": 88,
            "recommendation": "strong_apply",
            "semantic_filter": {
                "should_keep": True,
                "match_reasons": ["核心职责包含 Agent 产品规划"],
                "evidence": {"domain": ["Agent", "大模型"]},
                "concerns": ["行业经验需要确认"],
            },
            "match_analysis": {
                "strong_matches": [
                    {
                        "requirement": "ToB 产品经验",
                        "candidate_evidence": "简历包含企业级产品项目",
                    }
                ],
                "potential_matches": [],
                "gaps": [{"requirement": "行业经验", "suggestion": "面试确认"}],
            },
            "scoring_breakdown": {
                "target_role_fit": 25,
                "core_responsibility_fit": 10,
                "domain_fit": 20,
                "resume_evidence": 20,
                "preference_fit": 8,
                "evidence_quality": 8,
                "risk_penalty": 3,
            },
            "risk_warning": "行业经验需要确认",
        },
        source="agent",
    )
    return records[0]


def test_render_full_crawl_audit_uses_confirmed_structure():
    markdown = render_full_crawl_audit([_record_with_evaluation("https://jobs.example.com/1")])

    expected_labels = [
        "公司",
        "岗位名称",
        "地点",
        "类别",
        "完整职责",
        "完整任职要求",
        "发布时间",
        "工作年限",
        "原始链接",
        "处理状态",
        "判断来源",
        "最终结论",
    ]
    for label in expected_labels:
        assert f"| {label} |" in markdown
    assert "## 全量抓取与判断记录" in markdown
    assert "#### 语义判断及引用证据" in markdown
    assert "核心职责包含 Agent 产品规划" in markdown
    assert "简历包含企业级产品项目" in markdown
    assert "#### 评分拆解" in markdown
    assert "target_role_fit" in markdown
    assert "88" in markdown


def test_original_url_is_never_truncated_and_remains_clickable():
    url = (
        "https://jobs.example.com/detail/1234567890"
        "?keyword=AI%20Product%20Manager&source=official&campaign=very-long-value-abcdef"
    )
    markdown = render_full_crawl_audit([_record_with_evaluation(url)])

    assert f"[{url}]({url})" in markdown
    assert url in markdown
    assert "very-long-value-abcdef" in markdown
    assert validate_original_url(url) == (True, None)
    assert validate_original_url("https://jobs.example.com/detail/123...")[0] is False
    assert validate_original_url("javascript:alert(1)")[0] is False


def test_report_prompt_does_not_teach_truncated_or_label_only_links():
    prompt = Path(".claude/skills/jobhunter/prompts/report.md").read_text(encoding="utf-8")

    assert "(https://...)" not in prompt
    assert "[查看详情]" not in prompt
