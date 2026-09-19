"""
Approval workflow state (human-in-the-loop).
When a case is only waiting for a person's decision, the platform mails the approver and remembers the case here.
On the next run it looks for the approver's reply, completes the case, or sends a reminder / escalation.
"""
import json
from core.common import RUNTIME

FILE = RUNTIME / "workflow_state.json"


class Workflow:
    def __init__(self):
        self.data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}

    def save(self):
        FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def open(self, case_id, category, approval, run_id, day, request_mail):
        self.data[case_id] = {"category": category, "codes": approval["codes"], "role": approval["role"],
                              "approver": approval["approver"], "requested_on": day, "run_id": run_id,
                              "request_mail": request_mail, "state": "PENDING", "reminded": False, "escalated": False}

    def pending(self):
        return {k: v for k, v in self.data.items() if v["state"] == "PENDING"}

    def close(self, case_id, state):
        self.data[case_id]["state"] = state
