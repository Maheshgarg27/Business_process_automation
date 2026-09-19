"""
Compares a run with the expected results written by the dataset generator.

    python -m tools.verify_results --input data/input/payroll_cases_test.xlsx              # after the first run
    python -m tools.verify_results --input data/input/payroll_cases_test.xlsx --after-approvals
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook
from tools.simulate_approvers import approver_decision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--after-approvals", action="store_true")
    a = ap.parse_args()
    exp = json.loads((Path(a.input).parent / "expected_results.json").read_text(encoding="utf-8"))
    ws = load_workbook(a.input).worksheets[0]
    head = [c.value for c in ws[1]]
    bad, ok = [], 0
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = dict(zip(head, r))
        e = exp.get(d.get("case_id"))
        if not e:
            continue
        want = e["first"]
        if a.after_approvals and e["first"] == "NEEDS_REVIEW" and e["approvable"]:
            want = "APPROVED" if approver_decision(d["case_id"]) == "APPROVE" else "REJECTED"
        got = d.get("result_status")
        if got == want:
            ok += 1
        else:
            bad.append((d["case_id"], e["category"], e["scenario"], want, got, str(d.get("result_detail"))[:110]))
    total = ok + len(bad)
    print(f"Matched expected result: {ok}/{total} ({ok / total:.1%})")
    for b in bad[:40]:
        print("  MISMATCH", b)
    if bad:
        print("by scenario:", dict(Counter((b[1], b[2]) for b in bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
