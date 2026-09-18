"""
Simulated ENTERPRISE SYSTEMS exposed as one REST API. In production these are separate
products (mail server, HRIS, ERP, procurement, WMS, file share); the pipeline only sees this interface.

Run:  uvicorn services.server:app --port 8765
All endpoints except /health need header  X-API-Key.
State-changing endpoints are idempotent per case_id (a retry never applies twice).
"""
import base64
from datetime import datetime
from typing import Optional
from fastapi import Body, Depends, FastAPI, Header, HTTPException
from core.common import RUNTIME, load_config
from services import store

API_KEY = load_config()["api"]["api_key"]
DRIVE = RUNTIME / "drive"


def auth(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(401, "invalid api key")


app = FastAPI(title="Enterprise systems (simulated)", dependencies=[Depends(auth)])


@app.get("/health", dependencies=[])
def health():
    return {"ok": True}


def once(action, case_id, fn):
    prev = store.get("actions", f"{action}:{case_id}")
    if prev:
        return {**prev, "duplicate": True}
    res = fn()
    store.put("actions", f"{action}:{case_id}", res)
    return res


def need(obj, what):
    if obj is None:
        raise HTTPException(404, f"{what} not found")
    return obj


# ============================================================ DOCUMENT STORE (shared drive)
def _safe(path):
    p = (DRIVE / path).resolve()
    if DRIVE.resolve() not in p.parents:
        raise HTTPException(400, "invalid path")
    return p


@app.get("/files/list")
def files_list(prefix: str = ""):
    if not DRIVE.exists():
        return []
    base = DRIVE.resolve()
    return sorted(str(f.relative_to(base)).replace("\\", "/") for f in base.rglob("*")
                  if f.is_file() and str(f.relative_to(base)).replace("\\", "/").startswith(prefix))


@app.get("/files/download")
def files_download(path: str):
    p = _safe(path)
    if not p.is_file():
        raise HTTPException(404, "file not found")
    return {"path": path, "content_b64": base64.b64encode(p.read_bytes()).decode()}


@app.post("/files/upload")
def files_upload(payload: dict = Body(...)):
    p = _safe(payload["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    if "text" in payload:
        p.write_text(payload["text"], encoding="utf-8")
    else:
        p.write_bytes(base64.b64decode(payload["content_b64"]))
    return {"path": payload["path"]}


# ================================================================ MAIL SERVER
@app.get("/mail/inbox")
def mail_list(case_ref: Optional[str] = None, folder: str = "inbox", kind: Optional[str] = None):
    out = []
    for m in store.rows("mail"):
        if m["folder"] == folder and (not case_ref or m["case_ref"] == case_ref) and (not kind or m.get("kind") == kind):
            out.append({k: v for k, v in m.items() if k != "attachments"}
                       | {"attachments": [a["doc_type"] for a in m.get("attachments", [])]})
    return out


@app.get("/mail/{mail_id}")
def mail_get(mail_id: str):
    m = need(store.get("mail", mail_id), "mail")
    return m | {"attachments": [{"doc_type": a["doc_type"], "filename": a["filename"]} for a in m.get("attachments", [])]}


@app.get("/mail/{mail_id}/attachments/{doc_type}")
def mail_attachment(mail_id: str, doc_type: str):
    m = need(store.get("mail", mail_id), "mail")
    for a in m.get("attachments", []):
        if a["doc_type"] == doc_type:
            return a
    raise HTTPException(404, "attachment not found")


@app.post("/mail/send")
def mail_send(p: dict = Body(...)):
    def do():
        mid = f"MSG-{store.count('mail') + 1:05d}"
        store.put("mail", mid, {
            "id": mid, "case_ref": p["case_ref"], "folder": "sent", "direction": "out", "kind": p.get("kind", "reply"),
            "from": p.get("from", "payroll-automation@company.local"), "to": p["to"], "subject": p["subject"],
            "body": p["body"], "in_reply_to": p.get("in_reply_to"),
            "sent_at": datetime.now().isoformat(timespec="seconds"), "attachments": []})
        return {"id": mid}
    return once("mail:" + p.get("kind", "reply"), p["case_ref"], do)


@app.post("/mail/{mail_id}/move")
def mail_move(mail_id: str, p: dict = Body(...)):
    m = need(store.get("mail", mail_id), "mail")
    m["folder"] = p["folder"]
    if p.get("replied"):
        m["replied"] = True
    store.put("mail", mail_id, m)
    return {"id": mail_id, "folder": m["folder"]}


# ===================================================================== HRIS
@app.get("/hr/employees/{emp_id}")
def hr_employee(emp_id: str):
    return need(store.get("employees", emp_id), "employee")


@app.get("/hr/departments/{dept}")
def hr_department(dept: str):
    return need(store.get("departments", dept), "department")


@app.get("/hr/background-checks/{candidate_id}")
def hr_bgcheck(candidate_id: str):
    return need(store.get("background_checks", candidate_id), "background check")


@app.get("/hr/leave-requests/{case_id}")
def hr_leave_request(case_id: str):
    return need(store.get("leave_requests", case_id), "leave request")


@app.get("/hr/leave-balance/{emp_id}")
def hr_balance(emp_id: str):
    return need(store.get("leave_balances", emp_id), "leave balance")


@app.get("/hr/team-absences")
def hr_team_absences(dept: str, date: str):
    d = need(store.get("departments", dept), "department")
    rec = store.get("team_absences", f"{dept}:{date}") or {"absent": 0}
    return {"dept": dept, "date": date, "absent": rec["absent"], "headcount": d["headcount"]}


@app.get("/hr/comp-used/{emp_id}")
def hr_comp_used(emp_id: str):
    return store.get("comp_used", emp_id) or []


@app.get("/hr/flex-changes/{emp_id}")
def hr_flex_count(emp_id: str, month: str):
    return store.get("flex_changes", f"{emp_id}:{month}") or {"count": 0}


@app.post("/hr/leave-balance/deduct")
def hr_deduct(p: dict = Body(...)):
    def do():
        b = need(store.get("leave_balances", p["emp_id"]), "leave balance")
        bucket, days = p["bucket"], float(p["days"])
        if b[bucket] < days:
            raise HTTPException(409, f"insufficient {bucket} balance")
        b[bucket] = round(b[bucket] - days, 2)
        if p.get("half_day"):
            b["half_days_used"] += 1
        store.put("leave_balances", p["emp_id"], b)
        return {"bucket": bucket, "remaining": b[bucket], "ref": f"LV-{p['case_id'][-8:]}"}
    return once("leave_deduct", p["case_id"], do)


@app.post("/hr/comp-used/register")
def hr_comp_register(p: dict = Body(...)):
    def do():
        used = store.get("comp_used", p["emp_id"]) or []
        used.append(p["worked_date"])
        store.put("comp_used", p["emp_id"], used)
        return {"ref": f"COMP-{p['case_id'][-8:]}"}
    return once("comp_register", p["case_id"], do)


@app.post("/hr/flex-changes/register")
def hr_flex_register(p: dict = Body(...)):
    def do():
        key = f"{p['emp_id']}:{p['month']}"
        rec = store.get("flex_changes", key) or {"count": 0}
        rec["count"] += 1
        store.put("flex_changes", key, rec)
        return {"count": rec["count"], "ref": f"FLEX-{p['case_id'][-8:]}"}
    return once("flex_register", p["case_id"], do)


@app.post("/hr/team-absences/register")
def hr_absence_register(p: dict = Body(...)):
    def do():
        key = f"{p['dept']}:{p['date']}"
        rec = store.get("team_absences", key) or {"absent": 0}
        rec["absent"] += 1
        store.put("team_absences", key, rec)
        return {"absent": rec["absent"]}
    return once("absence_register", p["case_id"], do)


# ===================================================== ERP / FINANCE (AP, expenses)
@app.get("/fin/invoices/{invoice_id}")
def fin_invoice(invoice_id: str):
    return need(store.get("invoices", invoice_id), "invoice")


@app.get("/fin/invoices/{invoice_id}/duplicates")
def fin_invoice_dups(invoice_id: str):
    inv = need(store.get("invoices", invoice_id), "invoice")
    return [o["invoice_id"] for o in store.rows("invoices")
            if o["invoice_id"] != invoice_id and o["vendor_id"] == inv["vendor_id"]
            and o["amount"] == inv["amount"] and o["invoice_date"] == inv["invoice_date"]
            and o["status"] in ("PAID", "APPROVED")]


@app.get("/fin/purchase-orders/{po_no}")
def fin_po(po_no: str):
    return need(store.get("purchase_orders", po_no), "purchase order")


@app.get("/fin/goods-receipts/{po_no}")
def fin_gr(po_no: str):
    return need(store.get("goods_receipts", po_no), "goods receipt")


@app.get("/fin/vendors/{vendor_id}")
def fin_vendor(vendor_id: str):
    return need(store.get("vendors", vendor_id), "vendor")


@app.get("/fin/expense-claims/{case_id}")
def fin_claim(case_id: str):
    return need(store.get("expense_claims", case_id), "expense claim")


@app.get("/fin/receipts/{receipt_no}")
def fin_receipt(receipt_no: str):
    return store.get("used_receipts", receipt_no) or {"used": False}


@app.post("/fin/decisions")
def fin_decision(p: dict = Body(...)):
    """Books a final AP / budget / expense decision and updates the source record."""
    def do():
        n = store.count("decisions") + 1
        ref = f"{p['kind'][:3].upper()}-{datetime.now():%y%m}-{n:05d}"
        store.put("decisions", ref, {"ref": ref, **p, "at": datetime.now().isoformat(timespec="seconds")})
        if p["kind"] == "invoice":
            inv = store.get("invoices", p["invoice_id"])
            if inv:
                inv["status"] = {"APPROVED": "APPROVED", "REJECTED": "REJECTED"}.get(p["status"], "ON_HOLD")
                inv["contract_checked"] = True
                store.put("invoices", p["invoice_id"], inv)
        if p["kind"] == "expense":
            cl = store.get("expense_claims", p["case_id"])
            if cl:
                cl["status"] = p["status"]
                store.put("expense_claims", p["case_id"], cl)
            if p["status"] == "APPROVED" and p.get("receipt_no"):
                store.put("used_receipts", p["receipt_no"], {"used": True, "case_id": p["case_id"]})
        return {"ref": ref}
    return once("fin_decision:" + p["kind"], p["case_id"], do)


# ==================================================================== PROCUREMENT
@app.get("/scm/requisitions/{case_id}")
def scm_requisition(case_id: str):
    return need(store.get("requisitions", case_id), "requisition")


@app.get("/scm/vendors/{vendor_id}")
def scm_vendor(vendor_id: str):
    return need(store.get("scm_vendors", vendor_id), "vendor")


@app.get("/scm/blanket-contracts/{vendor_id}")
def scm_blanket(vendor_id: str):
    return need(store.get("blanket_contracts", vendor_id), "blanket contract")


@app.post("/scm/purchase-orders")
def scm_create_po(p: dict = Body(...)):
    def do():
        po = f"PO-{datetime.now():%y%m}-{store.count('scm_pos') + 1:05d}"
        if p["status"] == "CONFIRMED" and p["contract_type"] == "年間契約":
            bc = need(store.get("blanket_contracts", p["vendor_id"]), "blanket contract")
            if bc["used"] + p["total"] > bc["annual_limit"]:
                raise HTTPException(409, "blanket contract limit exceeded")
            bc["used"] += p["total"]
            store.put("blanket_contracts", p["vendor_id"], bc)
        store.put("scm_pos", po, {"po_no": po, **p, "created_at": datetime.now().isoformat(timespec="seconds")})
        return {"po_no": po, "status": p["status"]}
    return once("po", p["case_id"], do)


# ======================================================================== WMS
@app.get("/wms/stock/{item_code}")
def wms_stock(item_code: str):
    return need(store.get("stock", item_code), "stock item")


@app.get("/wms/adjustment-requests/{case_id}")
def wms_request(case_id: str):
    return need(store.get("adjustment_requests", case_id), "adjustment request")


@app.post("/wms/adjustments")
def wms_adjust(p: dict = Body(...)):
    def do():
        s = need(store.get("stock", p["item_code"]), "stock item")
        if s["on_hand"] + p["delta"] < 0:
            raise HTTPException(409, "adjustment would make on-hand negative")
        s["on_hand"] += p["delta"]
        mv = f"MOV-{store.count('movements') + 1:05d}"
        store.put("stock", p["item_code"], s)
        store.put("movements", mv, {"id": mv, **p, "balance_after": s["on_hand"],
                                    "at": datetime.now().isoformat(timespec="seconds")})
        return {"movement_id": mv, "balance_after": s["on_hand"]}
    return once("wms_adjust", p["case_id"], do)


@app.post("/wms/alerts")
def wms_alert(p: dict = Body(...)):
    def do():
        aid = f"ALERT-{store.count('alerts') + 1:04d}"
        store.put("alerts", aid, {"id": aid, **p})
        return {"id": aid}
    return once("wms_alert", p["case_id"], do)
