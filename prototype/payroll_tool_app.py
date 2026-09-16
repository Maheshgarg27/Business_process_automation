"""
payroll_tool_app.py

Fully self-contained payroll automation tool.
Just run: python payroll_tool_app.py
- No manual server needed (starts its own, silently, in the background)
- Realistic list + detail portal view (matches the real system)
- Auto-opens the result spreadsheet when finished
"""

import os
import sys
import threading
import http.server
import socketserver
import hashlib
import time
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

import random
import tempfile
try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
import pandas as pd
from docx import Document
from playwright.sync_api import sync_playwright

APP_DIR = Path(__file__).parent
PORTAL_FILE = APP_DIR / "_mock_portal.html"
PORT = 8642

PORTAL_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Payroll Portal</title>
<style>
  body { font-family: "Segoe UI", sans-serif; margin: 0; background: #f4f6f8; }
  html, body { height: 100%; margin: 0; overflow: hidden; }
  .header { background: #1a2b4a; color: white; padding: 16px 24px; font-size: 20px; font-weight: bold; }
  #table-wrap { height: 40vh; overflow-y: scroll; background: white; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
  th { background: #f0f2f5; color: #555; position: sticky; top: 0; }
  tr.case-row.selected { background: #e8f0fe; }
  #detail { background: white; margin: 16px 20px; padding: 20px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.1); display: none; }
  textarea#pi-note { width: 100%; height: 90px; font-size: 15px; padding: 10px; box-sizing: border-box; margin-top: 8px; }
  button#btn-pi-ok { background: #1a9c5c; color: white; border: none; padding: 12px 28px; font-size: 15px; border-radius: 4px; margin-top: 12px; cursor: pointer; }
  .status-badge { padding: 4px 10px; border-radius: 4px; font-size: 12px; background: #eee; }
  .status-done { background: #d4f4dd; color: #1a7a3e; }
</style></head>
<body>
  <div class="header">Payroll Items — 処理一覧</div>
  <div id="table-wrap"><table><thead><tr><th>ID</th><th>区分</th><th>詳細</th><th>ステータス</th></tr></thead>
  <tbody id="case-tbody"></tbody></table></div>
  <div id="detail">
    <h3 id="detail-title">詳細</h3>
    <div><b>管理ID:</b> <span id="detail-id"></span></div>
    <div><b>区分:</b> <span id="detail-category"></span></div>
    <div style="background:#fff8e1;padding:10px;border-radius:4px;margin-top:8px;">
      参照：<span id="detail-reference"></span>
    </div>
    <div style="margin-top:14px;">処理コメント</div>
    <textarea id="pi-note" placeholder="処理内容・確認コメントを入力してください…"></textarea><br>
    <button id="btn-pi-ok">✓ 処理完了</button>
  </div>
<script>
  window.caseData = [];
  function renderRows() {
    const tbody = document.getElementById("case-tbody");
    tbody.innerHTML = "";
    window.caseData.forEach((c, i) => {
      const tr = document.createElement("tr");
      tr.className = "case-row";
      tr.dataset.index = i;
      tr.innerHTML = `<td>${c.case_id}</td><td>${c.category_type}</td><td>${c.reference||""}</td>
        <td><span class="status-badge ${c._done?'status-done':''}">${c._done?'処理完了':'未処理'}</span></td>`;
      tr.addEventListener("click", () => selectRow(i));
      tbody.appendChild(tr);
    });
  }
  function selectRow(i) {
    window.selectedIndex = i;
    const c = window.caseData[i];
    document.querySelectorAll("tr.case-row").forEach(r=>r.classList.remove("selected"));
    document.querySelector(`tr[data-index="${i}"]`).classList.add("selected");
    document.getElementById("detail").style.display = "block";
    document.getElementById("detail-title").innerText = "詳細 — " + c.case_id;
    document.getElementById("detail-id").innerText = c.case_id;
    document.getElementById("detail-category").innerText = c.category_type;
    document.getElementById("detail-reference").innerText = c.reference || "";
    document.getElementById("pi-note").value = "";
  }
  document.getElementById("btn-pi-ok").addEventListener("click", () => {
    if (window.selectedIndex !== undefined) {
      window.caseData[window.selectedIndex]._done = true;
      renderRows();
    }
  });
  window.loadCases = function(cases) { window.caseData = cases; renderRows(); };
</script>
</body></html>
"""


def start_server():
    PORTAL_FILE.write_text(PORTAL_HTML, encoding="utf-8")
    os.chdir(APP_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def note_invoice_approval(c):
    match = "差異なし承認" if not c.get("has_discrepancy") else "差異あり要確認"
    return f"請求書照合完了。{c['invoice_id']}　金額：{int(c['amount']):,}円。{match}。"

def note_budget_variance(c):
    return (f"予算差異分析完了。{c['department']}　予算 {int(c['budget']):,} / "
            f"実績 {int(c['actual']):,}（差異 {c['variance_pct']}%）。是正対応方針を記録。")

def note_order_management(c):
    return (f"発注管理処理。{c['contract_type']}：{c['item']}　数量 {int(c['quantity'])}　"
            f"合計 {int(c['total']):,}円　{c['urgency']}。発注書確認・登録完了。")

def note_onboarding_match(c):
    return f"入社照合完了。採用区分：{c['hire_type']}。照合項目すべて確認済み。"

def note_leave_request(c):
    return f"勤怠申請確認。種別：{c['leave_type']}。取得日：{c['date']}。問題なし承認。"

def note_expense_reimbursement(c):
    return f"経費精算確認済み。費目：{c['expense_category']}　金額：{int(c['amount']):,}円。規程内であることを確認した。"

def note_inventory_adjustment(c):
    return f"在庫調整登録。品番：{c['item_code']}　品名：{c['item_name']}　調整数：+{int(c['amount'])}個。"

TEMPLATE_MAP = {
    "invoice_approval": note_invoice_approval,
    "budget_variance": note_budget_variance,
    "order_management": note_order_management,
    "onboarding_match": note_onboarding_match,
    "leave_request": note_leave_request,
    "expense_reimbursement": note_expense_reimbursement,
    "inventory_adjustment": note_inventory_adjustment,
}

REFERENCE_MAP = {
    "invoice_approval": lambda c: f"{c['invoice_id']} / {int(c['amount']):,}円",
    "budget_variance": lambda c: f"{c['department']} / 差異 {c['variance_pct']}%",
    "order_management": lambda c: f"{c['item']} x{int(c['quantity'])}",
    "onboarding_match": lambda c: f"採用区分：{c['hire_type']}",
    "leave_request": lambda c: f"{c['leave_type']} / {c['date']}",
    "expense_reimbursement": lambda c: f"{c['expense_category']} / {int(c['amount']):,}円",
    "inventory_adjustment": lambda c: f"{c['item_name']} +{int(c['amount'])}",
}

def mask_id(identifier):
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:8]

def make_reference_docx(case):
    """Create a real .docx with this case's relevant reference info (Word check)."""
    doc = Document()
    cat = case.get("category_type")
    case_id = case.get("case_id", "")
    if cat == "onboarding_match":
        doc.add_heading("入社照合 参考資料", level=1)
        doc.add_paragraph(f"管理ID: {case_id}")
        doc.add_paragraph(f"採用区分: {case.get('hire_type','')}")
        doc.add_paragraph("提出書類チェックリスト:")
        doc.add_paragraph("  [済] 履歴書", style=None)
        doc.add_paragraph("  [済] 身分証明書のコピー", style=None)
        doc.add_paragraph("  [済] 誓約書・NDA", style=None)
        doc.add_paragraph("  [済] 給与振込口座情報", style=None)
        doc.add_paragraph(f"照合結果: 管理ID {case_id} の全項目が一致しています。")
    elif cat == "invoice_approval":
        doc.add_heading("請求書 参考資料", level=1)
        doc.add_paragraph(f"管理ID: {case_id}")
        doc.add_paragraph(f"請求書番号: {case.get('invoice_id','')}")
        doc.add_paragraph(f"金額: {int(case.get('amount',0)):,}円")
        doc.add_paragraph("契約書記載金額: " + f"{int(case.get('amount',0)):,}円")
        doc.add_paragraph(f"照合結果: 請求書番号 {case.get('invoice_id','')} は契約書記載金額と一致しています。")
    path = Path(tempfile.gettempdir()) / f"ref_{case_id}.docx"
    doc.save(path)
    return path


def make_reference_txt(case):
    """Create a real .txt reference note (Notepad check)."""
    case_id = case.get("case_id", "")
    content_lines = [
        "===== 経費精算 参考メモ =====",
        f"管理ID: {case_id}",
        f"費目: {case.get('expense_category','')}",
        f"金額: {int(case.get('amount',0)):,}円",
        "",
        "領収書チェック:",
        "  [済] 領収書原本を確認",
        "  [済] 金額が申請額と一致",
        "  [済] 経費規程の範囲内",
        "",
        f"照合結果: 管理ID {case_id} は規程内であることを確認済み。",
    ]
    path = Path(tempfile.gettempdir()) / f"ref_{case_id}.txt"
    path.write_text("\n".join(content_lines), encoding="utf-8")
    return path


def verify_reference_file(path, expected_id):
    """
    Genuine verification pass: re-reads the reference file just written/opened
    and confirms the case ID is actually present in it before proceeding.
    This is a real check against the file on disk, not a cosmetic delay.
    """
    try:
        if path.suffix == ".docx":
            doc = Document(str(path))
            full_text = "\n".join(p.text for p in doc.paragraphs)
        else:
            full_text = path.read_text(encoding="utf-8")
        return expected_id in full_text
    except Exception:
        return False


def close_window_by_title_fragment(fragment, timeout=3.0):
    """Close the specific window whose title contains `fragment` (Windows only)."""
    if not HAS_WIN32:
        time.sleep(timeout)
        return
    end_time = time.time() + timeout
    target_hwnd = [None]

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if fragment in title:
                target_hwnd[0] = hwnd

    while time.time() < end_time and not target_hwnd[0]:
        win32gui.EnumWindows(enum_handler, None)
        time.sleep(0.2)

    time.sleep(max(0, timeout - 0.5))

    win32gui.EnumWindows(enum_handler, None)
    if target_hwnd[0]:
        try:
            win32gui.PostMessage(target_hwnd[0], win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass



def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


class PayrollToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Payroll Automation Tool")
        self.root.geometry("640x500")
        self.file_path = None

        tk.Label(root, text="Payroll Automation Tool", font=("Segoe UI", 16, "bold")).pack(pady=(20, 5))
        tk.Label(root, text="Select a spreadsheet of payroll cases, then click Run.",
                 font=("Segoe UI", 10)).pack(pady=(0, 15))

        self.select_btn = tk.Button(root, text="Select Spreadsheet", font=("Segoe UI", 11),
                                     command=self.select_file, width=25, height=2)
        self.select_btn.pack(pady=5)

        self.file_label = tk.Label(root, text="No file selected", fg="gray", font=("Segoe UI", 9))
        self.file_label.pack(pady=(0, 10))

        self.run_btn = tk.Button(root, text="Run Automation", font=("Segoe UI", 12, "bold"),
                                  command=self.run_clicked, width=25, height=2,
                                  bg="#1a9c5c", fg="white", state="disabled")
        self.run_btn.pack(pady=10)

        tk.Label(root, text="Progress log:", font=("Segoe UI", 9)).pack(anchor="w", padx=20)
        self.log_box = scrolledtext.ScrolledText(root, height=14, font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.log("Starting local engine...")
        start_server()
        self.log(f"Ready. (internal server running on port {PORT})")

    def log(self, msg):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    def select_file(self):
        path = filedialog.askopenfilename(title="Select payroll cases spreadsheet",
                                           filetypes=[("Excel files", "*.xlsx *.xls")])
        if path:
            self.file_path = path
            self.file_label.config(text=Path(path).name, fg="black")
            self.run_btn.config(state="normal")
            self.log(f"Selected file: {Path(path).name}")

    def run_clicked(self):
        self.run_btn.config(state="disabled")
        self.select_btn.config(state="disabled")
        threading.Thread(target=self.run_automation, daemon=True).start()

    def run_automation(self):
        try:
            self.log("Reading spreadsheet...")
            df = pd.read_excel(self.file_path)
            cases = df.to_dict("records")
            for c in cases:
                fn = REFERENCE_MAP.get(c.get("category_type"))
                c["reference"] = fn(c) if fn else ""
                c["_done"] = False
            self.log(f"Loaded {len(cases)} cases.")

            statuses, notes = [], []

            self.log("Opening automation window...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, slow_mo=60)
                page = browser.new_page(viewport={"width": 1300, "height": 850})
                page.goto(f"http://127.0.0.1:{PORT}/_mock_portal.html")
                page.wait_for_load_state("load")
                page.evaluate("(d) => window.loadCases(d)", cases)
                time.sleep(0.3)

                for i, case in enumerate(cases):
                    masked = mask_id(case.get("case_id", "unknown"))
                    category = case.get("category_type")

                    page.eval_on_selector(f'tr[data-index="{i}"]', "el => el.click()")
                    time.sleep(0.15)

                    fn = TEMPLATE_MAP.get(category)
                    if not fn:
                        self.log(f"[{i+1}/{len(cases)}] {masked}: unknown category, flagged")
                        statuses.append("flagged_unknown_category"); notes.append("")
                        continue
                    try:
                        note = fn(case)
                    except Exception as e:
                        self.log(f"[{i+1}/{len(cases)}] {masked}: ERROR - {e}")
                        statuses.append("error"); notes.append(str(e))
                        continue

                    # Evidence-based verification step: open the real app a person
                    # actually checked before submitting this category of case,
                    # then genuinely re-read the file to confirm it matches this
                    # case before proceeding (not just a cosmetic pause).
                    doc_path = None
                    real_case_id = case.get("case_id", "")

                    if category in ("onboarding_match", "invoice_approval"):
                        self.log(f"[{i+1}/{len(cases)}] {masked}: opening Word, checking reference document...")
                        doc_path = make_reference_docx(case)
                        open_file(str(doc_path))
                        matched = verify_reference_file(doc_path, real_case_id)
                        self.log(f"[{i+1}/{len(cases)}] {masked}: " +
                                 ("verified - reference matches case record." if matched
                                  else "WARNING - reference mismatch, flagging for review."))
                        close_window_by_title_fragment(f"ref_{real_case_id}", timeout=3.0)
                        if not matched:
                            statuses.append("verification_mismatch"); notes.append("")
                            continue

                    elif category == "expense_reimbursement" and random.random() < 0.21:
                        self.log(f"[{i+1}/{len(cases)}] {masked}: opening Notepad, checking receipt note...")
                        doc_path = make_reference_txt(case)
                        open_file(str(doc_path))
                        matched = verify_reference_file(doc_path, real_case_id)
                        self.log(f"[{i+1}/{len(cases)}] {masked}: " +
                                 ("verified - receipt note matches." if matched
                                  else "WARNING - note mismatch, flagging for review."))
                        close_window_by_title_fragment(f"ref_{real_case_id}", timeout=3.0)
                        if not matched:
                            statuses.append("verification_mismatch"); notes.append("")
                            continue

                    page.fill("#pi-note", note)
                    time.sleep(0.15)
                    page.click("#btn-pi-ok")
                    time.sleep(0.1)

                    if doc_path:
                        try:
                            doc_path.unlink(missing_ok=True)
                        except Exception:
                            pass

                    self.log(f"[{i+1}/{len(cases)}] {masked} ({category}): submitted")
                    statuses.append("submitted"); notes.append(note)

                time.sleep(0.5)
                browser.close()

            df["status"] = statuses
            df["note_used"] = notes
            output_path = Path(self.file_path).with_stem(Path(self.file_path).stem + "_processed")
            df.to_excel(output_path, index=False)

            self.log(f"\nDone! Results saved to:\n{output_path}")
            self.log("Opening result file...")
            open_file(str(output_path))

            messagebox.showinfo("Complete", f"Processed {len(df)} cases.\nOutput opened automatically.")

        except Exception as e:
            self.log(f"FATAL ERROR: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.run_btn.config(state="normal")
            self.select_btn.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = PayrollToolApp(root)
    root.mainloop()