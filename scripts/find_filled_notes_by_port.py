import json, glob
from datetime import datetime

def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

for session_dir in glob.glob("dataset_b/ses_*"):
    for chunk in glob.glob(session_dir + "/chunk_*"):
        with open(chunk + "/events.jsonl", encoding="utf-8") as f:
            events = [json.loads(l) for l in f if l.strip()]

        url_events = []
        for e in events:
            ctx = e.get("context", {}) or {}
            tab = ctx.get("active_browser_tab") or {}
            url = tab.get("url", "") or ""
            if url:
                url_events.append((parse_ts(e["timestamp_iso"]), url))
        if not url_events:
            continue

        for e in events:
            if e["event_type"] == "screenshot_smart":
                shot_ts = parse_ts(e["timestamp_iso"])
                closest_ts, closest_url = min(url_events, key=lambda x: abs((x[0]-shot_ts).total_seconds()))
                gap = abs((closest_ts - shot_ts).total_seconds())
                if "payroll-items" in closest_url and gap <= 10:
                    for port in ["5132", "5133", "5134"]:
                        if port in closest_url:
                            fname = e["payload"]["file_reference"]["filename"]
                            print(port, f"{chunk}/screenshots/{fname}")