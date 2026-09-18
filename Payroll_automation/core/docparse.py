"""
Reading business documents (PDF, Word, Excel, text) into text / rows.
The processors never open files themselves: they download bytes through the
document-store API and hand them to these helpers.
"""
import io
import re


def read_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        lines = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lines)
    return data.decode("utf-8", errors="replace")


def read_xlsx(data: bytes):
    """First sheet -> list of dicts keyed by the header row."""
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(data), data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    head = [str(h) for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if any(v is not None for v in r)]


def field(text: str, label: str):
    """Value after 'label:' (or full-width colon) on its own line."""
    m = re.search(rf"^\s*{re.escape(label)}\s*[:：]\s*(.+?)\s*$", text or "", re.M)
    return m.group(1) if m else None


def to_int(s):
    d = re.sub(r"[^\d-]", "", str(s or ""))
    return int(d) if d not in ("", "-") else None
