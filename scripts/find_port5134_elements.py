import json, glob
from collections import Counter

element_ids = Counter()
for session_dir in glob.glob("dataset_b/ses_*"):
    for chunk in glob.glob(session_dir + "/chunk_*"):
        with open(chunk + "/events.jsonl", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                e = json.loads(line)
                ctx = e.get("context", {}) or {}
                tab = ctx.get("active_browser_tab") or {}
                url = tab.get("url", "") or ""
                if "5134" in url and "payroll-items" in url and e["event_type"] in ("browser_click", "browser_form_input"):
                    el = e.get("payload", {}).get("element", {}) or e.get("payload", {}).get("field", {})
                    eid = el.get("id") or el.get("css_selector")
                    if eid:
                        element_ids[eid] += 1

for eid, cnt in element_ids.most_common(15):
    print(eid, cnt)