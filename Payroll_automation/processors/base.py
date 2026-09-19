"""Helpers shared by all process engines."""
from core.common import Result, now_iso

ROLE_RANK = {"director": 3, "manager": 2, "warehouse": 1, "procurement": 1}


def notify(api, case_id, to, subject, body, kind, in_reply_to=None):
    """Send an e-mail through the mail-server API. Returns the message id."""
    return api.post("/mail/send", {"case_ref": case_id, "to": to, "subject": subject, "body": body,
                                   "kind": kind, "in_reply_to": in_reply_to})["id"]


def archive_memo(api, cfg, row, category, status, lines, reference=""):
    """Store a decision memo (text file) in the document store under the run's folder."""
    content = "\n".join(["決裁メモ / Decision memo", f"run_id : {cfg.get('run_id', '-')}", f"案件ID : {row['case_id']}",
                         f"処理区分: {category}", f"判定    : {status}", f"参照番号: {reference}", f"処理日時: {now_iso()}",
                         "-" * 40] + [str(x) for x in lines])
    path = cfg["paths"]["memo"].format(run_id=cfg.get("run_id", "manual"), case_id=row["case_id"])
    api.put_file(path, content)
    return path


def approver_email(api, cfg, role, dept=None):
    if role == "manager":
        return api.get(f"/hr/departments/{dept}")["head_email"]
    return cfg["workflow"]["approvers"][role]


def finish(ctx, reject, review, approvable_codes, role_of, api, cfg, dept):
    """
    Turn rule failures into a decision.
      reject / review : lists of (code, text)
      role_of(codes)  : which approver role can settle the open review items
    Returns (status, detail_parts, codes, approval_or_None, notes).
    """
    review, denied, notes = ctx.resolve(review)
    reject_txt = [t for _, t in reject] + denied
    codes = [c for c, _ in reject] + [c for c, _ in review]
    if reject_txt:
        return "REJECTED", reject_txt + [t for _, t in review], codes, None, notes
    if review:
        approval = None
        if all(c in approvable_codes for c, _ in review):
            role = role_of([c for c, _ in review])
            approval = {"codes": [c for c, _ in review], "role": role, "approver": approver_email(api, cfg, role, dept),
                        "summary": " / ".join(t for _, t in review)}
        return "NEEDS_REVIEW", [t for _, t in review], codes, approval, notes
    return "APPROVED", [], codes, None, notes
