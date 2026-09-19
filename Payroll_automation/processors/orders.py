"""
ORDER MANAGEMENT
Checks: vendor status, quotation (PDF opened and read: price, validity, quote number), unit-price tolerance by contract
type, contract price list (Excel) for annual contracts, blanket-contract remaining limit, emergency justification,
approval authority by amount. Success creates a purchase order and mails the vendor.
Systems: Procurement, Document store (quotation, price list), Mail, decision memo.
"""
from datetime import date
from core.common import Result, run_date
from core.docparse import field, read_text, read_xlsx
from processors.base import notify, archive_memo, finish
from processors.util import yen

APPROVABLE = {"approval_level", "price_variance", "justification"}
RANK = {None: 0, "manager": 1, "director": 2}
LEVEL_JP = {"manager": "部長", "director": "役員"}


def process(row, api, cfg, ctx):
    o, case, today = cfg["orders"], row["case_id"], run_date(cfg)
    rq = api.get(f"/scm/requisitions/{case}", allow_404=True)
    if not rq:
        return Result("NEEDS_REVIEW", "購買依頼が調達システムに存在しません", codes=["requisition_not_found"])
    vendor = api.get(f"/scm/vendors/{rq['vendor_id']}")
    ct, qty, total = row["contract_type"], int(row["quantity"]), int(row["total"])
    reject, review = [], []
    need = "director" if total >= o["approval_levels"]["director"] else "manager" if total >= o["approval_levels"]["manager"] else None

    if vendor["status"] != "ACTIVE":
        reject.append(("vendor_inactive", f"取引先 {vendor['name']} が取引停止中"))
    raw = api.get_file(cfg["paths"]["quote"].format(vendor_id=rq["vendor_id"], quote_no=rq["quote_no"]))
    quote_price = None
    if raw is None:
        review.append(("quote_missing", f"見積書 {rq['quote_no']} が共有ドライブにありません"))
    else:
        qt = read_text("q.pdf", raw)
        quote_price = float(field(qt, "Unit Price (JPY)").replace(",", ""))
        valid = date.fromisoformat(field(qt, "Valid Until"))
        if valid < today:
            reject.append(("quote_expired", f"見積の有効期限切れ（{valid}）"))
        expected = qty * quote_price
        dev = (total - expected) / expected * 100
        if abs(dev) > o["price_tolerance_pct"][ct]:
            review.append(("price_variance", f"見積金額との差異 {dev:+.1f}%（{ct}の許容±{o['price_tolerance_pct'][ct]}%）"))
    if ct == "年間契約":
        pl = api.get_file(cfg["paths"]["price_list"].format(vendor_id=rq["vendor_id"]))
        if pl and quote_price:
            lp = next((r["contract_unit_price"] for r in read_xlsx(pl) if r["item"] == row["item"]), None)
            if lp and abs(lp - quote_price) / lp * 100 > o["price_tolerance_pct"][ct]:
                review.append(("contract_price_conflict", f"契約単価表（{lp:,.0f}円）と見積単価（{quote_price:,.0f}円）が相違"))
        bc = api.get(f"/scm/blanket-contracts/{rq['vendor_id']}")
        if total > bc["annual_limit"] - bc["used"]:
            review.append(("contract_limit", f"年間契約の残枠不足（残{yen(bc['annual_limit'] - bc['used'])}／今回{yen(total)}）"))
    if row["urgency"] == "緊急" and not rq["justification"]:
        review.append(("justification", "緊急発注の理由書がありません"))
    if RANK[rq["approved_level"]] < RANK[need]:
        review.append(("approval_level", f"{yen(total)}は{LEVEL_JP[need]}承認が必要（現状: {LEVEL_JP.get(rq['approved_level'], '承認なし')}）"))

    def role_of(codes):
        if "approval_level" in codes:
            return "director" if need == "director" else "manager"
        return "procurement"

    status, parts, codes, approval, notes = finish(ctx, reject, review, APPROVABLE, role_of, api, cfg, rq["requester_dept"])
    ref = ""
    if status == "REJECTED":
        detail = "却下: " + " / ".join(parts)
    elif status == "NEEDS_REVIEW":
        detail = ("承認待ち（承認依頼を送付）: " if approval else "再確認が必要: ") + " / ".join(parts)
    else:
        po = api.post("/scm/purchase-orders", {"case_id": case, "vendor_id": rq["vendor_id"], "item": row["item"], "quantity": qty, "total": total,
                                               "contract_type": ct, "urgency": row["urgency"], "status": "CONFIRMED"}, allow_conflict=True)
        if po.get("conflict"):
            status, detail = "NEEDS_REVIEW", f"発注登録時に契約枠超過: {po['message']}"
            codes.append("contract_limit")
        else:
            ref = po["po_no"]
            detail = f"発注確定 {ref}（{row['item']} {qty}個 {yen(total)}）" + ("／緊急のため優先処理" if row["urgency"] == "緊急" else "") + (f"／{'; '.join(notes)}" if notes else "")
            notify(api, case, vendor["email"], f"【発注書】{ref} {row['item']}",
                   f"{vendor['name']} ご担当者様\n\n下記のとおり発注いたします。\n  発注番号: {ref}\n  品目: {row['item']}\n  数量: {qty}\n"
                   f"  金額: {yen(total)}\n  区分: {ct}／{row['urgency']}\n\nご確認をお願いいたします。\n購買部", "purchase_order")
    archive_memo(api, cfg, row, "order_management", status, [f"取引先: {vendor['name']}"] + parts + notes, ref)
    return Result(status, detail, ref, codes=codes, approval=approval)
