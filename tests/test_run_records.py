from copy import deepcopy

from src.run_records import (
    attach_evaluation,
    create_run_records,
    select_record_ids_for_jobs,
    update_record_stage,
)


def test_create_records_preserves_full_raw_job_and_duplicate_instances():
    url = "https://jobs.example.com/detail?id=123&keyword=AI%20PM&source=official"
    job = {
        "id": "123",
        "hash": "same-hash",
        "title": "AI 产品经理",
        "url": url,
        "job_type": "social",
        "product": "Agent",
        "bg": "企业服务",
        "custom_field": {"nested": ["kept"]},
    }
    original = deepcopy(job)

    records = create_run_records([job, deepcopy(job)], run_id="run-001")

    assert len(records) == 2
    assert records[0]["run_record_id"] != records[1]["run_record_id"]
    assert records[0]["run_id"] == records[1]["run_id"] == "run-001"
    assert records[0]["raw_job"] == original
    assert records[0]["original_url"] == url
    job["custom_field"]["nested"].append("mutated")
    assert records[0]["raw_job"]["custom_field"] == {"nested": ["kept"]}


def test_stage_updates_do_not_remove_records_and_evaluation_source_is_explicit():
    records = create_run_records(
        [
            {"id": "1", "hash": "h1", "title": "A", "url": "https://example.com/a"},
            {"id": "2", "hash": "h2", "title": "B", "url": "https://example.com/b"},
        ],
        run_id="run-002",
    )
    first_id = records[0]["run_record_id"]

    update_record_stage(records, {first_id}, "time_filtered", "outside_time_window")
    attach_evaluation(
        records[0],
        {
            "score": 42,
            "recommendation": "skip",
            "semantic_filter": {"should_keep": False, "match_reasons": ["职责不匹配"]},
            "scoring_breakdown": {"target_role_fit": 5},
        },
        source="python_fallback",
    )

    assert len(records) == 2
    assert records[0]["processing"] == {
        "stage": "time_filtered",
        "reason": "outside_time_window",
    }
    assert records[0]["evaluation"]["source"] == "python_fallback"
    assert records[0]["evaluation"]["score"] == 42
    assert records[0]["evaluation"]["final_decision"] == "skip"
    assert records[1]["processing"]["stage"] == "crawled"


def test_select_record_ids_matches_duplicate_occurrences_without_empty_hash_collision():
    jobs = [
        {"company": "A", "title": "产品经理", "url": "https://a.example/1", "hash": ""},
        {"company": "A", "title": "产品经理", "url": "https://a.example/1", "hash": ""},
        {"company": "B", "title": "产品经理", "url": "https://b.example/2", "hash": ""},
    ]
    records = create_run_records(jobs, "run-003")

    selected = select_record_ids_for_jobs(records, [jobs[0], jobs[2]])

    assert selected == {"run-003:1", "run-003:3"}
