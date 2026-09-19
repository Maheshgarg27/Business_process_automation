"""
PAYROLL PROCESS AUTOMATION - control panel

    python app.py

On start it builds a fresh dummy sheet with all supporting records and documents (the previous one is removed),
then opens a page in the browser: select the sheet, press Start, watch the live log, and open the results
(dashboard, spreadsheet, mailbox in Japanese / English).

The page only starts and shows things. The work itself is done by run_pipeline.py, exactly as on the command line.
"""
import argparse, io, json, os, random, re, socket, subprocess, sys, threading, time, webbrowser
from fastapi import Body, FastAPI, HTTPException, Request, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn
from core.common import ROOT, RUNTIME
from reports import mailbox, sheet_view
from tools import generate_dataset

INPUT = ROOT / "data" / "input"
app = FastAPI(title="Payroll automation UI")
lock = threading.Lock()
S = {"phase": "idle", "lines": [], "done": 0, "total": 0, "mode": "rows", "error": None, "job": "", "meta": {}, "runs": 0}


def sheets():
    return sorted(p.name for p in INPUT.glob("*.xlsx"))


def sheet_path(name):
    p = (INPUT / name).resolve()
    if p.parent != INPUT.resolve() or p.suffix != ".xlsx" or not p.exists():
        raise HTTPException(400, "unknown spreadsheet")
    return p


def count_rows(path):
    """Number of cases in a spreadsheet (used for the progress bar)."""
    from openpyxl import load_workbook
    ws = load_workbook(path, read_only=True).worksheets[0]
    return sum(1 for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0])


def pending_count():
    f = RUNTIME / "workflow_state.json"
    if not f.exists():
        return 0
    return sum(1 for v in json.loads(f.read_text(encoding="utf-8")).values() if v["state"] == "PENDING")


def push(line):
    with lock:
        S["lines"].append(line)
        if S["mode"] == "rows" and " INFO " in line and re.search(r"AUTO-\w+\s*$", line):
            S["done"] += 1
        if S["mode"] == "resume" and " INFO resumed " in line:
            S["done"] += 1


def run_job(label, cmds, total, mode):
    with lock:
        S.update(phase="running", lines=[], done=0, total=total, mode=mode, error=None, job=label)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    try:
        for cmd in cmds:
            push("$ " + " ".join(os.path.basename(c) if os.path.isabs(c) else c for c in cmd))
            p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in p.stdout:
                push(line.rstrip("\n"))
            if p.wait() != 0:
                with lock:
                    S.update(phase="error", error=f"command exited with code {p.returncode}")
                return
        with lock:
            S["phase"] = "done"
            S["runs"] += 1
    except Exception as e:                                       # never leave the page hanging
        with lock:
            S.update(phase="error", error=str(e))


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "ui" / "index.html").read_text(encoding="utf-8")


@app.get("/api/state")
def state(since: int = 0):
    with lock:
        return {"phase": S["phase"], "lines": S["lines"][since:], "next": len(S["lines"]), "done": S["done"], "total": S["total"],
                "error": S["error"], "job": S["job"], "sheets": sheets(), "meta": S["meta"], "pending": pending_count(), "runs": S["runs"]}


@app.post("/api/upload")
async def upload(request: Request, name: str):
    """A spreadsheet chosen in the browser is stored next to the generated one. Nothing is executed here."""
    if S["phase"] == "running":
        raise HTTPException(409, "a run is in progress")
    data = await request.body()
    safe = re.sub(r"[^\w.\- ]", "_", os.path.basename(name)) or "uploaded.xlsx"
    if not safe.lower().endswith(".xlsx"):
        raise HTTPException(400, "Please choose an .xlsx file")
    if safe == S["meta"].get("sheet"):
        safe = "uploaded_" + safe
    target = INPUT / safe
    try:
        target.write_bytes(data)
        from openpyxl import load_workbook
        ws = load_workbook(target).worksheets[0]
        head = [c.value for c in ws[1]]
        if "case_id" not in head or "category_type" not in head:
            raise ValueError("The sheet needs the columns case_id and category_type")
        ids = [r[head.index("case_id")].value for r in ws.iter_rows(min_row=2) if r[head.index("case_id")].value]
    except PermissionError:
        raise HTTPException(423, "That file name is open in Excel. Close it or rename the file.")
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(400, f"Not a usable spreadsheet: {e}")
    known_file = INPUT / "expected_results.json"
    known = set(json.loads(known_file.read_text(encoding="utf-8"))) if known_file.exists() else set()
    matched = sum(1 for i in ids if i in known)
    return {"name": safe, "rows": len(ids), "matched": matched}


@app.post("/api/start")
def start(payload: dict = Body(...)):
    if S["phase"] == "running":
        raise HTTPException(409, "a run is already in progress")
    path = sheet_path(payload["sheet"])
    threading.Thread(target=run_job, args=("Automation run", [[sys.executable, "-u", "run_pipeline.py", "--input", str(path)]],
                                          count_rows(path), "rows"), daemon=True).start()
    return {"ok": True}


@app.post("/api/approvals")
def approvals(payload: dict = Body(...)):
    """Demo helper: approvers 'reply' to the pending approval mails, then the pipeline resumes those cases."""
    if S["phase"] == "running":
        raise HTTPException(409, "a run is already in progress")
    path = sheet_path(payload["sheet"])
    threading.Thread(target=run_job, args=("Approvals and resume", [[sys.executable, "-u", "-m", "tools.simulate_approvers"],
                     [sys.executable, "-u", "run_pipeline.py", "--input", str(path)]], pending_count(), "resume"), daemon=True).start()
    return {"ok": True}


@app.post("/api/reset")
def reset():
    if S["phase"] == "running":
        raise HTTPException(409, "a run is in progress")
    try:
        new_data()
    except PermissionError:
        raise HTTPException(423, "Close the spreadsheet in Excel first, then try again.")
    return {"ok": True}


@app.get("/view/dashboard", response_class=HTMLResponse)
def dashboard():
    f = RUNTIME / "dashboard.html"
    if not f.exists():
        return HTMLResponse("<body style='font-family:sans-serif;color:#666;padding:30px'>The dashboard appears after a run.</body>")
    return re.sub(r'\s*·\s*<a style="color:#bcd" href="mailbox.html">mailbox</a>', "", f.read_text(encoding="utf-8"))


@app.get("/view/mailbox", response_class=HTMLResponse)
def view_mailbox(lang: str = "ja"):
    return mailbox.render("en" if lang == "en" else "ja")


@app.get("/view/sheet", response_class=HTMLResponse)
def view_sheet(name: str, lang: str = "ja"):
    return sheet_view.render(sheet_path(name), "en" if lang == "en" else "ja")


@app.get("/view/preview", response_class=HTMLResponse)
def view_preview(name: str, limit: int = 60):
    """Short preview of the selected input sheet (shown under the live progress until results exist)."""
    return sheet_view.render(sheet_path(name), "ja", limit=min(max(limit, 1), 500))


@app.get("/download/sheet")
def download(name: str):
    return FileResponse(sheet_path(name), filename=name)


def new_data(seed=None):
    seed = seed or random.randint(1000, 9999)
    print(f"Creating a fresh dummy sheet with all supporting records and documents (seed {seed}) ...")
    info = generate_dataset.build(50, seed)
    with lock:
        S.update(meta=info, phase="idle", lines=[], done=0, total=info["rows"], error=None)
    print(f"Ready: {info['rows']} cases, {info['files_on_drive']} documents on the shared drive.")


def free_port(start):
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("no free port")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--seed", type=int, default=None, help="use a fixed seed to get the same dummy data again")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    try:
        new_data(a.seed)
    except PermissionError:
        sys.exit("Cannot replace the dummy spreadsheet: it is open in Excel. Close it and run again.")
    port = free_port(a.port)
    url = f"http://127.0.0.1:{port}"
    print(f"Open {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
