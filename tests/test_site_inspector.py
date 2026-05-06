#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.site_inspector import build_page_fingerprint, inspect_html_signals


def test_detect_login_required_from_html():
    result = inspect_html_signals("<html>请登录后查看职位</html>")

    assert "login_required" in result["signals"]


def test_generic_login_button_does_not_mark_job_page_as_login_required():
    result = inspect_html_signals(
        "<html><button class='loginBtn'>登录</button><div>职位列表</div></html>",
        "登录\n社会招聘\nAI产品经理 岗位 职位列表",
    )

    assert "job_like" in result["signals"]
    assert "login_required" not in result["signals"]


def test_hidden_login_script_does_not_mark_job_page_as_login_required():
    result = inspect_html_signals(
        "<html><script>const text='请登录'; const api='/user/mobile/login_status'</script></html>",
        "社招\n所有职位\n产品\n开启新的工作",
    )

    assert "login_required" not in result["signals"]


def test_detect_captcha_from_html():
    result = inspect_html_signals("<html>captcha 验证码</html>")

    assert "captcha" in result["signals"]


def test_detect_job_like_page_from_text():
    result = inspect_html_signals("<html>careers</html>", "AI产品经理 岗位 职位列表")

    assert "job_like" in result["signals"]


def test_fingerprint_changes_when_title_or_dom_changes():
    a = build_page_fingerprint("Jobs", "产品经理 北京")
    b = build_page_fingerprint("Careers", "暂无岗位")

    assert a != b
