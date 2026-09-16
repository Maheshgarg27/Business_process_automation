"""
extract_real_payroll_cases.py

Scans real event logs for confirmed submitted payroll notes (extracted_text,
source == "text_pattern"), parses them by category using the confirmed
templates, and outputs a cases.json file in the exact format automate_payroll.py
expects. This replaces hand-typed test cases with real data extracted directly
from the logs.

Usage:
    python extract_real_payroll_cases.py --data-dir dataset_b --out prototype/payroll_cases.json
"""

import json
import re
import glob
import hashlib
import argparse
from pathlib import Path

# Each pattern maps to (category_type, regex, field_transform)
PATTERNS = [
    (
        "invoice_approval",
        re.compile(r"請求書照合完了。(?P<invoice_id>[\w-]+)\s*金額：(?P<amount>[\d,]+)円。(?P<outcome>差異なし承認|差異あり要確認)。"),
        lambda m: {
            "invoice_id": m["invoice_id"],
            "amount": int(m["amount"].replace(",", "")),
            "has_discrepancy": m["outcome"] == "差異あり要確認",
        },
    ),
    (
        "budget_variance",
        re.compile(r"予算差異分析完了。(?P<department>\S+?)\s*予算\s*(?P<budget>[\d,]+)\s*/\s*実績\s*(?P<actual>[\d,]+)\s*[（(]差異\s*(?P<pct>[+\-\d.]+)%[）)]。"),
        lambda m: {
            "department": m["department"],
            "budget": int(m["budget"].replace(",", "")),
            "actual": int(m["actual"].replace(",", "")),
            "variance_pct": float(m["pct"]),
        },
    ),
    (
        "order_management",
        re.compile(r"発注管理処理。(?P<contract_type>[^：]+)：(?P<item>\S+?)\s*数量\s*(?P<quantity>\d+)\s*合計\s*(?P<total>[\d,]+)円\s*(?P<urgency>\S+?)。"),
        lambda m: {
            "contract_type": m["contract_type"],
            "item": m["item"],
            "quantity": int(m["quantity"]),
            "total": int(m["total"].replace(",", "")),
            "urgency": m["urgency"],
        },
    ),
    (
        "onboarding_match",
        re.compile(r"入社照合完了。採用区分：(?P<hire_type>\S+?)。"),
        lambda m: {"hire_type": m["hire_type"]},
    ),
    (
        "leave_request",
        re.compile(r"勤怠申請確認。種別：(?P<leave_type>\S+?)。取得日：(?P<date>[\d-]+)。"),
        lambda m: {"leave_type": m["leave_type"], "date": m["date"]},
    ),
    (
        "expense_reimbursement",
        re.compile(r"経費精算確認済み。費目：(?P<expense_category>\S+?)\s*金額：(?P<amount>[\d,]+)円。"),
        lambda m: {
            "expense_category": m["expense_category"],
            "amount": int(m["amount"].replace(",", "")),
        },
    ),
    (
        "inventory_adjustment",
        re.compile(r"在庫調整登録。品番：(?P<item_code>\S+?)\s*品名：(?P<item_name>\S+?)\s*調整数：\+(?P<amount>\d+)個。"),
        lambda m: {
            "item_code": m["item_code"],
            "item_name": m["item_name"],
            "amount": int(m["amount"]),
        },
    ),
]


def extract_cases(data_dir):
    cases = []
    seen = set()

    for session_dir in glob.glob(f"{data_dir}/ses_*"):
        for chunk in glob.glob(f"{session_dir}/chunk_*"):
            events_file = Path(chunk) / "events.jsonl"
            if not events_file.exists():
                continue
            with open(events_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    e = json.loads(line)
                    ctx = e.get("context", {}) or {}
                    text_obj = ctx.get("extracted_text")
                    if not text_obj or not isinstance(text_obj, dict):
                        continue
                    if text_obj.get("source") != "text_pattern":
                        continue
                    text = text_obj.get("text", "")

                    for category_type, pattern, transform in PATTERNS:
                        for m in pattern.finditer(text):
                            fields = transform(m.groupdict())
                            dedup_key = (category_type, tuple(sorted(fields.items())))
                            if dedup_key in seen:
                                continue
                            seen.add(dedup_key)

                            case_id_source = f"{category_type}-{fields}"
                            case_id = "AUTO-" + hashlib.sha256(case_id_source.encode()).hexdigest()[:10]

                            case = {"case_id": case_id, "category_type": category_type}
                            case.update(fields)
                            cases.append(case)

    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="dataset_b")
    parser.add_argument("--out", default="prototype/payroll_cases.json")
    args = parser.parse_args()

    cases = extract_cases(args.data_dir)

    print(f"Extracted {len(cases)} real cases across {len(set(c['category_type'] for c in cases))} categories")
    from collections import Counter
    counts = Counter(c["category_type"] for c in cases)
    for cat, cnt in counts.most_common():
        print(f"  {cat}: {cnt}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {args.out}")