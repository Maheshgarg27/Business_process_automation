"""
LEAVE REQUEST - every leave type has its own policy rules.
  annual  : 80% attendance rule, balance, team capacity that day
  half    : balance >= 0.5 and yearly half-day cap
  special : event -> allowed days, proof document (Word file on the drive) must match the event
  comp    : an unused holiday-work day in the attendance export (Excel) inside the validity window
  flex    : core time must be worked, monthly change cap
Systems: HRIS, Document store (proof, attendance export), Mail, decision memo.
"""
from datetime import date
from core.common import Result, run_date
from core.docparse import field, read_text, read_xlsx
from processors.base import notify, archive_memo, finish

APPROVABLE = {"manager_approval"}


def process(row, api, cfg, ctx):
    lv, case, today = cfg["leave"], row["case_id"], run_date(cfg)
    req = api.get(f"/hr/leave-requests/{case}", allow_404=True)
    if not req:
        return Result("NEEDS_REVIEW", "HRシステムに該当の休暇申請がありません", codes=["request_not_found"])
    emp = api.get(f"/hr/employees/{req['emp_id']}")
    bal = api.get(f"/hr/leave-balance/{emp['emp_id']}")
    lt, d, days = row["leave_type"], row["date"], req["days"]
    reject, review, apply = [], [], {}

    if date.fromisoformat(d) <= today:
        reject.append(("past_date", "申請日が処理基準日以前です"))
    if not req["manager_approved"]:
        review.append(("manager_approval", "上長承認が未完了"))

    if lt == "年次有給休暇":
        if bal["attendance_rate_prev_year"] < lv["min_attendance_rate"]:
            reject.append(("attendance_rate", f"前年度出勤率{bal['attendance_rate_prev_year']:.0%}（付与要件{lv['min_attendance_rate']:.0%}未満）"))
        if bal["annual_days"] < days:
            reject.append(("balance", f"有給残日数不足（残{bal['annual_days']}日／申請{days}日）"))
        ab = api.get("/hr/team-absences", dept=emp["dept"], date=d)
        cap = int(ab["headcount"] * lv["team_max_absent_ratio"])
        if ab["absent"] + 1 > ab["headcount"] * lv["team_max_absent_ratio"]:
            reject.append(("team_capacity", f"同日の部門欠勤上限超過（{ab['absent']}名／上限{cap}名）"))
        apply = {"bucket": "annual_days", "days": days}
    elif lt == "半日有給申請":
        if bal["annual_days"] < 0.5:
            reject.append(("balance", f"有給残日数不足（残{bal['annual_days']}日）"))
        if bal["half_days_used"] >= lv["half_day_max_per_year"]:
            reject.append(("half_day_cap", f"半日有給の年間上限（{lv['half_day_max_per_year']}回）に到達"))
        apply = {"bucket": "annual_days", "days": 0.5, "half_day": True}
    elif lt == "特別休暇（慶弔）":
        ev = req.get("event") or {}
        key = ev.get("kind") if ev.get("kind") == "結婚" else f"{ev.get('kind')}_{ev.get('relation')}"
        allowed = lv["special_leave_days"].get(key)
        if allowed is None:
            reject.append(("policy", "慶弔区分が就業規則に該当しません"))
        elif days > allowed:
            reject.append(("over_days", f"{ev['kind']}（{ev['relation']}）の付与上限{allowed}日を超過（申請{days}日）"))
        proof = api.get_file(cfg["paths"]["leave_proof"].format(emp_id=emp["emp_id"], case_id=case))
        if proof is None:
            reject.append(("no_proof", "証明書類が共有ドライブにありません"))
        else:
            pt = read_text("p.docx", proof)
            if field(pt, "事由") != ev.get("kind") or field(pt, "続柄") != ev.get("relation"):
                reject.append(("proof_mismatch", f"証明書類の内容（{field(pt, '事由')}／{field(pt, '続柄')}）が申請内容と一致しません"))
    elif lt == "代休申請":
        used = set(api.get(f"/hr/comp-used/{emp['emp_id']}"))
        recs = []
        for f in api.list_files(cfg["paths"]["attendance"]):
            recs += [r for r in read_xlsx(api.get_file(f)) if r["emp_id"] == emp["emp_id"] and r["day_type"] == "休日出勤"]
        recs = [r for r in recs if str(r["work_date"])[:10] not in used]
        valid = [r for r in recs if (today - date.fromisoformat(str(r["work_date"])[:10])).days <= lv["comp_day_valid_days"]]
        if not recs:
            reject.append(("no_record", "勤怠データに未消化の休日出勤実績がありません"))
        elif not valid:
            reject.append(("expired_record", f"休日出勤実績が代休取得期限（{lv['comp_day_valid_days']}日）を超過"))
        else:
            apply = {"worked_date": str(valid[0]["work_date"])[:10]}
    elif lt == "フレックス変更申請":
        fx = req["flex"]
        if fx["new_start"] > lv["flex_core_start"] or fx["new_end"] < lv["flex_core_end"]:
            reject.append(("core_time", f"コアタイム（{lv['flex_core_start']}-{lv['flex_core_end']}）を満たしていません（申請 {fx['new_start']}-{fx['new_end']}）"))
        n = api.get(f"/hr/flex-changes/{emp['emp_id']}", month=d[:7])["count"]
        if n >= lv["flex_max_changes_per_month"]:
            reject.append(("flex_cap", f"月間変更回数の上限（{lv['flex_max_changes_per_month']}回）に到達"))
        apply = {"flex": True}
    else:
        return Result("NEEDS_REVIEW", f"未対応の休暇区分: {lt}", codes=["unsupported"])

    status, parts, codes, approval, notes = finish(ctx, reject, review, APPROVABLE, lambda c: "manager", api, cfg, emp["dept"])
    ref, extra = "", {"emp_id": emp["emp_id"], "leave_type": lt, "date": d, "days": days if lt != "フレックス変更申請" else 0}
    if status == "REJECTED":
        detail = "却下: " + " / ".join(parts)
        ref = notify(api, case, emp["email"], f"【休暇申請結果】{lt} 否認",
                     f"{emp['name']} 様\n\n{d}の「{lt}」申請は以下の理由により承認できませんでした。\n" + "\n".join(f"  ・{p}" for p in parts)
                     + "\n\n内容をご確認のうえ再申請ください。\n人事部 勤怠担当", "leave_result")
    elif status == "NEEDS_REVIEW":
        detail = "要件は充足。" + " / ".join(parts) + "のため保留（承認依頼を送付）" if approval else "要確認: " + " / ".join(parts)
        if not approval:
            ref = notify(api, case, emp["email"], f"【休暇申請】{lt} 要確認", f"{emp['name']} 様\n\n{detail}", "leave_result")
    else:
        note = ""
        if "bucket" in apply:
            r = api.post("/hr/leave-balance/deduct", {"case_id": case, "emp_id": emp["emp_id"], "bucket": apply["bucket"],
                                                     "days": apply["days"], "half_day": apply.get("half_day", False)})
            note = f"有給残 {r['remaining']}日"
        if "worked_date" in apply:
            api.post("/hr/comp-used/register", {"case_id": case, "emp_id": emp["emp_id"], "worked_date": apply["worked_date"]})
            note = f"休日出勤日 {apply['worked_date']} を代休に充当"
        if apply.get("flex"):
            api.post("/hr/flex-changes/register", {"case_id": case, "emp_id": emp["emp_id"], "month": d[:7]})
            note = "フレックス勤務パターンを更新"
        if lt != "フレックス変更申請":
            api.post("/hr/team-absences/register", {"case_id": case, "dept": emp["dept"], "date": d})
        note = note or "特別休暇として付与"
        detail = f"承認（{note}）" + (f"／{'; '.join(notes)}" if notes else "")
        ref = notify(api, case, emp["email"], f"【休暇申請結果】{lt} 承認", f"{emp['name']} 様\n\n{d}の「{lt}」を承認しました。（{note}）\n人事部 勤怠担当", "leave_result")
    archive_memo(api, cfg, row, "leave_request", status, [f"社員: {emp['name']} ({emp['emp_id']}) {emp['dept']}", f"区分: {lt} {d}"] + parts + notes, ref)
    return Result(status, detail, ref, codes=codes, approval=approval, extra=extra)
