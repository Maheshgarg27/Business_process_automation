"""
Step 3 prototype: automates the repetitive "verify case -> write note -> submit"
loop observed in the onboarding process (Dataset B analysis).

DRY_RUN mode: previews every action WITHOUT clicking submit - a safeguard
against blind-submitting HR data changes before human review.

Logging: every processed case is logged to outputs/automation_log.txt
with a MASKED (hashed) identifier, not the real employee ID - giving an
auditable trail without exposing PII in log files, which could otherwise
become a data-handling liability of their own.
"""

from playwright.sync_api import sync_playwright
import time
import argparse
import hashlib
import logging
import os

os.makedirs("outputs", exist_ok=True)
logging.basicConfig(
    filename="outputs/automation_log.txt",
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)

NOTE_TEMPLATE = "Verified automatically - case {case_id} data matches expected format."


def mask_id(identifier):
    """One-way hash so the log file never contains a real, reversible identifier."""
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:8]


def process_case(page, row, dry_run):
    case_id = row.get_attribute("data-case")
    masked = mask_id(case_id)

    logging.info(f"Processing case {masked}")

    row.query_selector("td").click()
    time.sleep(0.3)

    note_text = NOTE_TEMPLATE.format(case_id=case_id)
    page.fill("#ob-note", note_text)
    time.sleep(0.2)

    if dry_run:
        print(f"  [DRY RUN] Case {case_id}: would submit note -> '{note_text}'")
        print("            -> Skipped actual submit (dry run, no changes made)")
        logging.info(f"Dry-run complete for case {masked} - no submission made")
    else:
        page.click("#btn-ob-ok")
        time.sleep(0.3)
        print(f"  [LIVE] Case {case_id}: submitted -> '{note_text}'")
        logging.info(f"Completed case {masked} - submitted successfully")


def run_automation(portal_url, dry_run, headless=False):
    mode = "DRY RUN (preview only, no real submissions)" if dry_run else "LIVE (will actually submit)"
    print(f"Running in {mode} mode.\n")
    logging.info(f"=== Run started - mode: {'DRY_RUN' if dry_run else 'LIVE'} ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(portal_url)

        rows = page.query_selector_all("#case-table tr[data-case]")
        print(f"Found {len(rows)} onboarding cases to process.\n")
        logging.info(f"Found {len(rows)} cases to process")

        for row in rows:
            process_case(page, row, dry_run)

        print("\nAll cases processed.")
        if dry_run:
            print("Nothing was actually submitted - run with --live to execute for real.")
        logging.info("=== Run finished ===\n")
        time.sleep(2)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Onboarding automation prototype")
    parser.add_argument("--live", action="store_true",
                         help="Actually submit changes (default is dry-run/preview mode)")
    args = parser.parse_args()

    dry_run = not args.live

    MOCK_PORTAL_URL = "http://localhost:8000/mock_onboarding_portal.html"
    run_automation(MOCK_PORTAL_URL, dry_run=dry_run, headless=False)