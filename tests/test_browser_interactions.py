from src.browser_interactions import perform_generic_search


class Element:
    def __init__(self, visible=True, enabled=True):
        self.visible = visible
        self.enabled = enabled
        self.value = None
        self.clicked = False
        self.key = None

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def click(self):
        self.clicked = True

    def fill(self, value):
        self.value = value

    def press(self, key):
        self.key = key


class Page:
    def __init__(self):
        self.search = Element()
        self.button = Element()

    def query_selector_all(self, selector):
        if selector == 'input[placeholder*="搜索"]':
            return [self.search]
        if selector == 'button[class*="search"]':
            return [self.button]
        return []

    def wait_for_timeout(self, _milliseconds):
        return None


def test_generic_search_returns_replayable_action_trace():
    page = Page()

    actions = perform_generic_search(page, "AI产品经理")

    assert page.search.value == "AI产品经理"
    assert page.search.key == "Enter"
    assert page.button.clicked is True
    assert [item["action"] for item in actions] == ["click", "fill", "press", "click"]
    assert actions[1]["value"] == "AI产品经理"

