"""
BUDGET VARIANCE
Compares the sheet with the general-ledger export (Excel on the drive), recomputes the variance and
escalates deviations to the department head, who can accept them by e-mail.
Systems: Document store (GL export), ERP (decision booking), HRIS (department head), Mail, decision memo.
"""
from core.common import Result
from core.docparse import read_xlsx
from processors.base import archive_memo, finish
from processors.util import yen

APPROVABLE = {"variance_review"}


def process(row, api, cfg, ctx):
    b, case = cfg["budget"], row["case_id"]
    raw = api.get_file(cfg["paths"]["gl"].format(period=cfg["budget_period"]))
    if raw is None:
        return Result("NEEDS_REVIEW", f"総勘定元帳エクスポート（{cfg['budget_period']}）が見つかりません", codes=["gl_missing"])
    line = next((r for r in read_xlsx(raw) if r["department"] == row["department"] and int(r["budget"]) == int(row["budget"])), None)
    if not line:
        return Result("NEEDS_REVIEW", "元帳に該当の予算行がありません（部門・予算額で照合）", codes=["ledger_line_missing"])

    ledger_actual, budget = int(line["actual"]), int(line["budget"])
    var = (ledger_actual - budget) / budget * 100
    reject, review = [], []
    if ledger_actual != int(row["actual"]):
        review.append(("ledger_mismatch", f"シートと元帳の実績が不一致（元帳{yen(ledger_actual)}／シート{yen(row['actual'])}）"))
    recomputed = (int(row["actual"]) - budget) / budget * 100
    if row.get("variance_pct") is not None and abs(row["variance_pct"] - recomputed) > b["mismatch_tolerance_pct"] + 0.05:
        review.append(("variance_mismatch", f"差異率が再計算値と相違（シート{row['variance_pct']}%／再計算{recomputed:.1f}%）"))
    a = abs(var)
    if a > b["note_pct"]:
        review.append(("variance_review", f"差異 {var:+.1f}%（予算{'超過' if var > 0 else '未消化'}）— 是正・役員報告が必要"))
    elif a > b["ok_pct"]:
        review.append(("variance_review", f"差異 {var:+.1f}% — 部門長によるコメント記入が必要"))

    status, parts, codes, approval, notes = finish(ctx, reject, review, APPROVABLE, lambda c: "manager", api, cfg, row["department"])
    if status == "APPROVED":
        detail = f"予算内（差異 {var:+.1f}%、許容±{b['ok_pct']}%）" + (f"／{'; '.join(notes)}" if notes else "")
    elif status == "REJECTED":
        detail = "差異は受け入れられません: " + " / ".join(parts)
    else:
        detail = ("承認待ち（部門長へ確認依頼を送付）: " if approval else "データ不整合のため要確認: ") + " / ".join(parts)
    ref = ""
    if not approval:
        ref = api.post("/fin/decisions", {"kind": "budget", "case_id": case, "status": status, "note": detail})["ref"]
    archive_memo(api, cfg, row, "budget_variance", status, [f"部門: {row['department']}", f"差異(元帳): {var:+.2f}%"] + parts + notes, ref)
    return Result(status, detail, ref, codes=codes, approval=approval, extra={"variance_pct": round(var, 2)})
