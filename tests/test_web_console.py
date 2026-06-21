"""Comprehensive web console test suite."""
from playwright.sync_api import sync_playwright

def test_console():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1. Page load
        page.goto("http://localhost:8080", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        label = "Page loads"
        ok = len(errors) == 0
        results.append((label, ok, len(errors)))
        print(f"[{'PASS' if ok else 'FAIL'}] {label} ({len(errors)} errors)")

        # 2. Tasks tab renders
        sidebar = page.query_selector("[class*='sidebar']")
        label = "Tasks tab renders"
        ok = bool(sidebar)
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 3. Strategy tab
        page.query_selector("button[data-tab='strategy']").click()
        page.wait_for_timeout(2000)
        cards = page.query_selector_all(".company-card")
        label = "Strategy tab (70+ cards)"
        ok = len(cards) > 50
        results.append((label, ok, len(cards)))
        print(f"[{'PASS' if ok else 'FAIL'}] {label} ({len(cards)} cards)")

        # 4. Sub-tabs
        subs = page.query_selector_all(".sub-tab")
        label = "Sub-tabs exist (2)"
        ok = len(subs) == 2
        results.append((label, ok, len(subs)))
        print(f"[{'PASS' if ok else 'FAIL'}] {label} ({len(subs)})")

        # 5. Health panel
        subs[1].click()
        page.wait_for_timeout(1500)
        hs = page.query_selector_all(".hs-card")
        label = "Health panel stats"
        ok = len(hs) == 4
        results.append((label, ok, len(hs)))
        print(f"[{'PASS' if ok else 'FAIL'}] {label} ({len(hs)} cards)")

        # 6. Back to companies, test filters
        subs[0].click()
        page.wait_for_timeout(1000)
        s1 = page.query_selector("#coStatus")
        s2 = page.query_selector("#coHealth")
        label = "Filter dropdowns"
        ok = bool(s1) and bool(s2)
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 7. Modal
        btns = page.query_selector_all(".btn-primary")
        for b in btns:
            if "+" in (b.text_content() or ""):
                b.click()
                break
        page.wait_for_timeout(1500)
        modal = page.query_selector(".modal-overlay")
        label = "Add company modal"
        ok = bool(modal)
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if modal:
            close = page.query_selector(".modal-header button")
            if close:
                close.click()
                page.wait_for_timeout(500)

        # 8. Toggle
        tg = page.query_selector(".company-card:not(.disabled) .toggle")
        if tg:
            cb = tg.query_selector("input")
            was = cb.is_checked()
            tg.click()
            page.wait_for_timeout(1000)
            label = "Toggle switch"
            ok = cb.is_checked() != was
            results.append((label, ok, ""))
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 9. Action buttons
        tb = page.query_selector(".btn-outline")
        label = "Action buttons exist"
        ok = bool(tb)
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 10. Back to tasks tab, check search
        page.query_selector("button[data-tab='tasks']").click()
        page.wait_for_timeout(1500)
        search = page.query_selector("#coSearch")
        label = "Search input on tasks"
        ok = bool(search)
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 11. Mobile 375px
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(500)
        overflow = page.evaluate("() => document.body.scrollWidth > window.innerWidth + 10")
        label = "Mobile no overflow"
        ok = not overflow
        results.append((label, ok, ""))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 12. Tablet 768px
        page.goto("http://localhost:8080", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.set_viewport_size({"width": 768, "height": 1024})
        page.wait_for_timeout(500)
        page.query_selector("button[data-tab='tasks']").click()
        page.wait_for_timeout(1000)
        rl = page.query_selector(".report-layout")
        cols = page.evaluate("el => getComputedStyle(el).gridTemplateColumns", rl) if rl else ""
        label = "Tablet grid single col"
        ok = "1fr" in cols or rl is None
        results.append((label, ok, cols))
        print(f"[{'PASS' if ok else 'FAIL'}] {label} ({cols})")

        # Summary
        passed = sum(1 for _, p, _ in results if p)
        print(f"\n=== {passed}/{len(results)} passed ===")
        if errors:
            print(f"\nCONSOLE ERRORS ({len(errors)}):")
            for e in errors:
                print(f"  - {e[:200]}")

        browser.close()
        return passed == len(results)


if __name__ == "__main__":
    ok = test_console()
    exit(0 if ok else 1)
