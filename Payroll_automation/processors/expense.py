"""
EXPENSE REIMBURSEMENT
Checks: submission deadline, receipt file (opened and read), duplicate receipt, amount on receipt = claim,
category limits, manager approval, pre-approval for travel/training, per-head cap for entertainment,
qualified-invoice number (tax deduction warning).
Systems: ERP expense module, Document store (receipt PDF), HRIS, Mail, decision memo.
"""
from datetime import date
from core.common import Result, run_date
from core.docparse import field, read_text, to_int
from processors.base import notify, archive_memo, finish
from processors.util import yen

APPROVABLE = {"manager_approval", "pre_approval", "per_head"}


def process(row, api, cfg, ctx):
    ex, case, today = cfg["expense"], row["case_id"], run_date(cfg)
    cl = api.get(f"/fin/expense-claims/{case}", allow_404=True)
    if not cl:
        return Result("NEEDS_REVIEW", "経費システムに該当の申請がありません", codes=["claim_not_found"])
    emp = api.get(f"/hr/employees/{cl['emp_id']}")
    cat, amt = cl["category"], cl["amount"]
    lim = ex["limits"][cat]
    reject, review, warn, rcpt_no = [], [], [], None

    if amt != int(row["amount"]):
        review.append(("sheet_mismatch", f"シート金額({yen(row['amount'])})と申請金額({yen(amt)})が不一致"))
    pdf = api.get_file(cfg["paths"]["receipt"].format(emp_id=emp["emp_id"], yyyy_mm=cl["submitted_at"][:7].replace("-", "_"), claim_id=cl["claim_id"]))
    if pdf is None:
        if amt > ex["receipt_required_over"]:
            reject.append(("no_receipt", f"領収書ファイルがありません（{yen(ex['receipt_required_over'])}超は必須）"))
    else:
        text = read_text("r.pdf", pdf)
        rcpt_no = field(text, "Receipt No")
        total, rdate = to_int(field(text, "Total (JPY)")), field(text, "Date")
        if total != amt:
            review.append(("amount_mismatch", f"領収書の金額({yen(total or 0)})が申請金額({yen(amt)})と不一致"))
        age = (today - date.fromisoformat(rdate)).days
        if age > ex["approval_deadline_days"]:
            reject.append(("stale", f"領収書日付から{age}日経過（申請期限{ex['approval_deadline_days']}日）"))
        if rcpt_no and api.get(f"/fin/receipts/{rcpt_no}")["used"]:
            reject.append(("duplicate_receipt", f"領収書 {rcpt_no} は精算済み（二重申請）"))
        if not field(text, "Registration No"):
            warn.append("適格請求書発行事業者番号なし（仕入税額控除の対象外）")
    if amt > lim["max"]:
        reject.append(("over_limit", f"{cat}の上限{yen(lim['max'])}を超過（{yen(amt)}）"))
    elif amt > lim["auto"] and not cl["manager_approved"]:
        review.append(("manager_approval", f"{yen(lim['auto'])}超のため上長承認が必要（未承認）"))
    if cat in ("出張旅費", "研修費") and not cl["pre_approval_id"]:
        review.append(("pre_approval", "事前申請（出張/研修承認）がありません"))
    if cat == "接待交際費":
        per = amt / max(cl["attendees"], 1)
        if per > ex["entertainment_per_head"]:
            review.append(("per_head", f"1人当たり{yen(per)}が上限{yen(ex['entertainment_per_head'])}超（参加{cl['attendees']}名）"))

    status, parts, codes, approval, notes = finish(ctx, reject, review, APPROVABLE, lambda c: "manager", api, cfg, emp["dept"])
    if status == "REJECTED":
        detail = "却下: " + " / ".join(parts)
    elif status == "NEEDS_REVIEW":
        detail = ("承認待ち（承認依頼を送付）: " if approval else "要確認: ") + " / ".join(parts)
    else:
        detail = f"承認（{cat} {yen(amt)}／方針内）" + (f"／{'; '.join(notes)}" if notes else "")
    if warn:
        detail += "【注意】" + " / ".join(warn)
    ref = ""
    if not approval:
        dec = api.post("/fin/decisions", {"kind": "expense", "case_id": case, "status": status, "note": detail, "receipt_no": rcpt_no})
        ref = dec["ref"]
        notify(api, case, emp["email"], f"【経費精算結果】{cat} {yen(amt)} - {status}",
               f"{emp['name']} 様\n\n経費申請（{cat} {yen(amt)}）の審査結果: {status}\n{detail}\n\n経理部 経費精算担当", "expense_result")
    archive_memo(api, cfg, row, "expense_reimbursement", status, [f"申請者: {emp['name']} ({emp['dept']})"] + parts + notes + warn, ref)
    return Result(status, detail, ref, codes=codes, approval=approval, extra={"emp_id": emp["emp_id"], "amount": amt, "category": cat, "claim_id": cl["claim_id"]})
