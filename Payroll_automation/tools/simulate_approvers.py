"""
Stands in for the human approvers in the prototype: for every pending approval request it puts a reply
("APPROVE" or "REJECT") into the mailbox, exactly as an approver's mail client would.
In real life people answer the mails themselves; this script only exists so the demo can show the full loop.

    python -m tools.simulate_approvers
"""
import hashlib
from core.common import now_iso
from core.workflow import Workflow
from services import store


def approver_decision(case_id):
    """Deterministic pseudo-decision: about 70% approve."""
    return "APPROVE" if int(hashlib.md5(case_id.encode()).hexdigest()[-2:], 16) % 10 < 7 else "REJECT"


def main():
    wf, n = Workflow(), 0
    for case, w in wf.pending().items():
        if any(m["case_ref"] == case and m.get("kind") == "approval_reply" for m in store.rows("mail")):
            continue
        d = approver_decision(case)
        mid = f"IN-APR-{case[-8:]}"
        store.put("mail", mid, {"id": mid, "case_ref": case, "folder": "inbox", "direction": "in", "kind": "approval_reply", "replied": False,
                                "from": w["approver"], "from_name": w["approver"], "to": "payroll-automation@company.local",
                                "subject": f"Re: 【承認依頼】{w['category']} {case}", "received_at": now_iso(), "attachments": [],
                                "body": f"{d}\n\n{'確認しました。問題ありません。' if d == 'APPROVE' else '内容に問題があるため却下します。'}"})
        n += 1
    print(f"{n} approver replies placed in the mailbox")


if __name__ == "__main__":
    main()
