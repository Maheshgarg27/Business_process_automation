"""
Builds the TEST WORLD for the platform:
  * an input workbook with ~50 rows per process, shuffled together (same columns as the real sheet)
  * expected_results.json  (what a correct run must produce for every row)
  * the records in the simulated systems (mail, HRIS, ERP, procurement, WMS)
  * the real documents on the simulated shared drive (PDF / Word / Excel files)

    python -m tools.generate_dataset --per-process 50 --seed 2026

In a real deployment none of this exists: the company's systems and drives already hold the data.
"""
import argparse, base64, io, json, random, shutil
from datetime import date, timedelta
from pathlib import Path
from openpyxl import Workbook
from core.common import ROOT, RUNTIME, load_config, run_date
from services import store

DRIVE = RUNTIME / "drive"
COLS = ["case_id", "category_type", "hire_type", "invoice_id", "amount", "has_discrepancy", "leave_type", "date",
        "expense_category", "item_code", "item_name", "department", "budget", "actual", "variance_pct",
        "contract_type", "item", "quantity", "total", "urgency"]
FAMILY = ["田中", "佐藤", "鈴木", "高橋", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田", "松本", "井上", "木村", "斎藤", "清水", "林"]
GIVEN = ["太郎", "花子", "健一", "美咲", "翔太", "陽子", "蓮", "結衣", "大輝", "彩", "拓也", "直樹", "真由", "優子", "誠", "恵"]
DEPTS = ["営業部", "開発部", "管理部", "物流部", "製造部", "人事部", "経理部"]
ITEMS = ["事務用品", "梱包材料", "工場設備部品", "電子基板ユニット", "包装資材", "サーバー保守部品", "測定機器"]


# ------------------------------------------------------------------ file builders
def pdf_bytes(lines):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for i, ln in enumerate(lines):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 16 if i == 0 else 11)
        c.drawString(60, y, ln)
        y -= 26 if i == 0 else 18
    c.save()
    return buf.getvalue()


def docx_bytes(lines):
    import docx
    d = docx.Document()
    for ln in lines:
        d.add_paragraph(ln)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def xlsx_bytes(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def drive_write(path, data):
    p = DRIVE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def yen(n):
    return f"{int(n):,}"


# ------------------------------------------------------------------ world state
class World:
    def __init__(self, seed, cfg, n):
        self.rng = random.Random(seed)
        self.cfg, self.n = cfg, n
        self.today = run_date(cfg)
        self.rows, self.expected = [], {}
        self.emp_seq = 10000

    def cid(self):
        return "AUTO-" + "".join(self.rng.choice("0123456789abcdef") for _ in range(10))

    def person(self):
        return self.rng.choice(FAMILY) + " " + self.rng.choice(GIVEN)

    def employee(self, dept=None):
        self.emp_seq += self.rng.randint(1, 9)
        e = {"emp_id": f"E{self.emp_seq}", "name": self.person(), "dept": dept or self.rng.choice(DEPTS)}
        e["email"] = f"{e['emp_id'].lower()}@company.local"
        store.put("employees", e["emp_id"], e)
        return e

    def add(self, cat, values, scenario, status, approvable=False):
        row = {c: None for c in COLS}
        row.update(values)
        row["case_id"], row["category_type"] = self.cid(), cat
        self.rows.append(row)
        self.expected[row["case_id"]] = {"category": cat, "scenario": scenario, "first": status, "approvable": approvable}
        return row

    def plan(self, counts):
        lst = [s for s, k in counts.items() for _ in range(k)]
        assert len(lst) == self.n, (len(lst), self.n)
        self.rng.shuffle(lst)
        return lst


def scale(counts, n):
    """Scale scenario counts (defined for 50) to n rows, keeping every scenario at least once."""
    if n == 50:
        return counts
    out = {k: max(1, round(v * n / 50)) for k, v in counts.items()}
    first = next(iter(out))
    out[first] += n - sum(out.values())
    return out


# ------------------------------------------------------------------ ONBOARDING
DOC_LABEL = {"resume": "履歴書", "career_history": "職務経歴書", "graduation_certificate": "卒業（見込）証明書",
             "id_copy": "本人確認書類", "offer_acceptance": "内定承諾書", "signed_contract": "雇用契約書（署名済）",
             "bank_form": "給与振込口座届", "health_certificate": "健康診断書", "withholding_slip": "源泉徴収票",
             "dependent_form": "扶養控除等申告書", "residence_certificate": "住民票"}
DATED = {"graduation_certificate", "health_certificate", "withholding_slip", "residence_certificate"}


def gen_onboarding(w):
    ob, today, rng = w.cfg["onboarding"], w.today, w.rng
    counts = scale({"ok": 26, "missing_doc": 5, "name_mismatch": 3, "expired_cert": 4, "unsigned": 3, "low_experience": 4,
                    "background_flag": 3, "underage": 1, "id_expired": 1}, w.n)
    types = ["新卒", "中途", "新卒家族持", "契約社員"]
    k = 0
    for scen in w.plan(counts):
        pool = [t for t in types if ob["min_experience_years"][t] > 0] if scen == "low_experience" else types
        ht = pool[k % len(pool)]
        k += 1
        name = w.person()
        need_exp = ob["min_experience_years"][ht]
        exp = 0 if ht.startswith("新卒") else round(rng.uniform(need_exp + 0.5, need_exp + 6), 1)
        if scen == "low_experience":
            exp = round(rng.uniform(0.3, need_exp - 0.4), 1)
        birth = today.replace(year=today.year - (17 if scen == "underage" else 22 if ht.startswith("新卒") else rng.randint(26, 40)))
        docs = {}
        for d in ob["required_documents"][ht]:
            lines = [f"【書類種別】{DOC_LABEL[d]}", f"氏名: {name}"]
            if d in ("resume", "career_history"):
                lines.append(f"経験年数: {exp}年")
            if d in DATED:
                lines.append(f"発行日: {(today - timedelta(days=rng.randint(5, 60))).isoformat()}")
            if d == "id_copy":
                exp_id = today - timedelta(days=30) if scen == "id_expired" else today.replace(year=today.year + 3)
                lines += [f"生年月日: {birth.isoformat()}", f"有効期限: {exp_id.isoformat()}"]
            if d in ("offer_acceptance", "signed_contract"):
                lines.append("署名: 済")
            if d == "signed_contract" and ht == "契約社員":
                lines.append("契約期間: 6ヶ月")
            if d == "dependent_form":
                lines.append("扶養家族人数: 2")
            docs[d] = lines
        if scen == "missing_doc":
            del docs[rng.choice([d for d in docs if d != "resume"])]
        if scen == "expired_cert":
            docs["health_certificate"][2] = f"発行日: {(today - timedelta(days=rng.randint(130, 220))).isoformat()}"
        if scen == "name_mismatch":
            docs["id_copy"][1] = f"氏名: {rng.choice(FAMILY)} {rng.choice(GIVEN)}"
        if scen == "unsigned":
            key = "signed_contract" if "signed_contract" in docs else "offer_acceptance"
            docs[key] = [ln if not ln.startswith("署名") else "署名: 未" for ln in docs[key]]
        row = w.add("onboarding_match", {"hire_type": ht}, scen, "APPROVED" if scen == "ok" else "REJECTED")
        cid = f"CAND-{rng.randint(100000, 999999)}"
        email = f"cand{cid[-5:]}@example-mail.local"
        atts = [{"doc_type": d, "filename": f"{DOC_LABEL[d]}.docx",
                 "content_b64": base64.b64encode(docx_bytes(v)).decode()} for d, v in docs.items()]
        mid = f"IN-{row['case_id'][-8:]}"
        store.put("mail", mid, {"id": mid, "case_ref": row["case_id"], "folder": "inbox", "direction": "in", "kind": "application",
                                "replied": False, "candidate_id": cid, "from": email, "from_name": name,
                                "to": "hr-onboarding@company.local", "subject": f"【入社手続き書類のご提出】{ht}／{name}",
                                "body": f"人事ご担当者様\n\nお世話になっております。{name}です。\n入社手続きに必要な書類を添付いたします。"
                                        f"ご確認のほどよろしくお願いいたします。\n（雇用区分: {ht}）",
                                "received_at": (today - timedelta(days=rng.randint(1, 4))).isoformat(), "attachments": atts})
        store.put("background_checks", cid, {"candidate_id": cid, "status": "HOLD" if scen == "background_flag" else "CLEAR",
                                              "note": "前職照会で確認事項あり" if scen == "background_flag" else ""})


# --------------------------------------------------------------------- INVOICE
def gen_invoice(w):
    rng, today = w.rng, w.today
    vendors = [f"VND-AP{n:02d}" for n in range(1, 9)]
    for i, v in enumerate(vendors):
        store.put("vendors", v, {"vendor_id": v, "name": f"取引先{i + 1}株式会社", "status": "ACTIVE", "contact_email": f"ar@vendor{i + 1}.example.local"})
    for v in ("VND-AP91", "VND-AP92"):
        store.put("vendors", v, {"vendor_id": v, "name": "取引停止先株式会社", "status": "INACTIVE", "contact_email": f"ar@{v.lower()}.example.local"})
    counts = scale({"ok": 24, "ok_tolerance": 4, "amount_over": 5, "partial_receipt": 4, "duplicate": 3, "missing_po": 3,
                    "vendor_inactive": 2, "pdf_mismatch": 3, "contract_expired": 2}, w.n)
    for scen in w.plan(counts):
        amount = rng.randint(150_000, 6_000_000)
        vendor = rng.choice(["VND-AP91", "VND-AP92"]) if scen == "vendor_inactive" else rng.choice(vendors)
        inv_id = f"INV-2026-{rng.randint(1000, 9999)}"
        while store.get("invoices", inv_id):
            inv_id = f"INV-2026-{rng.randint(1000, 9999)}"
        po_no, contract_no = f"PO-{inv_id[-4:]}-{rng.randint(10, 99)}", f"CT-{rng.randint(1000, 9999)}"
        inv_date = today - timedelta(days=rng.randint(3, 25))
        po_amount = received = pdf_amount = amount
        has_po = scen != "missing_po"
        c_start, c_end = today - timedelta(days=300), today + timedelta(days=200)
        if scen == "ok_tolerance":
            po_amount = received = amount + rng.randint(-250, 250)
        elif scen == "amount_over":
            po_amount = received = int(amount * rng.uniform(0.86, 0.95))
        elif scen == "partial_receipt":
            received = int(amount * rng.uniform(0.7, 0.9))
        elif scen == "pdf_mismatch":
            pdf_amount = int(amount * rng.choice([1.1, 0.9, 1.05]))
        elif scen == "contract_expired":
            c_end = inv_date - timedelta(days=20)
        elif scen == "duplicate":
            store.put("invoices", f"{inv_id}-P", {"invoice_id": f"{inv_id}-P", "vendor_id": vendor, "amount": amount,
                      "invoice_date": inv_date.isoformat(), "po_no": po_no, "status": "PAID", "contract_checked": True})
        first = "APPROVED" if scen in ("ok", "ok_tolerance") else "REJECTED" if scen in ("duplicate", "missing_po", "vendor_inactive") else "NEEDS_REVIEW"
        w.add("invoice_approval", {"invoice_id": inv_id, "amount": amount, "has_discrepancy": first != "APPROVED"}, scen, first)
        store.put("invoices", inv_id, {"invoice_id": inv_id, "vendor_id": vendor, "amount": amount, "invoice_date": inv_date.isoformat(),
                                       "po_no": po_no, "status": "RECEIVED", "contract_checked": False})
        if has_po:
            store.put("purchase_orders", po_no, {"po_no": po_no, "vendor_id": vendor, "amount": po_amount, "contract_no": contract_no})
            store.put("goods_receipts", po_no, {"po_no": po_no, "received_amount": received, "received_at": (today - timedelta(days=12)).isoformat()})
        drive_write(w.cfg["paths"]["invoice_pdf"].format(vendor_id=vendor, invoice_id=inv_id), pdf_bytes([
            "INVOICE", f"Invoice No: {inv_id}", f"PO No: {po_no}", f"Vendor ID: {vendor}", f"Invoice Date: {inv_date.isoformat()}",
            f"Amount (JPY, tax incl.): {yen(pdf_amount)}"]))
        drive_write(w.cfg["paths"]["contract"].format(vendor_id=vendor, contract_no=contract_no), docx_bytes([
            "基本取引契約書", f"契約番号: {contract_no}", f"契約開始日: {c_start.isoformat()}", f"契約終了日: {c_end.isoformat()}",
            f"契約上限額: {yen(amount * 3)}"]))


# ----------------------------------------------------------------------- LEAVE
def gen_leave(w):
    lv, rng, today = w.cfg["leave"], w.rng, w.today
    for d in DEPTS:
        store.put("departments", d, {"dept": d, "headcount": 200, "head_name": f"{d[:2]}部長",
                                      "head_email": f"head.{DEPTS.index(d) + 1}@company.local"})
    per = max(1, w.n // 5)
    plans = {
        "年次有給休暇": {"ok": 6, "low_balance": 1, "low_attendance": 1, "team_full": 1, "pending_manager": 1},
        "半日有給申請": {"ok": 7, "half_cap": 1, "low_balance": 1, "pending_manager": 1},
        "特別休暇（慶弔）": {"ok": 6, "over_days": 2, "no_proof": 1, "proof_mismatch": 1},
        "代休申請": {"ok": 6, "expired_record": 2, "no_record": 2},
        "フレックス変更申請": {"ok": 6, "core_violation": 2, "too_many": 1, "pending_manager": 1}}
    events = [("結婚", "本人"), ("忌引", "配偶者"), ("忌引", "父母"), ("忌引", "祖父母"), ("忌引", "兄弟姉妹")]
    attendance = {}                                    # "YYYY-MM" -> rows
    for lt, cnt in plans.items():
        cnt = scale(cnt, per) if per != 10 else cnt
        lst = [s for s, k in cnt.items() for _ in range(k)]
        rng.shuffle(lst)
        for scen in lst:
            emp = w.employee()
            d = date(2026, 7, rng.randint(7, 31))
            while d.weekday() >= 5:
                d += timedelta(days=1)
            ds = d.isoformat()
            req = {"emp_id": emp["emp_id"], "leave_type": lt, "date": ds, "dept": emp["dept"], "days": 1.0,
                   "submitted_at": (today - timedelta(days=rng.randint(1, 4))).isoformat(), "manager_approved": scen != "pending_manager"}
            bal = {"emp_id": emp["emp_id"], "annual_days": round(rng.uniform(6, 18), 1), "special_days": 5.0,
                   "half_days_used": rng.randint(0, 4), "attendance_rate_prev_year": round(rng.uniform(0.9, 1.0), 2)}
            first = "APPROVED" if scen == "ok" else "NEEDS_REVIEW" if scen == "pending_manager" else "REJECTED"
            row = w.add("leave_request", {"leave_type": lt, "date": ds}, scen, first, approvable=(scen == "pending_manager"))
            req["case_id"] = row["case_id"]
            if lt == "年次有給休暇":
                req["days"] = rng.choice([1.0, 1.0, 2.0])
                if scen == "low_balance": bal["annual_days"] = 0.5
                if scen == "low_attendance": bal["attendance_rate_prev_year"] = 0.72
                if scen == "team_full": store.put("team_absences", f"{emp['dept']}:{ds}", {"absent": 60})
            elif lt == "半日有給申請":
                req["days"] = 0.5
                if scen == "half_cap": bal["half_days_used"] = lv["half_day_max_per_year"]
                if scen == "low_balance": bal["annual_days"] = 0.0
            elif lt == "特別休暇（慶弔）":
                kind, rel = rng.choice(events)
                key = kind if kind == "結婚" else f"{kind}_{rel}"
                allowed = lv["special_leave_days"][key]
                req["days"] = float(allowed + 2 if scen == "over_days" else rng.randint(1, allowed))
                req["event"] = {"kind": kind, "relation": rel}
                if scen != "no_proof":
                    rel_doc = rel if scen != "proof_mismatch" else next(r for r in ["配偶者", "父母", "祖父母", "兄弟姉妹", "本人"] if r != rel)
                    drive_write(w.cfg["paths"]["leave_proof"].format(emp_id=emp["emp_id"], case_id=row["case_id"]), docx_bytes([
                        "慶弔証明書類", f"事由: {kind}", f"続柄: {rel_doc}", f"発生日: {(d - timedelta(days=2)).isoformat()}"]))
            elif lt == "代休申請":
                if scen != "no_record":
                    worked = today - timedelta(days=rng.randint(70, 110) if scen == "expired_record" else rng.randint(8, 40))
                    attendance.setdefault(worked.strftime("%Y-%m"), []).append([emp["emp_id"], worked.isoformat(), 8.0, "休日出勤"])
                attendance.setdefault(today.strftime("%Y-%m"), []).append([emp["emp_id"], (today - timedelta(days=3)).isoformat(), 8.0, "通常勤務"])
            elif lt == "フレックス変更申請":
                req["days"] = 0.0
                start = "12:30" if scen == "core_violation" else rng.choice(["08:00", "09:00", "10:00"])
                req["flex"] = {"new_start": start, "new_end": "20:30" if scen == "core_violation" else f"{int(start[:2]) + 9:02d}:00"}
                if scen == "too_many": store.put("flex_changes", f"{emp['emp_id']}:{ds[:7]}", {"count": lv["flex_max_changes_per_month"]})
            store.put("leave_requests", row["case_id"], req)
            store.put("leave_balances", emp["emp_id"], bal)
    for month, rows in attendance.items():
        drive_write(f"{w.cfg['paths']['attendance']}{month}.xlsx", xlsx_bytes(["emp_id", "work_date", "hours", "day_type"], rows))


# --------------------------------------------------------------------- EXPENSE
def gen_expense(w):
    ex, rng, today = w.cfg["expense"], w.rng, w.today
    counts = scale({"ok": 26, "no_receipt": 3, "stale": 3, "duplicate_receipt": 3, "amount_mismatch": 3, "no_pre_approval": 2,
                    "over_head": 2, "pending_manager": 3, "over_max": 2, "no_reg_no": 3}, w.n)
    cats = list(ex["limits"])
    for scen in w.plan(counts):
        if scen == "no_pre_approval":
            cat = rng.choice(["出張旅費", "研修費"])
        elif scen == "over_head":
            cat = "接待交際費"
        else:
            cat = rng.choice(cats)
        lim = ex["limits"][cat]
        if scen == "over_max":
            amt = int(lim["max"] * rng.uniform(1.1, 1.6))
        elif scen == "pending_manager":
            amt = rng.randint(lim["auto"] + 1000, lim["max"])
        elif scen == "over_head":
            amt = rng.randint(30000, lim["auto"])
        elif scen == "ok" and rng.random() < 0.2:
            amt = rng.randint(lim["auto"] + 1000, lim["max"])                 # allowed: manager approved
        else:
            amt = rng.randint(3500, lim["auto"])
        emp = w.employee()
        claim_id, rcpt = f"EXP-{rng.randint(10000, 99999)}", f"RC-{rng.randint(100000, 999999)}"
        rdate = today - timedelta(days=rng.randint(90, 140) if scen == "stale" else rng.randint(3, 40))
        first = {"ok": "APPROVED", "no_reg_no": "APPROVED", "no_receipt": "REJECTED", "stale": "REJECTED", "duplicate_receipt": "REJECTED",
                 "over_max": "REJECTED"}.get(scen, "NEEDS_REVIEW")
        row = w.add("expense_reimbursement", {"amount": amt, "expense_category": cat}, scen, first,
                    approvable=scen in ("no_pre_approval", "over_head", "pending_manager"))
        attendees = None
        if cat == "接待交際費":
            per = ex["entertainment_per_head"]
            attendees = max(1, amt // per - 2) if scen == "over_head" else amt // per + rng.randint(2, 4)
        store.put("expense_claims", row["case_id"], {
            "case_id": row["case_id"], "claim_id": claim_id, "emp_id": emp["emp_id"], "dept": emp["dept"], "category": cat, "amount": amt,
            "submitted_at": today.isoformat(), "status": "SUBMITTED", "attendees": attendees,
            "manager_approved": scen != "pending_manager",
            "pre_approval_id": None if scen == "no_pre_approval" or cat not in ("出張旅費", "研修費") else f"PRE-{rng.randint(1000, 9999)}"})
        if scen == "duplicate_receipt":
            store.put("used_receipts", rcpt, {"used": True, "case_id": "PREV-CLAIM"})
        if scen != "no_receipt":
            total = amt + rng.choice([1, 100, 350]) if scen == "amount_mismatch" else amt
            lines = ["RECEIPT", f"Receipt No: {rcpt}", f"Date: {rdate.isoformat()}", f"Merchant: MERCHANT-{rng.randint(100, 999)}",
                     f"Total (JPY): {yen(total)}"]
            if scen != "no_reg_no":
                lines.append(f"Registration No: T{rng.randint(10**12, 10**13 - 1)}")
            drive_write(w.cfg["paths"]["receipt"].format(emp_id=emp["emp_id"], yyyy_mm=today.strftime("%Y_%m"), claim_id=claim_id), pdf_bytes(lines))


# ------------------------------------------------------------------- INVENTORY
def gen_inventory(w):
    rng, today = w.rng, w.today
    codes = [f"BATCH-W{i}" for i in range(1, 9)]
    names = ["制御基板ユニットA", "電源モジュールB", "センサーC", "ケーブルセットD", "筐体パネルE", "ファンユニットF", "コネクタG", "ブラケットH"]
    for c, n in zip(codes, names):
        store.put("stock", c, {"item_code": c, "name": n, "on_hand": 5000, "reserved": 500, "safety_stock": 1000, "uom": "個"})
    store.put("stock", "BATCH-W9", {"item_code": "BATCH-W9", "name": "特注部品I", "on_hand": 500, "reserved": 50, "safety_stock": 480, "uom": "個"})
    counts = scale({"outbound_ok": 21, "safety_alert": 1, "inbound_ok": 6, "scrap_ok": 4, "count_ok": 5, "outbound_insufficient": 4,
                    "scrap_no_reason": 2, "name_mismatch": 2, "large_scrap": 3, "count_unsupported": 2}, w.n)
    large_items = iter(["BATCH-W1", "BATCH-W2", "BATCH-W3"] * 3)
    for scen in w.plan(counts):
        code = "BATCH-W9" if scen == "safety_alert" else next(large_items) if scen == "large_scrap" else rng.choice(codes)
        typ = {"outbound_ok": "OUTBOUND", "safety_alert": "OUTBOUND", "inbound_ok": "INBOUND", "scrap_ok": "SCRAP", "count_ok": "COUNT_CORRECTION",
               "outbound_insufficient": "OUTBOUND", "scrap_no_reason": "SCRAP", "name_mismatch": "OUTBOUND", "large_scrap": "SCRAP",
               "count_unsupported": "COUNT_CORRECTION"}[scen]
        qty = {"outbound_insufficient": rng.randint(8000, 9500), "large_scrap": 2250, "safety_alert": 60}.get(scen, rng.randint(10, 120))
        delta = qty if typ == "INBOUND" else -qty
        if typ == "COUNT_CORRECTION":
            delta = rng.choice([-1, 1]) * rng.randint(5, 40)
            qty = abs(delta)
        st = store.get("stock", code)
        sheet_name = st["name"] + ("X" if scen == "name_mismatch" else "")
        first = {"outbound_insufficient": "REJECTED", "scrap_no_reason": "REJECTED", "name_mismatch": "NEEDS_REVIEW", "large_scrap": "NEEDS_REVIEW",
                 "count_unsupported": "NEEDS_REVIEW"}.get(scen, "APPROVED")
        row = w.add("inventory_adjustment", {"amount": qty, "item_code": code, "item_name": sheet_name}, scen, first, approvable=scen == "large_scrap")
        reason = "" if scen == "scrap_no_reason" else {"OUTBOUND": "PICKING", "INBOUND": "GRN", "SCRAP": "DAMAGED", "COUNT_CORRECTION": "CYCLE_COUNT"}[typ]
        req_no = f"ADJ-{rng.randint(10000, 99999)}"
        store.put("adjustment_requests", row["case_id"], {"case_id": row["case_id"], "request_no": req_no, "item_code": code, "type": typ,
                  "qty": qty, "delta": delta, "reason_code": reason, "requested_by": f"E{rng.randint(10000, 99999)}"})
        if typ == "COUNT_CORRECTION":
            counted = st["on_hand"] + (delta if scen == "count_ok" else delta + rng.choice([-9, 9]))
            drive_write(w.cfg["paths"]["count_sheet"].format(item_code=code, request_no=req_no),
                        xlsx_bytes(["item_code", "system_qty", "counted_qty", "counted_by"], [[code, st["on_hand"], counted, "warehouse-team"]]))


# ---------------------------------------------------------------------- BUDGET
def gen_budget(w):
    rng, today, cfg = w.rng, w.today, w.cfg
    counts = scale({"ok": 25, "var_5_10": 6, "over_10": 7, "under_10": 5, "ledger_mismatch": 4, "sheet_var_wrong": 3}, w.n)
    gl, used = [], set()
    for scen in w.plan(counts):
        dept = rng.choice(DEPTS)
        budget = rng.randrange(3_000_000, 30_000_000, 1000)
        while (dept, budget) in used:
            budget += 1000
        used.add((dept, budget))
        var = {"ok": rng.uniform(-4.5, 4.5), "ledger_mismatch": rng.uniform(-3, 3), "sheet_var_wrong": rng.uniform(-3, 3),
               "var_5_10": rng.choice([-1, 1]) * rng.uniform(5.4, 9.5), "over_10": rng.uniform(10.6, 25),
               "under_10": -rng.uniform(10.6, 25)}[scen]
        actual = int(budget * (1 + var / 100))
        sheet_var = round((actual - budget) / budget * 100, 1)
        ledger_actual = actual + int(budget * 0.03) if scen == "ledger_mismatch" else actual
        if scen == "sheet_var_wrong":
            sheet_var = round(sheet_var + 2.0, 1)
        first = "APPROVED" if scen == "ok" else "NEEDS_REVIEW"
        w.add("budget_variance", {"department": dept, "budget": budget, "actual": actual, "variance_pct": sheet_var}, scen, first,
              approvable=scen in ("var_5_10", "over_10", "under_10"))
        gl.append([dept, budget, ledger_actual])
    drive_write(cfg["paths"]["gl"].format(period=cfg["budget_period"]), xlsx_bytes(["department", "budget", "actual"], gl))


# ---------------------------------------------------------------------- ORDERS
def gen_orders(w):
    rng, today, cfg = w.rng, w.today, w.cfg
    o = cfg["orders"]
    vendors = [f"VND-{i:02d}" for i in range(1, 13)]
    for v in vendors:
        store.put("scm_vendors", v, {"vendor_id": v, "name": f"{v} Supply Co.", "status": "ACTIVE", "email": f"sales@{v.lower()}.example.local"})
        store.put("blanket_contracts", v, {"vendor_id": v, "annual_limit": 10**11, "used": 0})
    store.put("scm_vendors", "VND-S1", {"vendor_id": "VND-S1", "name": "Suspended Supply Co.", "status": "SUSPENDED", "email": "sales@vnd-s1.example.local"})
    store.put("blanket_contracts", "VND-S1", {"vendor_id": "VND-S1", "annual_limit": 10**11, "used": 0})
    base = {}
    price_lists = {}
    counts = scale({"ok": 28, "price_up": 4, "expired_quote": 3, "vendor_suspended": 3, "over_blanket": 3, "no_justification": 3,
                    "approval_missing": 3, "quote_missing": 1, "price_list_conflict": 2}, w.n)
    types = ["年間契約", "定期発注", "スポット発注", "緊急発注"]
    k = 0
    for scen in w.plan(counts):
        if scen in ("over_blanket", "price_list_conflict"):
            ct = "年間契約"
        elif scen == "no_justification":
            ct = "緊急発注"
        elif scen == "price_up":
            ct = rng.choice(types[1:])
        else:
            ct = types[k % 4]; k += 1
        item = rng.choice(ITEMS)
        qty = rng.randint(5, 500)
        vendor = "VND-S1" if scen == "vendor_suspended" else rng.choice(vendors)
        if scen == "over_blanket":
            vendor = f"VND-L{rng.randint(100, 999)}"
            store.put("scm_vendors", vendor, {"vendor_id": vendor, "name": f"{vendor} Supply Co.", "status": "ACTIVE", "email": f"sales@{vendor.lower()}.example.local"})
        if ct == "年間契約":
            unit = base.setdefault((vendor, item), rng.randint(300, 60000))
        else:
            unit = rng.randint(300, 60000)
        if scen == "approval_missing":
            qty = max(qty, 1_200_000 // unit + 1)
        total = qty * unit
        quote_unit = unit / 1.2 if scen == "price_up" else unit
        if scen == "over_blanket":
            store.put("blanket_contracts", vendor, {"vendor_id": vendor, "annual_limit": int(total * 0.5), "used": 0})
        level = "director" if total >= o["approval_levels"]["director"] else "manager" if total >= o["approval_levels"]["manager"] else None
        if scen == "approval_missing":
            level = None
        first = {"ok": "APPROVED", "expired_quote": "REJECTED", "vendor_suspended": "REJECTED"}.get(scen, "NEEDS_REVIEW")
        row = w.add("order_management", {"contract_type": ct, "item": item, "quantity": qty, "total": total,
                                         "urgency": "緊急" if ct == "緊急発注" else "通常"}, scen, first,
                    approvable=scen in ("price_up", "no_justification", "approval_missing"))
        quote_no = f"Q-{rng.randint(100000, 999999)}"
        store.put("requisitions", row["case_id"], {"case_id": row["case_id"], "vendor_id": vendor, "item": item, "quote_no": quote_no,
                  "requester_dept": rng.choice(DEPTS), "approved_level": level,
                  "justification": None if scen == "no_justification" else "生産ライン停止回避のため"})
        valid = today - timedelta(days=5) if scen == "expired_quote" else today + timedelta(days=30)
        if scen != "quote_missing":
            drive_write(cfg["paths"]["quote"].format(vendor_id=vendor, quote_no=quote_no), pdf_bytes([
                "QUOTATION", f"Quote No: {quote_no}", f"Vendor ID: {vendor}", f"Quantity: {qty}",
                f"Unit Price (JPY): {quote_unit * rng.uniform(0.997, 1.003) if scen != 'price_up' else quote_unit:,.2f}",
                f"Valid Until: {valid.isoformat()}"]))
        if ct == "年間契約":
            price_lists.setdefault(vendor, {})[item] = unit * 1.25 if scen == "price_list_conflict" else unit
    for v, items in price_lists.items():
        drive_write(cfg["paths"]["price_list"].format(vendor_id=v), xlsx_bytes(["item", "contract_unit_price"], [[i, p] for i, p in items.items()]))


def build(per_process=50, seed=2026, out=None):
    """Create a fresh test world (sheet + systems + documents). Returns a small info dict."""
    cfg = load_config()
    store.clear_all()
    for stale in ("workflow_state.json", "audit_log.jsonl", "mailbox.html", "dashboard.html"):      # start from a clean run history
        (RUNTIME / stale).unlink(missing_ok=True)
    shutil.rmtree(RUNTIME / "exports", ignore_errors=True)
    if DRIVE.exists():
        shutil.rmtree(DRIVE)
    DRIVE.mkdir(parents=True)
    w = World(seed, cfg, per_process)
    gen_leave(w)                                       # creates departments first
    for g in (gen_onboarding, gen_invoice, gen_expense, gen_inventory, gen_budget, gen_orders):
        g(w)
    w.rng.shuffle(w.rows)
    out = Path(out or ROOT / "data" / "input" / "payroll_cases_test.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    for old in out.parent.glob("*.xlsx"):              # only one dummy sheet exists at a time
        try:
            old.unlink()
        except OSError:
            pass
    wb = Workbook()
    ws = wb.active
    ws.title = "cases"
    ws.append(COLS)
    for r in w.rows:
        ws.append([r[c] for c in COLS])
    wb.save(out)
    (out.parent / "expected_results.json").write_text(json.dumps(w.expected, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    info = {"sheet": out.name, "path": str(out), "rows": len(w.rows), "seed": seed, "per_process": per_process,
            "by_process": dict(Counter(r["category_type"] for r in w.rows)),
            "expected_first_run": dict(Counter(v["first"] for v in w.expected.values())),
            "files_on_drive": sum(1 for f in DRIVE.rglob("*") if f.is_file())}
    (out.parent / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-process", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    info = build(a.per_process, a.seed, a.out)
    print(f"Wrote {info['rows']} rows -> {info['path']}")
    print(info["by_process"])
    print("expected first-run:", info["expected_first_run"])
    print("files on shared drive:", info["files_on_drive"])


if __name__ == "__main__":
    main()
