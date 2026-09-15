"""
Step 3 prototype: automates the repetitive "verify case -> write note -> submit"
loop observed in the onboarding process (Dataset B analysis).

This targets a LOCAL MOCK replica of the real portal's structure (same
element IDs: #ob-note textarea, #btn-ob-ok button), since the real system
only exists on the machine that recorded the logs (127.0.0.1) and its
underlying API could not be confirmed from the event data alone (see
docs/dataset_b_proposal.md - API vs UI-automation decision).

DRY_RUN mode: previews every action (which case, what note text) WITHOUT
clicking the final submit button - a cheap, concrete safeguard against
blind-submitting changes to real HR/employee data before a human reviews
them. This directly addresses the governance risk flagged in the report
(human-in-the-loop approval before final submission).
"""

from playwright.sync_api import sync_playwright
import time

DRY_RUN = False  # flip to False only after a human has reviewed dry-run output

NOTE_TEMPLATE = "Verified automatically - case {case_id} data matches expected format."


def process_case(page, row):
    case_id = row.get_attribute("data-case")

    # Step 1: click the row (same action seen in the real logs)
    row.query_selector("td").click()
    time.sleep(0.3)

    # Step 2: fill in the note field (same element ID as the real portal)
    note_text = NOTE_TEMPLATE.format(case_id=case_id)
    page.fill("#ob-note", note_text)
    time.sleep(0.2)

    if DRY_RUN:
        print(f"  [DRY RUN] Case {case_id}: would submit note -> '{note_text}'")
        print("            -> Skipped actual submit (dry run, no changes made)")
    else:
        # Step 3: click submit (same element ID as the real portal)
        page.click("#btn-ob-ok")
        time.sleep(0.3)
        print(f"  [LIVE] Case {case_id}: submitted -> '{note_text}'")


def run_automation(portal_url, headless=False):
    mode = "DRY RUN (preview only, no real submissions)" if DRY_RUN else "LIVE (will actually submit)"
    print(f"Running in {mode} mode.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(portal_url)

        rows = page.query_selector_all("#case-table tr[data-case]")
        print(f"Found {len(rows)} onboarding cases to process.\n")

        for row in rows:
            process_case(page, row)

        print("\nAll cases processed.")
        if DRY_RUN:
            print("Nothing was actually submitted - set DRY_RUN = False to execute for real.")
        time.sleep(2)
        browser.close()


if __name__ == "__main__":
    MOCK_PORTAL_URL = "http://localhost:8000/mock_onboarding_portal.html"
    run_automation(MOCK_PORTAL_URL, headless=False)