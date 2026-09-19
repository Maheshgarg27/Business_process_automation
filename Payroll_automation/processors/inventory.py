"""
INVENTORY ADJUSTMENT
Rules: outbound must not exceed AVAILABLE stock (on-hand minus reserved), stock never goes negative,
scrap needs a reason code, count corrections must be backed by the warehouse count sheet (Excel),
large scrap/count corrections need warehouse-manager approval, safety-stock breach raises an alert.
Systems: WMS, Document store (count sheet), decision memo.
"""
from core.common import Result
from core.docparse import read_xlsx
from processors.base import archive_memo, finish

APPROVABLE = {"large_adjustment"}


def process(row, api, cfg, ctx):
    inv, case = cfg["inventory"], row["case_id"]
    req = api.get(f"/wms/adjustment-requests/{case}", allow_404=True)
    st = api.get(f"/wms/stock/{row['item_code']}", allow_404=True)
    if not req or not st:
        return Result("NEEDS_REVIEW", "WMSに該当の調整依頼または在庫マスタがありません", codes=["record_not_found"])
    typ, delta, qty = req["type"], req["delta"], req["qty"]
    on_hand, avail = st["on_hand"], st["on_hand"] - st["reserved"]
    reject, review = [], []

    if st["name"] != row["item_name"]:
        review.append(("item_name_mismatch", f"品目名が不一致（WMS: {st['name']}／シート: {row['item_name']}）"))
    if typ == "SCRAP" and not req["reason_code"]:
        reject.append(("no_reason", "廃棄理由コードが未入力"))
    if typ == "OUTBOUND" and qty > avail:
        reject.append(("insufficient_stock", f"引当分を除く利用可能在庫が不足（利用可能{avail}／要求{qty}）"))
    elif on_hand + delta < 0:
        reject.append(("negative_stock", f"調整後在庫がマイナスになります（現在庫{on_hand}／調整{delta:+d}）"))
    if typ == "COUNT_CORRECTION":
        raw = api.get_file(cfg["paths"]["count_sheet"].format(item_code=row["item_code"], request_no=req["request_no"]))
        if raw is None:
            review.append(("count_sheet_missing", "実地棚卸シートが共有ドライブにありません"))
        else:
            c = read_xlsx(raw)[0]
            if c["counted_qty"] - c["system_qty"] != delta:
                review.append(("count_unsupported", f"棚卸差異（{c['counted_qty'] - c['system_qty']:+d}）が調整依頼（{delta:+d}）と一致しません"))
    if typ in ("SCRAP", "COUNT_CORRECTION") and on_hand and abs(delta) > on_hand * inv["max_single_adjust_ratio"]:
        review.append(("large_adjustment", f"大口調整（現在庫の{abs(delta) / on_hand:.0%}）のため倉庫責任者の承認が必要"))

    status, parts, codes, approval, notes = finish(ctx, reject, review, APPROVABLE, lambda c: "warehouse", api, cfg, None)
    if status == "REJECTED":
        detail = "却下: " + " / ".join(parts)
    elif status == "NEEDS_REVIEW":
        detail = ("承認待ち（承認依頼を送付）: " if approval else "要確認: ") + " / ".join(parts)
    else:
        r = api.post("/wms/adjustments", {"case_id": case, "item_code": row["item_code"], "delta": delta, "reason": req["reason_code"] or typ})
        detail = f"{typ} {delta:+d}個を反映（在庫 {on_hand}→{r['balance_after']}）" + (f"／{'; '.join(notes)}" if notes else "")
        if r["balance_after"] < st["safety_stock"]:
            api.post("/wms/alerts", {"case_id": case, "item_code": row["item_code"], "type": "REPLENISH",
                                     "message": f"安全在庫{st['safety_stock']}を下回りました（{r['balance_after']}）"})
            detail += "／安全在庫割れ→補充アラート発行"
        archive_memo(api, cfg, row, "inventory_adjustment", status, [detail], r["movement_id"])
        return Result(status, detail, r["movement_id"], codes=codes)
    archive_memo(api, cfg, row, "inventory_adjustment", status, [detail])
    return Result(status, detail, "", codes=codes, approval=approval)
