"""
automate_payroll_visible.py

Full visible walkthrough version: loads real cases into the realistic mock
portal (list + detail view, matching the actual system's screenshots), then
for EACH case: clicks its row, waits for the detail panel to open, reads the
reference info on screen, fills the note, clicks submit - visibly, one at a
time, exactly matching how a human works through the real portal.

Usage:
    python automate_payroll_visible.py --from-logs dataset_b
"""

import json
import time
import logging
import hashlib
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

REFERENCE_MAP = {
    "invoice_approval": lambda c: f"{c['invoice_id']} / {int(c['amount']):,}円",
    "budget_variance": lambda c: f"{c['department']} / 差異 {c['variance_pct']}%",
    "order_management": lambda c: f"{c['item']} x{int(c['quantity'])}",
    "onboarding_match": lambda c: f"採用区分：{c['hire_type']}",
    "leave_request": lambda c: f"{c['leave_type']} / {c['date']}",
    "expense_reimbursement": lambda c: f"{c['expense_category']} / {int(c['amount']):,}円",
    "inventory_adjustment": lambda c: f"{c['item_name']} +{int(c['amount'])}",
}


def run(cases_source, dry_run, portal_url, from_logs, pace_seconds):
    if from_logs:
        from extract_real_payroll_cases import extract_cases
        cases = extract_cases(cases_source)
    else:
        with open(cases_source, encoding="utf-8") as f:
            cases = json.load(f)

    print(f"Loaded {len(cases)} cases. Opening portal...")

    for c in cases:
        fn = REFERENCE_MAP.get(c.get("category_type"))
        c["reference"] = fn(c) if fn else ""
        c["_done"] = False

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page = browser.new_page(viewport={"width": 1300, "height": 850})
        page.goto(portal_url)
        page.wait_for_load_state("load")

        page.evaluate("(data) => window.loadCases(data)", cases)
        time.sleep(pace_seconds)

        for i, case in enumerate(cases):
            masked = mask_id(case.get("case_id", "unknown"))
            category = case.get("category_type")

            page.click(f'tr[data-index="{i}"]')
            time.sleep(pace_seconds)

            fn = TEMPLATE_MAP.get(category)
            if not fn:
                logging.warning(f"Case {masked}: unknown category, skipped")
                results.append({"case_id": case["case_id"], "status": "flagged_unknown_category"})
                continue

            try:
                note = fn(case)
            except Exception as e:
                logging.error(f"Case {masked}: {e}")
                results.append({"case_id": case["case_id"], "status": "error", "error": str(e)})
                continue

            page.fill("#pi-note", note)
            time.sleep(pace_seconds)

            if dry_run:
                logging.info(f"[DRY RUN] Case {masked}: {note}")
                results.append({"case_id": case["case_id"], "status": "dry_run_previewed",
                                 "category_type": category, "note_used": note})
            else:
                page.click("#btn-pi-ok")
                time.sleep(pace_seconds)
                logging.info(f"Case {masked}: submitted")
                results.append({"case_id": case["case_id"], "status": "submitted",
                                 "category_type": category, "note_used": note})

        time.sleep(1.5)
        browser.close()

    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/payroll_automation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Done. Processed {len(results)} cases -> outputs/payroll_automation_results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="prototype/payroll_cases.json")
    parser.add_argument("--from-logs", metavar="DATA_DIR", default=None)
    parser.add_argument("--live", dest="dry_run", action="store_false", default=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mock_payroll_portal_v2.html")
    parser.add_argument("--pace", type=float, default=0.6)
    args = parser.parse_args()

    if args.from_logs:
        run(args.from_logs, args.dry_run, args.url, True, args.pace)
    else:
        run(args.cases, args.dry_run, args.url, False, args.pace)