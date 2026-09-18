"""
Reads the input workbook and writes results back INTO THE SAME FILE.
Original columns are never touched; four output columns are appended on the right.
"""
import shutil
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from core.common import ROOT

OUT_COLS = ["result_status", "result_detail", "result_reference", "processed_at", "run_id"]
FILL = {"APPROVED": "C6EFCE", "REJECTED": "FFC7CE", "NEEDS_REVIEW": "FFEB9C", "ERROR": "D9D9D9"}


def backup(path: Path) -> Path:
    dst = ROOT / "backups" / f"{path.stem}.{datetime.now():%Y%m%d_%H%M%S}{path.suffix}"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def open_workbook(path):
    wb = load_workbook(path)
    ws = wb.worksheets[0]
    headers = [c.value for c in ws[1]]
    return wb, ws, headers


def read_rows(ws, headers):
    """Yield (excel_row_number, dict) for every non-empty row."""
    for r in range(2, ws.max_row + 1):
        vals = [ws.cell(r, c + 1).value for c in range(len(headers))]
        if not any(v is not None for v in vals):
            continue
        yield r, dict(zip(headers, vals))


def ensure_output_columns(ws, headers):
    idx = {}
    for name in OUT_COLS:
        if name in headers:
            idx[name] = headers.index(name) + 1
        else:
            headers.append(name)
            idx[name] = len(headers)
            cell = ws.cell(1, idx[name], name)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
    return idx


def write_result(ws, idx, excel_row, status, detail, reference, processed_at, run_id=""):
    ws.cell(excel_row, idx["result_status"], status).fill = PatternFill("solid", fgColor=FILL.get(status, "FFFFFF"))
    c = ws.cell(excel_row, idx["result_detail"], detail)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(excel_row, idx["result_reference"], reference)
    ws.cell(excel_row, idx["processed_at"], processed_at)
    ws.cell(excel_row, idx["run_id"], run_id)


def finish_sheet(ws, idx):
    ws.column_dimensions[get_column_letter(idx["result_detail"])].width = 70
    ws.column_dimensions[get_column_letter(idx["result_status"])].width = 16
    ws.column_dimensions[get_column_letter(idx["result_reference"])].width = 22
    ws.column_dimensions[get_column_letter(idx["processed_at"])].width = 20
    ws.column_dimensions[get_column_letter(idx["run_id"])].width = 22
    ws.freeze_panes = "B2"


def write_summary_sheet(wb, stats: dict):
    if "Run Summary" in wb.sheetnames:
        del wb["Run Summary"]
    ws = wb.create_sheet("Run Summary")
    ws.append(["category", "total", "APPROVED", "REJECTED", "NEEDS_REVIEW", "ERROR"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
    for cat, s in sorted(stats.items()):
        ws.append([cat, sum(s.values()), s.get("APPROVED", 0), s.get("REJECTED", 0),
                   s.get("NEEDS_REVIEW", 0), s.get("ERROR", 0)])
    ws.column_dimensions["A"].width = 26
