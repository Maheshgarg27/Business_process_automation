"""Static results dashboard (runtime/dashboard.html): totals, top reasons, pending approvals, rows needing attention."""
import json
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from openpyxl import load_workbook
from core.common import RUNTIME
from core.workflow import Workflow
from reports.payroll_export import latest_decisions

STAT = ["APPROVED", "REJECTED", "NEEDS_REVIEW", "ERROR"]
COLOR = {"APPROVED": "#4caf50", "REJECTED": "#e53935", "NEEDS_REVIEW": "#fbc02d", "ERROR": "#9e9e9e"}


def build(workbook_path, run_id, out=None):
    ws = load_workbook(workbook_path).worksheets[0]
    head = [c.value for c in ws[1]]
    rows = [dict(zip(head, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
    rows = [r for r in rows if r.get("case_id")]
    tot = defaultdict(Counter)
    for r in rows:
        tot[r["category_type"]][r.get("result_status") or "PENDING"] += 1
    last = latest_decisions()
    reasons = Counter(c for e in last.values() if e["status"] in ("REJECTED", "NEEDS_REVIEW") for c in e.get("codes", []))
    pend = Workflow().pending()
    attention = [r for r in rows if r.get("result_status") in ("NEEDS_REVIEW", "ERROR") and r["case_id"] not in pend]
    n = len(rows)
    cnt = Counter(r.get("result_status") or "PENDING" for r in rows)

    def bar(c):
        t = sum(c.values()) or 1
        return "".join(f'<span style="width:{c[s] / t * 100:.1f}%;background:{COLOR[s]}" title="{s}: {c[s]}"></span>' for s in STAT if c[s])

    cat_rows = "".join(f"<tr><td>{escape(k)}</td><td>{sum(v.values())}</td>" + "".join(f"<td>{v[s]}</td>" for s in STAT)
                       + f'<td class="bar">{bar(v)}</td></tr>' for k, v in sorted(tot.items()))
    reason_rows = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in reasons.most_common(12))
    pend_rows = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v['category'])}</td><td>{escape(v['approver'])}</td><td>{v['requested_on']}</td>"
                        f"<td>{', '.join(v['codes'])}</td></tr>" for k, v in pend.items()) or '<tr><td colspan="5">なし / none</td></tr>'
    att_rows = "".join(f"<tr><td>{escape(r['case_id'])}</td><td>{escape(r['category_type'])}</td><td>{r['result_status']}</td>"
                       f"<td>{escape(str(r.get('result_detail'))[:140])}</td></tr>" for r in attention[:60]) or '<tr><td colspan="4">なし / none</td></tr>'
    kpi = "".join(f'<div class="k"><b style="color:{COLOR.get(s, "#555")}">{cnt[s]}</b><span>{s}</span></div>' for s in STAT)
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>Payroll Automation Dashboard</title><style>
body{{font:14px/1.5 -apple-system,"Segoe UI","Yu Gothic",sans-serif;margin:0;background:#f6f8fc;color:#1f2328}}
header{{background:#1F3A5F;color:#fff;padding:16px 28px}}header h1{{margin:0;font-size:20px}}header small{{opacity:.75}}
main{{padding:22px 28px;max-width:1100px}}h2{{font-size:16px;margin:26px 0 8px;color:#1F3A5F}}
.kpis{{display:flex;gap:14px}}.k{{background:#fff;border:1px solid #e3e6ec;border-radius:10px;padding:14px 22px;min-width:130px}}.k b{{font-size:28px;display:block}}.k span{{color:#6b7280;font-size:12px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e3e6ec}}th{{background:#1F3A5F;color:#fff;text-align:left;font-weight:600}}
td,th{{padding:7px 10px;border-bottom:1px solid #e3e6ec;font-size:13px}}td.bar{{width:220px}}
td.bar span{{display:inline-block;height:14px}}td.bar{{white-space:nowrap;font-size:0}}a{{color:#1a73e8}}</style></head><body>
<header><h1>Payroll Automation - Results dashboard</h1><small>{run_id} · generated {datetime.now():%Y-%m-%d %H:%M} · {n} cases · <a style="color:#bcd" href="mailbox.html">mailbox</a></small></header>
<main><div class="kpis"><div class="k"><b>{n}</b><span>TOTAL CASES</span></div>{kpi}<div class="k"><b>{len(pend)}</b><span>WAITING FOR APPROVER</span></div></div>
<h2>By process</h2><table><tr><th>process</th><th>total</th>{''.join(f'<th>{s}</th>' for s in STAT)}<th>mix</th></tr>{cat_rows}</table>
<h2>Top reasons for rejection / review</h2><table><tr><th>rule code</th><th>cases</th></tr>{reason_rows}</table>
<h2>Waiting for an approver</h2><table><tr><th>case</th><th>process</th><th>approver</th><th>requested</th><th>codes</th></tr>{pend_rows}</table>
<h2>Needs a person (data conflicts / errors)</h2><table><tr><th>case</th><th>process</th><th>status</th><th>detail</th></tr>{att_rows}</table></main></body></html>"""
    out = out or RUNTIME / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out
