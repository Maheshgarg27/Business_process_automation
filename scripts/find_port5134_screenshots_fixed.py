import json
import glob
from datetime import datetime, timedelta

def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

matches = []

for session_dir in glob.glob("dataset_b/ses_*"):  # full dataset_b, WITH screenshots
    session_id = session_dir.replace("\\", "/").split("/")[-1]
    for chunk in glob.glob(session_dir + "/chunk_*"):
        with open(chunk + "/events.jsonl", encoding="utf-8") as f:
            events = [json.loads(l) for l in f if l.strip()]

        # Step 1: find timestamps where user was actually on port 5134's payroll-items
        port_times = []
        for e in events:
            ctx = e.get("context", {}) or {}
            tab = ctx.get("active_browser_tab") or {}
            url = tab.get("url", "") or ""
            if "5134" in url and "payroll-items" in url:
                port_times.append(parse_ts(e["timestamp_iso"]))

        if not port_times:
            continue

        # Step 2: find screenshots taken close in time to any of those moments
        for e in events:
            if e["event_type"] == "screenshot_smart":
                shot_ts = parse_ts(e["timestamp_iso"])
                closest_gap = min(abs((shot_ts - pt).total_seconds()) for pt in port_times)
                if closest_gap <= 15:  # within 15 seconds of confirmed port-5134 activity
                    fname = e["payload"]["file_reference"]["filename"]
                    matches.append({
                        "session": session_id,
                        "screenshot": f"{chunk}/screenshots/{fname}",
                        "gap_seconds": round(closest_gap, 1)
                    })

print(f"Found {len(matches)} screenshots within 15s of confirmed port-5134 payroll-items activity")
for m in matches[:10]:
    print(m)