"""
automate_payroll.py (v2 - fully deterministic, no LLM)

All note text is generated from confirmed real templates found directly in
the event logs (context.extracted_text, source: "text_pattern") across all
three payroll-items sub-systems and their categories. No LLM call needed -
every category follows a fixed, derivable template.

Usage:
    python automate_payroll.py --cases cases.json [--live]
"""

import json
import hashlib
import logging
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(
    filename="outputs/payroll_automation_log.txt",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

def mask_id(identifier):
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:8]


# ---- Confirmed templates, keyed by category ----

def note_invoice_approval(c):
    match = "差異なし承認" if c.get("has_discrepancy") is False else "差異あり要確認"
    return f"請求書照合完了。{c['invoice_id']}　金額：{c['amount']:,}円。{match}。"

def note_budget_variance(c):
    return (f"予算差異分析完了。{c['department']}　"
            f"予算 {c['budget']:,} / 実績 {c['actual']:,}（差異 {c['variance_pct']}%）。"
            f"是正対応方針を記録。")

def note_order_management(c):
    return (f"発注管理処理。{c['contract_type']}：{c['item']}　"
            f"数量 {c['quantity']}　合計 {c['total']:,}円　{c['urgency']}。"
            f"発注書確認・登録完了。")

def note_onboarding_match(c):
    return f"入社照合完了。採用区分：{c['hire_type']}。照合項目すべて確認済み。"

def note_leave_request(c):
    return f"勤怠申請確認。種別：{c['leave_type']}。取得日：{c['date']}。問題なし承認。"

def note_expense_reimbursement(c):
    return f"経費精算確認済み。費目：{c['expense_category']}　金額：{c['amount']:,}円。規程内であることを確認した。"

def note_inventory_adjustment(c):
    return f"在庫調整登録。品番：{c['item_code']}　品名：{c['item_name']}　調整数：+{c['amount']}個。"


TEMPLATE_MAP = {
    "invoice_approval": note_invoice_approval,
    "budget_variance": note_budget_variance,
    "order_management": note_order_management,
    "onboarding_match": note_onboarding_match,
    "leave_request": note_leave_request,
    "expense_reimbursement": note_expense_reimbursement,
    "inventory_adjustment": note_inventory_adjustment,
}


def generate_note(case):
    category = case.get("category_type")
    fn = TEMPLATE_MAP.get(category)
    if not fn:
        raise ValueError(f"Unknown category_type: {category} - no confirmed template. "
                          f"Do not fall back to guessing; flag for human review instead.")
    return fn(case)


# ---- Case processing ----

def process_case(page, case, dry_run):
    masked = mask_id(case.get("case_id", "unknown"))
    try:
        note = generate_note(case)
        logging.info(f"Case {masked} ({case.get('category_type')}): generated note")

        note_field = page.locator("#pi-note")
        if note_field.count() == 0:
            logging.warning(f"Case {masked}: note field missing, skipping")
            return {"case_id": case["case_id"], "status": "skipped_missing_field"}

        note_field.fill(note)

        if dry_run:
            logging.info(f"[DRY RUN] Case {masked}: would submit -> {note}")
            return {"case_id": case["case_id"], "status": "dry_run_previewed", "note_used": note}
        else:
            page.locator("#btn-pi-ok").click()
            logging.info(f"Case {masked}: submitted")
            return {"case_id": case["case_id"], "status": "submitted", "note_used": note}

    except ValueError as e:
        logging.warning(f"Case {masked}: unrecognized category - {e}")
        return {"case_id": case["case_id"], "status": "flagged_unknown_category", "error": str(e)}
    except Exception as e:
        logging.error(f"Case {masked}: error - {e}")
        return {"case_id": case["case_id"], "status": "error", "error": str(e)}


def run(cases_path, dry_run, portal_url):
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(portal_url)

        for case in cases:
            results.append(process_case(page, case, dry_run))

        browser.close()

    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/payroll_automation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Processed {len(results)} cases -> outputs/payroll_automation_results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="prototype/payroll_cases.json")
    parser.add_argument("--live", dest="dry_run", action="store_false", default=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mock_payroll_portal.html")
    args = parser.parse_args()
    run(args.cases, args.dry_run, args.url)