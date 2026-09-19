"""
Payroll adjustment export: approved expense reimbursements and leave deductions per employee,
built from the audit log (latest decision per case). The payroll system picks this file up.
"""
import json
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from core.common import RUNTIME, run_date

AUDIT = RUNTIME / "audit_log.jsonl"


def latest_decisions():
    last = {}
    if AUDIT.exists():
        for line in AUDIT.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            last[e["case_id"]] = e
    return last


def build(cfg, path=None):
    period = run_date(cfg).strftime("%Y-%m")
    lines, per_emp = [], defaultdict(lambda: {"reimbursement": 0, "leave_days": 0.0})
    for e in latest_decisions().values():
        if e["status"] != "APPROVED" or not e.get("extra"):
            continue
        x = e["extra"]
        if e["category"] == "expense_reimbursement":
            lines.append([x["emp_id"], "EXPENSE_REIMBURSEMENT", x["amount"], None, x["category"], e["reference"], e["case_id"], period])
            per_emp[x["emp_id"]]["reimbursement"] += x["amount"]
        elif e["category"] == "leave_request" and x.get("leave_type") in ("年次有給休暇", "半日有給申請"):
            lines.append([x["emp_id"], "PAID_LEAVE_DEDUCTION", None, x["days"], x["leave_type"], e["reference"], e["case_id"], period])
            per_emp[x["emp_id"]]["leave_days"] += x["days"]
    lines.sort(key=lambda r: (r[0], r[1]))
    wb = Workbook()
    ws = wb.active
    ws.title = "Adjustments"
    head = ["emp_id", "adjustment_type", "amount_jpy", "leave_days", "detail", "reference", "case_id", "payroll_period"]
    ws.append(head)
    for r in lines:
        ws.append(r)
    s2 = wb.create_sheet("By employee")
    s2.append(["emp_id", "reimbursement_jpy", "paid_leave_days_deducted"])
    for emp, v in sorted(per_emp.items()):
        s2.append([emp, v["reimbursement"], v["leave_days"]])
    for w in (ws, s2):
        for c in w[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E78")
    out = path or (RUNTIME / "exports" / "payroll_adjustments.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
