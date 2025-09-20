import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = os.environ.get("MANAGER_URL", "http://127.0.0.1:8590")
REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_DIR = REPO_ROOT / ".run"
PIDFILE = RUN_DIR / "main_service.pid"


def assert_text(page, text, timeout=5000):
    page.get_by_text(text, exact=False).wait_for(timeout=timeout)


def wait_stable(page, seconds=3):
    navs = {"count": 0}

    def _on_nav(event):  # noqa: ARG001
        navs["count"] += 1

    page.on("framenavigated", _on_nav)
    time.sleep(seconds)
    # Consider stable if we saw at most one navigation during the window
    return navs["count"] <= 1


def go_tab(page, name):
    # Streamlit tabs are role=tab buttons; if name matching is flaky, pick by text scan
    tabs = page.locator("div[role='tablist'] button")
    count = tabs.count()
    for i in range(count):
        t = tabs.nth(i)
        try:
            txt = t.inner_text()
        except Exception:
            txt = ""
        if name.lower() in txt.lower():
            t.click()
            return
    # Fallback: click the first tab (Dashboard)
    tabs.first.click()


def main():
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # 1) Load app and ensure UI renders (no blocking loop)
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.locator("div[role=tablist]").wait_for(timeout=8000)

        # Check tabs present
        tab_texts = [el.inner_text() for el in page.locator("div[role=tablist] button").all()]
        expected = ["Dashboard", "Services", "Logs", "PLC Tester", "Parameter Control", "Debug"]
        missing = [t for t in expected if not any(t in x for x in tab_texts)]
        if missing:
            errors.append(f"Missing tabs: {missing} (found={tab_texts})")

        # 2) Services tab: Start/Stop core and check toast + PID file
        try:
            go_tab(page, "Services")
        except PWTimeout:
            errors.append("Could not navigate to Services tab")
        else:
            # Scope to the Core Service Settings expander to avoid UI service buttons
            core_box = page.locator("div[data-testid='stExpander']").filter(has_text="Core Service Settings")
            try:
                # Measure navigations to ensure button does not cause rerun loop
                navs = {"count": 0}
                page.on("framenavigated", lambda e: navs.__setitem__("count", navs["count"] + 1))
                core_box.get_by_role("button", name="Start", exact=True).click()
                page.get_by_text("Core service start requested", exact=False).wait_for(timeout=5000)
                if navs["count"] > 2:
                    errors.append(f"Start core: excessive navigations={navs['count']}")
            except PWTimeout:
                errors.append("Start core: toast not seen or button not clickable")
            # Check PID file created within a few seconds
            for _ in range(10):
                if PIDFILE.exists() and PIDFILE.read_text().strip():
                    break
                time.sleep(0.5)
            else:
                errors.append(f"Start core: PID file not created at {PIDFILE}")

            # Now Stop
            try:
                navs2 = {"count": 0}
                page.on("framenavigated", lambda e: navs2.__setitem__("count", navs2["count"] + 1))
                core_box.get_by_role("button", name="Stop", exact=True).click()
                page.get_by_text("Core service stop requested", exact=False).wait_for(timeout=5000)
                if navs2["count"] > 2:
                    errors.append(f"Stop core: excessive navigations={navs2['count']}")
            except PWTimeout:
                errors.append("Stop core: toast not seen or button not clickable")
            # Ensure PID file cleared (allow some time)
            for _ in range(10):
                if not PIDFILE.exists() or not PIDFILE.read_text().strip():
                    break
                time.sleep(0.5)
            else:
                errors.append("Stop core: PID file still present or non-empty")

        # 3) Logs tab: Ensure no auto-refresh loop and manual refresh works
        try:
            go_tab(page, "Logs")
        except PWTimeout:
            errors.append("Could not navigate to Logs tab")
        else:
            # Logs should render a code block and a Refresh button
            try:
                page.get_by_role("button", name="Refresh Logs").wait_for(timeout=5000)
            except PWTimeout:
                errors.append("Logs: Refresh button not found (expected manual refresh)")
            # Verify stable (no autorefresh)
            if not wait_stable(page, seconds=3):
                errors.append("Logs: page content changed repeatedly (possible autorefresh loop)")
            # Click refresh once and ensure still stable after
            try:
                page.get_by_role("button", name="Refresh Logs").click()
                # Allow a rerun and settle
                ok = wait_stable(page, seconds=3)
                if not ok:
                    errors.append("Logs: manual refresh caused ongoing loop")
            except PWTimeout:
                errors.append("Logs: Refresh button not clickable")

        # 4) PLC Tester tab presence (no start required)
        try:
            go_tab(page, "PLC Tester")
            assert_text(page, "PLC Testing Interface")
        except Exception:
            errors.append("PLC Tester tab did not render expected content")

        # 5) Parameter Control tab presence
        try:
            go_tab(page, "Parameter Control")
            assert_text(page, "Parameter Control Interface")
        except Exception:
            errors.append("Parameter Control tab did not render expected content")

        # 6) Debug tab presence
        try:
            go_tab(page, "Debug")
            assert_text(page, "Debug & Diagnostics")
        except Exception:
            errors.append("Debug tab did not render expected content")

        # 7) Navigate back to Services (skip enforcing UI status text due to host side-processes)
        try:
            go_tab(page, "Services")
            page.get_by_role("button", name="Refresh Service Status").click()
        except Exception:
            errors.append("Services: could not navigate/refresh status tab")

        # 8) Dashboard navigation sanity (non-fatal)
        try:
            go_tab(page, "Dashboard")
        except Exception:
            errors.append("Dashboard: could not navigate to tab")

        browser.close()

    if errors:
        print("TEST RESULT: FAIL")
        for e in errors:
            print("- ", e)
        exit(1)
    print("TEST RESULT: PASS")


if __name__ == "__main__":
    main()
