"""Shows a workbook in the browser as a table: the result sheet (JA original or EN translation) or a short input preview."""
from collections import Counter
from html import escape
from openpyxl import load_workbook
from core.translate import to_english

COLOR = {"APPROVED": "#c6efce", "REJECTED": "#ffc7ce", "NEEDS_REVIEW": "#ffeb9c", "ERROR": "#d9d9d9"}


def render(path, lang="ja", limit=None):
    """limit=None -> full result view with filters. limit=N -> plain preview of the first N rows (input check)."""
    ws = load_workbook(path, read_only=True).worksheets[0]
    all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
    head, rows = all_rows[0], [r for r in all_rows[1:] if r and r[0]]
    total = len(rows)
    preview = limit is not None
    if preview:
        rows = rows[:limit]
    en = lang == "en"
    ci = {h: i for i, h in enumerate(head)}
    st = Counter(r[ci["result_status"]] or "PENDING" for r in rows) if "result_status" in ci and not preview else Counter()
    procs = sorted({r[ci["category_type"]] for r in rows if r[ci["category_type"]]})
    tr = lambda v: to_english(v) if en and isinstance(v, str) else v
    body = []
    for r in rows:
        cells = []
        for h, v in zip(head, r):
            v = "" if v is None else tr(v)
            style = f' style="background:{COLOR.get(v, "")}"' if h == "result_status" and v in COLOR else ""
            cls = ' class="wide"' if h == "result_detail" else ""
            cells.append(f"<td{cls}{style}>{escape(str(v))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    if preview:
        top = f"<b>Input preview</b><span class='mut'>first {len(rows)} of {total} rows — this is what the tool receives</span>"
    else:
        chips = "".join(f'<span class="chip" style="background:{COLOR.get(k, "#eee")}">{k}: {v}</span>' for k, v in st.items())
        opts = "".join(f"<option>{escape(p)}</option>" for p in procs)
        sopts = "".join(f"<option>{s}</option>" for s in ["APPROVED", "REJECTED", "NEEDS_REVIEW", "ERROR"])
        top = (f'<b>{total} rows</b>{chips}<select id="p"><option value="">all processes</option>{opts}</select>'
               f'<select id="s"><option value="">all statuses</option>{sopts}</select><input id="q" placeholder="search..."><span id="n"></span>')
    script = "" if preview else f"""<script>
const rows=[...document.querySelectorAll("#t tbody tr")],ci={{p:{ci["category_type"]},s:{ci.get("result_status", 0)}}};
function f(){{const p=document.getElementById("p").value,s=document.getElementById("s").value,q=document.getElementById("q").value.toLowerCase();let n=0;
rows.forEach(r=>{{const c=r.children;const ok=(!p||c[ci.p].textContent===p)&&(!s||c[ci.s].textContent===s)&&(!q||r.textContent.toLowerCase().includes(q));r.style.display=ok?"":"none";if(ok)n++}});
document.getElementById("n").textContent=n+" shown"}}
["p","s","q"].forEach(i=>document.getElementById(i).oninput=f);f();
</script>"""
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>
html,body{{height:100%;margin:0}}
body{{display:flex;flex-direction:column;font:13px/1.45 -apple-system,"Segoe UI","Yu Gothic",sans-serif;color:#1f2328;background:#fff}}
.bar{{flex:none;padding:10px 14px;border-bottom:1px solid #e3e6ec;display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:#fff}}
.mut{{color:#66748a}}.chip{{padding:2px 10px;border-radius:12px;font-size:12px}}select,input{{padding:5px 8px;border:1px solid #cfd6e2;border-radius:6px}}
.wrap{{flex:1;min-height:0;overflow:auto}}
table{{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%}}
th{{position:sticky;top:0;z-index:2;background:#1F3A5F;color:#fff;text-align:left;padding:7px 10px;white-space:nowrap}}
td{{padding:5px 10px;border-bottom:1px solid #eceff4;white-space:nowrap;vertical-align:top;background:#fff}}
td.wide{{white-space:normal;min-width:360px;max-width:520px}}tr:hover td{{background:#f6f9ff}}
</style></head><body><div class="bar">{top}</div>
<div class="wrap"><table id="t"><thead><tr>{"".join(f"<th>{escape(str(h))}</th>" for h in head)}</tr></thead><tbody>{"".join(body)}</tbody></table></div>
{script}</body></html>"""
