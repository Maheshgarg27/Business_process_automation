"""
INVOICE APPROVAL  (invoice PDF <-> ERP invoice <-> purchase order <-> goods receipt <-> contract)
Systems: ERP/AP, Document store (invoice PDF, contract Word file), Mail (vendor query), decision memo.
"""
from datetime import date
from core.common import Result
from core.docparse import field, read_text, to_int
from processors.base import notify, archive_memo, finish
from processors.util import yen

APPROVABLE = set()


def process(row, api, cfg, ctx):
    t, case = cfg["invoice"], row["case_id"]
    inv = api.get(f"/fin/invoices/{row['invoice_id']}", allow_404=True)
    if not inv:
        return Result("NEEDS_REVIEW", f"請求書 {row['invoice_id']} がERPに存在しません", codes=["invoice_not_found"])
    reject, review = [], []

    if int(row["amount"]) != inv["amount"]:
        review.append(("sheet_mismatch", f"シート金額({yen(row['amount'])})とERP登録金額({yen(inv['amount'])})が不一致"))

    pdf = api.get_file(cfg["paths"]["invoice_pdf"].format(vendor_id=inv["vendor_id"], invoice_id=inv["invoice_id"]))
    if pdf is None:
        review.append(("invoice_pdf_missing", "請求書PDFが共有ドライブにありません"))
    else:
        text = read_text("x.pdf", pdf)
        pdf_amt = to_int(field(text, "Amount (JPY, tax incl.)"))
        if pdf_amt != inv["amount"]:
            review.append(("pdf_mismatch", f"請求書PDFの金額({yen(pdf_amt or 0)})がERP金額({yen(inv['amount'])})と不一致"))
        if field(text, "PO No") != inv["po_no"]:
            review.append(("po_reference_mismatch", f"請求書PDFのPO番号({field(text, 'PO No')})がERPと不一致"))

    vendor = api.get(f"/fin/vendors/{inv['vendor_id']}", allow_404=True)
    if not vendor or vendor["status"] != "ACTIVE":
        reject.append(("vendor_inactive", "取引先が有効でありません"))
    dups = api.get(f"/fin/invoices/{inv['invoice_id']}/duplicates")
    if dups:
        reject.append(("duplicate", f"二重請求の疑い（支払済/承認済の同一請求: {', '.join(dups)}）"))

    po = api.get(f"/fin/purchase-orders/{inv['po_no']}", allow_404=True)
    if not po:
        reject.append(("missing_po", f"対応する発注書(PO {inv['po_no']})が存在しません"))
    else:
        tol = max(po["amount"] * t["tolerance_pct"] / 100, t["tolerance_yen"])
        gap = inv["amount"] - po["amount"]
        if abs(gap) > tol:
            review.append(("po_gap", f"請求額と発注額に差異 {yen(gap)}（許容{yen(tol)}）"))
        gr = api.get(f"/fin/goods-receipts/{inv['po_no']}", allow_404=True)
        if not gr:
            review.append(("no_receipt", "検収（入荷）記録がありません"))
        elif inv["amount"] - gr["received_amount"] > tol:
            review.append(("receipt_gap", f"請求額が検収額を超過 {yen(inv['amount'] - gr['received_amount'])}（許容{yen(tol)}）"))
        cbytes = api.get_file(cfg["paths"]["contract"].format(vendor_id=inv["vendor_id"], contract_no=po["contract_no"]))
        if cbytes is None:
            review.append(("contract_missing", f"契約書 {po['contract_no']} が共有ドライブにありません"))
        else:
            ct = read_text("c.docx", cbytes)
            start, end = date.fromisoformat(field(ct, "契約開始日")), date.fromisoformat(field(ct, "契約終了日"))
            inv_date = date.fromisoformat(inv["invoice_date"])
            if not (start <= inv_date <= end):
                review.append(("contract_expired", f"請求日が契約期間外（{start}〜{end}）"))
            if inv["amount"] > (to_int(field(ct, "契約上限額")) or 0):
                review.append(("contract_ceiling", "請求額が契約上限額を超過"))

    status, parts, codes, _, _ = finish(ctx, reject, review, APPROVABLE, lambda c: "manager", api, cfg, None)
    detail = "3点照合（請求書・発注書・検収・契約書）一致。差異なし" if status == "APPROVED" else "差異あり・要確認: " + " / ".join(parts)
    dec = api.post("/fin/decisions", {"kind": "invoice", "case_id": case, "invoice_id": inv["invoice_id"], "status": status, "note": detail})
    if status != "APPROVED" and vendor:
        notify(api, case, vendor["contact_email"], f"【請求書のご確認】{inv['invoice_id']}",
               f"{vendor['name']} ご担当者様\n\n請求書 {inv['invoice_id']} について、以下の点を確認させてください。\n"
               + "\n".join(f"  ・{p}" for p in parts) + "\n\nご確認のうえ、修正版のご送付をお願いいたします。\n経理部 買掛金担当", "invoice_query")
    archive_memo(api, cfg, row, "invoice_approval", status, [f"請求書: {inv['invoice_id']}  PO: {inv['po_no']}"] + parts, dec["ref"])
    return Result(status, detail, dec["ref"], codes=codes)
