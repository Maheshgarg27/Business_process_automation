import json
import glob
from pathlib import Path

def get_note_text(events, seg_start, seg_end, note_field_id="pi-note"):
    """Find the actual text typed into the note field during this segment."""
    for e in events:
        if e["event_type"] == "browser_form_input":
            field = e.get("payload", {}).get("field", {})
            if field.get("id") == note_field_id:
                ts = e["timestamp_iso"]
                if seg_start <= ts <= seg_end:
                    return e["payload"].get("value") or field.get("value") or "(value not captured)"
    return None

def get_screenshot(events, seg_start, seg_end, chunk_dir):
    """Find a screenshot taken during this segment."""
    for e in events:
        if e["event_type"] == "screenshot_smart":
            ts = e["timestamp_iso"]
            if seg_start <= ts <= seg_end:
                fname = e["payload"]["file_reference"]["filename"]
                return str(Path(chunk_dir) / "screenshots" / fname)
    return None

# Load your segments.jsonl
segments = []
with open("outputs/segments.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            segments.append(json.loads(line))

payroll_segments = [s for s in segments if "payroll-items" in s["label"]]

results = []
for seg in payroll_segments:
    session_id = seg["session_id"]
    session_dir = f"dataset_b/{session_id}"  # use full dataset_b (has screenshots), not _clean
    for chunk_dir in glob.glob(session_dir + "/chunk_*"):
        events = []
        with open(Path(chunk_dir) / "events.jsonl", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        note = get_note_text(events, seg["start"], seg["end"])
        screenshot = get_screenshot(events, seg["start"], seg["end"], chunk_dir)
        if note and screenshot:
            results.append({"session": session_id, "start": seg["start"], "note": note, "screenshot": screenshot})

print(f"Found {len(results)} payroll segments with BOTH a note and a screenshot")
for r in results[:15]:
    print(f"\n{r['screenshot']}\nNote: {r['note']}")