"""Deterministic, replayable browser interactions for public job pages."""

from __future__ import annotations

from typing import Any


SEARCH_INPUT_SELECTORS = [
    'input[placeholder*="搜索"]',
    'input[placeholder*="职位"]',
    'input[placeholder*="关键词"]',
    'input[type="text"]',
    ".search-input",
    "#search-input",
    '[class*="search"] input',
]

SEARCH_BUTTON_SELECTORS = [
    'button[class*="search"]',
    '[class*="search_btn"]',
    '[class*="search-button"]',
    'button:has-text("搜索")',
]


def click_generic_search_button(page: Any, actions: list[dict] | None = None) -> bool:
    """Click the first visible, enabled search button."""
    action_log = actions if actions is not None else []
    for selector in SEARCH_BUTTON_SELECTORS:
        try:
            for element in page.query_selector_all(selector):
                if element and element.is_visible() and element.is_enabled():
                    element.click()
                    action_log.append({"action": "click", "selector": selector})
                    return True
        except Exception:
            continue
    return False


def perform_generic_search(page: Any, keyword: str) -> list[dict]:
    """Run stable generic search interactions and return an action trace."""
    actions: list[dict] = []
    for selector in SEARCH_INPUT_SELECTORS:
        try:
            for element in page.query_selector_all(selector):
                if not element or not element.is_visible() or not element.is_enabled():
                    continue
                element.click()
                actions.append({"action": "click", "selector": selector})
                page.wait_for_timeout(300)
                element.fill(keyword)
                actions.append({"action": "fill", "selector": selector, "value": keyword})
                page.wait_for_timeout(300)
                element.press("Enter")
                actions.append({"action": "press", "selector": selector, "key": "Enter"})
                click_generic_search_button(page, actions)
                return actions
        except Exception:
            continue
    return actions
