"""
PAYROLL PROCESS AUTOMATION - entry point

    python run_pipeline.py --input data/input/payroll_cases_test.xlsx

What happens:
  1. back up the workbook, start/verify the enterprise API connections
  2. RESUME cases that were waiting for a human approval (reads approver replies, sends reminders)
  3. for every new row: route by category_type -> process engine -> decision -> actions -> write result to the sheet
  4. publish reports: run summary, payroll adjustment export, dashboard, mailbox view
Nothing is opened on screen; all systems are reached through APIs.
"""
import argparse, logging, subprocess, sys, time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
from core import audit, excel_io
from core.api_client import Api
from core.common import ROOT, RUNTIME, Context, Result, load_config, now_iso, run_date
from core.workflow import Workflow
from processors import budget, expense, inventory, invoice, leave, onboarding, orders
from processors.base import notify

ROUTES = {"onboarding_match": onboarding.process, "invoice_approval": invoice.process, "leave_request": leave.process,
          "expense_reimbursement": expense.process, "inventory_adjustment": inventory.process,
          "budget_variance": budget.process, "order_management": orders.process}
log = logging.getLogger("pipeline")


def ensure_services(cfg, api):
    """Make sure the enterprise APIs answer; start the local simulated systems if configured to."""
    if api.healthy():
        return None
    if not cfg["api"].get("autostart_services"):
        sys.exit(f"API {cfg['api']['base_url']} is not reachable")
    port = urlparse(cfg["api"]["base_url"]).port or 8765
    log.info("starting enterprise systems on port %s", port)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "services.server:app", "--host", "127.0.0.1", "--port", str(port),
                             "--log-level", "warning"], cwd=ROOT, stdout=open(RUNTIME / "services.log", "a"), stderr=subprocess.STDOUT)
    for _ in range(60):
        if api.healthy():
            return proc
        time.sleep(0.2)
    proc.terminate()
    sys.exit("could not start enterprise systems (see runtime/services.log)")


def ensure_writable(path):
    """Fail early (before any mail is sent) if the workbook is locked, e.g. still open in Excel."""
    try:
        with open(path, "ab"):
            pass
    except OSError as e:
        sys.exit(f"Cannot write to {path}: {e.strerror}. Close the file in Excel (or any viewer) and run again.")


class Run:
    def __init__(self, args, cfg, api):
        self.cfg, self.api, self.args = cfg, api, args
        self.run_id = "RUN-" + time.strftime("%Y%m%d-%H%M%S")
        cfg["run_id"] = self.run_id
        self.wf = Workflow()
        self.stats = defaultdict(lambda: defaultdict(int))
        self.today = run_date(cfg)

    def handle(self, ws, idx, excel_row, row, ctx=None):
        """Run one row through its process engine and record everything."""
        ctx = ctx or Context()
        cat, t0 = row.get("category_type"), time.time()
        fn = ROUTES.get(cat)
        if not fn:
            res = Result("ERROR", f"未対応のcategory_type: {cat}", codes=["unsupported_category"])
        else:
            try:
                res = fn(row, self.api, self.cfg, ctx)
            except Exception as e:                            # one bad row never stops the batch
                log.exception("row %s failed", row["case_id"])
                res = Result("ERROR", f"処理エラー: {type(e).__name__}: {e}", codes=["exception"])
        ts = now_iso()
        if res.approval and not ctx.approver:                 # ask a human to decide
            a = res.approval
            mid = notify(self.api, row["case_id"], a["approver"], f"【承認依頼】{cat} {row['case_id']}",
                         f"ご担当者様\n\n以下の案件は、規定上ご承認が必要です。\n\n  案件ID: {row['case_id']}\n  区分: {cat}\n  内容: {a['summary']}\n\n"
                         f"承認する場合は本メールに「APPROVE」、却下する場合は「REJECT」と1行目に記入して返信してください。\n"
                         f"返信内容は次回の自動処理で反映されます。\n\n給与業務自動化システム", "approval_request")
            self.wf.open(row["case_id"], cat, a, self.run_id, self.today.isoformat(), mid)
            res.detail += f"／承認者: {a['approver']}"
        excel_io.write_result(ws, idx, excel_row, res.status, res.detail, res.reference, ts, self.run_id)
        audit.record({"ts": ts, "run_id": self.run_id, "case_id": row["case_id"], "category": cat, "status": res.status, "detail": res.detail,
                      "reference": res.reference, "codes": res.codes, "extra": res.extra, "ms": int((time.time() - t0) * 1000),
                      "approver": ctx.approver or None})
        return res

    def resume(self, ws, idx, by_case):
        for case, w in list(self.wf.pending().items()):
            if case not in by_case:
                continue
            excel_row, row = by_case[case]
            replies = self.api.get("/mail/inbox", case_ref=case, folder="inbox", kind="approval_reply")
            if replies:
                mail = self.api.get(f"/mail/{replies[0]['id']}")
                first = next((ln.strip().upper() for ln in mail["body"].splitlines() if ln.strip()), "")
                ctx = Context(approved=frozenset(w["codes"]) if first.startswith("APPROVE") else frozenset(),
                              denied=frozenset(w["codes"]) if first.startswith("REJECT") else frozenset(), approver=mail["from"])
                if first.startswith(("APPROVE", "REJECT")):
                    res = self.handle(ws, idx, excel_row, row, ctx)
                    if res.status != "ERROR":
                        self.api.post(f"/mail/{mail['id']}/move", {"folder": "processed", "replied": True})
                        self.wf.close(case, "APPROVED" if ctx.approved else "REJECTED")
                        self.stats[row["category_type"]]["resumed"] += 1
                        log.info("resumed %s (%s by %s)", case, first[:7], mail["from"])
                    continue
            age = (self.today - date.fromisoformat(w["requested_on"])).days
            if age >= self.cfg["workflow"]["escalate_days"] and not w["escalated"]:
                notify(self.api, case, self.cfg["workflow"]["approvers"]["director"], f"【承認遅延のエスカレーション】{case}",
                       f"案件 {case} の承認が {age} 日間未対応です（承認者: {w['approver']}）。ご確認ください。", "approval_escalation")
                w["escalated"] = True
            elif age >= self.cfg["workflow"]["reminder_days"] and not w["reminded"]:
                notify(self.api, case, w["approver"], f"【リマインド】承認依頼 {case}", f"案件 {case} の承認をお願いします（{age}日経過）。", "approval_reminder")
                w["reminded"] = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Excel workbook with the cases (updated in place)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--force", action="store_true", help="re-process ALL rows")
    ap.add_argument("--retry-review", action="store_true", help="also re-process NEEDS_REVIEW rows that are not waiting for an approver (after data was corrected)")
    ap.add_argument("--run-date", default=None, help="override business date (YYYY-MM-DD), e.g. to test reminders")
    a = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(RUNTIME / "pipeline.log", encoding="utf-8")])
    cfg = load_config(a.config)
    if a.run_date:
        cfg["run_date"] = a.run_date
    ensure_writable(a.input)
    api = Api(cfg)
    server = ensure_services(cfg, api)
    run = Run(a, cfg, api)
    try:
        path = Path(a.input)
        log.info("%s | backup: %s", run.run_id, excel_io.backup(path).name)
        wb, ws, headers = excel_io.open_workbook(path)
        idx = excel_io.ensure_output_columns(ws, headers)
        rows = list(excel_io.read_rows(ws, headers))
        by_case = {r["case_id"]: (n, r) for n, r in rows}
        run.resume(ws, idx, by_case)
        done = skipped = 0
        for excel_row, row in rows:
            prev = ws.cell(excel_row, idx["result_status"]).value
            retry = a.retry_review and prev == "NEEDS_REVIEW" and row["case_id"] not in run.wf.pending()
            if prev and prev != "ERROR" and not a.force and not retry:
                skipped += 1
                continue
            res = run.handle(ws, idx, excel_row, row)
            run.stats[row["category_type"]][res.status] += 1
            done += 1
            log.info("%-22s %-13s %s", row["category_type"], res.status, row["case_id"])
        run.wf.save()
        excel_io.finish_sheet(ws, idx)
        # summary sheet reflects the state of the whole workbook, not only this run
        totals = defaultdict(lambda: defaultdict(int))
        for n, r in excel_io.read_rows(ws, headers):
            totals[r["category_type"]][ws.cell(n, idx["result_status"]).value or "PENDING"] += 1
        excel_io.write_summary_sheet(wb, totals)
        try:
            wb.save(path)
        except PermissionError:                          # workbook locked by Excel: keep the results anyway
            alt = path.with_name(f"{path.stem}_RESULT_{run.run_id}{path.suffix}")
            wb.save(alt)
            log.warning("could not write %s (open in Excel?). Results saved to %s", path, alt)
            path = alt
        from reports import dashboard, mailbox, payroll_export
        mailbox.build()
        payroll_export.build(cfg)
        dashboard.build(path, run.run_id)
    finally:
        api.s.close()                                    # drop keep-alive connections so the server can exit
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

    print(f"\n{run.run_id}: processed {done} new rows, {skipped} already done, {sum(s.get('resumed', 0) for s in run.stats.values())} resumed after approval. "
          f"API calls: {api.calls}")
    print(f"{'category':<24}{'total':>6}{'APPROVED':>10}{'REJECTED':>10}{'REVIEW':>8}{'ERROR':>7}")
    for cat, s in sorted(totals.items()):
        print(f"{cat:<24}{sum(s.values()):>6}{s['APPROVED']:>10}{s['REJECTED']:>10}{s['NEEDS_REVIEW']:>8}{s['ERROR']:>7}")
    print(f"Pending approvals: {len(run.wf.pending())}   Results written into {path}")
    print("Reports: runtime/dashboard.html, runtime/mailbox.html, runtime/exports/payroll_adjustments.xlsx")


if __name__ == "__main__":
    main()