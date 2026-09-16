"""
automate_payroll_excel.py

Company-facing version: takes an Excel spreadsheet of payroll cases as input,
processes each row (generates the correct note, submits it via the portal),
and writes the result directly back into the same spreadsheet.

Expected input columns (one row per case):
    case_id | category_type | <fields specific to that category, e.g. invoice_id, amount, department, ...>

Usage:
    python automate_payroll_excel.py --input cases.xlsx --dry-run
"""

import argparse
import logging
import hashlib
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(
    filename="outputs/payroll_automation_log.txt",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

def mask_id(identifier):
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:8]


# ---- Same confirmed templates as before ----

def note_invoice_approval(c):
    match = "差異なし承認" if not c.get("has_discrepancy") else "差異あり要確認"
    return f"請求書照合完了。{c['invoice_id']}　金額：{int(c['amount']):,}円。{match}。"

def note_budget_variance(c):
    return (f"予算差異分析完了。{c['department']}　予算 {int(c['budget']):,} / "
            f"実績 {int(c['actual']):,}（差異 {c['variance_pct']}%）。是正対応方針を記録。")

def note_order_management(c):
    return (f"発注管理処理。{c['contract_type']}：{c['item']}　数量 {int(c['quantity'])}　"
            f"合計 {int(c['total']):,}円　{c['urgency']}。発注書確認・登録完了。")

def note_onboarding_match(c):
    return f"入社照合完了。採用区分：{c['hire_type']}。照合項目すべて確認済み。"

def note_leave_request(c):
    return f"勤怠申請確認。種別：{c['leave_type']}。取得日：{c['date']}。問題なし承認。"

def note_expense_reimbursement(c):
    return f"経費精算確認済み。費目：{c['expense_category']}　金額：{int(c['amount']):,}円。規程内であることを確認した。"

def note_inventory_adjustment(c):
    return f"在庫調整登録。品番：{c['item_code']}　品名：{c['item_name']}　調整数：+{int(c['amount'])}個。"

TEMPLATE_MAP = {
    "invoice_approval": note_invoice_approval,
    "budget_variance": note_budget_variance,
    "order_management": note_order_management,
    "onboarding_match": note_onboarding_match,
    "leave_request": note_leave_request,
    "expense_reimbursement": note_expense_reimbursement,
    "inventory_adjustment": note_inventory_adjustment,
}


def process_row(page, row, dry_run):
    case = row.to_dict()
    masked = mask_id(case.get("case_id", "unknown"))
    category = case.get("category_type")

    fn = TEMPLATE_MAP.get(category)
    if not fn:
        logging.warning(f"Case {masked}: unknown category '{category}', flagged for human review")
        return "flagged_unknown_category", ""

    try:
        note = fn(case)
    except Exception as e:
        logging.error(f"Case {masked}: template error - {e}")
        return "error_missing_fields", str(e)

    note_field = page.locator("#pi-note")
    if note_field.count() == 0:
        logging.warning(f"Case {masked}: note field missing on page")
        return "skipped_missing_field", note

    note_field.fill(note)

    if dry_run:
        logging.info(f"[DRY RUN] Case {masked}: {note}")
        return "dry_run_previewed", note
    else:
        page.locator("#btn-pi-ok").click()
        logging.info(f"Case {masked}: submitted")
        return "submitted", note


def run(input_path, dry_run, portal_url):
    df = pd.read_excel(input_path)

    statuses = []
    notes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(portal_url)

        for _, row in df.iterrows():
            status, note = process_row(page, row, dry_run)
            statuses.append(status)
            notes.append(note)

        browser.close()

    df["status"] = statuses
    df["note_used"] = notes

    output_path = Path(input_path).with_stem(Path(input_path).stem + "_processed")
    df.to_excel(output_path, index=False)

    print(f"Processed {len(df)} rows -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to the input Excel file")
    parser.add_argument("--live", dest="dry_run", action="store_false", default=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mock_payroll_portal.html")
    args = parser.parse_args()
    run(args.input, args.dry_run, args.url)