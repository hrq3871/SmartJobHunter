#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.base_crawler import InterceptCrawler


class FakeElement:
    def __init__(self, visible=True, enabled=True):
        self.visible = visible
        self.enabled = enabled
        self.filled = None
        self.clicked = False
        self.pressed = None

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def click(self):
        self.clicked = True

    def fill(self, value):
        self.filled = value

    def press(self, value):
        self.pressed = value


class FakePage:
    def __init__(self):
        self.hidden_input = FakeElement(visible=False)
        self.visible_input = FakeElement(visible=True)
        self.search_button = FakeElement(visible=True)

    def query_selector_all(self, selector):
        if selector == 'input[placeholder*="搜索"]':
            return [self.hidden_input, self.visible_input]
        if selector == 'button[class*="search"]':
            return [self.search_button]
        return []

    def wait_for_timeout(self, _milliseconds):
        return None


def test_try_search_skips_hidden_inputs_and_uses_visible_one():
    crawler = InterceptCrawler({"api": {"pattern": "jobs", "data_path": "data"}})
    page = FakePage()

    searched = crawler._try_search(page, "AI产品经理")

    assert searched is True
    assert page.hidden_input.filled is None
    assert page.visible_input.filled == "AI产品经理"
    assert page.visible_input.pressed == "Enter"
    assert page.search_button.clicked is True


class FakeContext:
    def __init__(self):
        self.init_scripts = []

    def add_init_script(self, script):
        self.init_scripts.append(script)


class FakeBrowser:
    def __init__(self):
        self.context = FakeContext()
        self.context_kwargs = None

    def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        return self.context


class FakeChromium:
    def __init__(self):
        self.browser = FakeBrowser()
        self.launch_kwargs = None

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


def test_create_browser_uses_standard_context_without_stealth_overrides():
    crawler = InterceptCrawler({"api": {"pattern": "jobs", "data_path": "data"}})
    playwright = FakePlaywright()

    crawler.create_browser(playwright, headless=True)

    launch_text = repr(playwright.chromium.launch_kwargs)
    scripts = "\n".join(playwright.chromium.browser.context.init_scripts)
    assert "AutomationControlled" not in launch_text
    assert "navigator.webdriver" not in scripts
    assert "window.chrome" not in scripts
    assert "navigator.plugins" not in scripts
    assert "navigator.languages" not in scripts
