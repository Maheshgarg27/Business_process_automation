"""
Run this LOCALLY on your machine (where dataset_b/ with screenshots actually lives).

Purpose: for a handful of "(no_url_generic)" segments, find which screenshot
files (if any) fall inside their [start, end] window, so you can manually
grab 2-3 of them to upload for a quick OCR legibility gut-check.

Usage:
    python find_generic_segment_screenshots.py --dataset-root dataset_b --segments segments.jsonl --limit 5

By default it targets the largest "Microsoft Word (no_url_generic)" group
since that's your biggest coverage gap (268 segments), but you can pass
--label to target a different one, e.g. "Notepad (no_url_generic)".
"""
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_session_events(session_dir):
    """Load and merge events.jsonl across all chunks in a session, sorted by time."""
    events = []
    for chunk_dir in sorted(glob.glob(str(Path(session_dir) / "chunk_*"))):
        ev_path = Path(chunk_dir) / "events.jsonl"
        if not ev_path.exists():
            continue
        with open(ev_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                ev["_chunk_dir"] = chunk_dir  # remember which chunk this came from
                events.append(ev)
    events.sort(key=lambda e: e["timestamp_iso"])
    return events


def find_screenshots_for_segment(dataset_root, session_id, start, end):
    session_dir = Path(dataset_root) / session_id
    if not session_dir.exists():
        return [], f"session dir not found: {session_dir}"

    events = load_session_events(session_dir)
    start_dt, end_dt = to_dt(start), to_dt(end)

    matches = []
    for ev in events:
        if ev.get("event_type") != "screenshot_smart":
            continue
        ts = to_dt(ev["timestamp_iso"])
        if start_dt <= ts <= end_dt:
            fname = (ev.get("payload", {}) or {}).get("file_reference", {}).get("filename")
            if not fname:
                continue
            img_path = Path(ev["_chunk_dir"]) / "screenshots" / fname
            matches.append({
                "filename": fname,
                "full_path": str(img_path),
                "exists_on_disk": img_path.exists(),
                "timestamp_iso": ev["timestamp_iso"],
                "trigger_reason": (ev.get("payload", {}) or {}).get("trigger_reason"),
            })
    return matches, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="dataset_b")
    ap.add_argument("--segments", default="segments.jsonl")
    ap.add_argument("--label", default="Microsoft Word (no_url_generic)")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    segs = []
    with open(args.segments, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segs.append(json.loads(line))

    target_segs = [s for s in segs if s["label"] == args.label]
    print(f"Found {len(target_segs)} segments with label '{args.label}'")

    # Sort by duration, longest first (more likely to have a "settled" screenshot)
    def dur(s):
        return (to_dt(s["end"]) - to_dt(s["start"])).total_seconds()
    target_segs.sort(key=dur, reverse=True)

    shown = 0
    for seg in target_segs:
        if shown >= args.limit:
            break
        matches, err = find_screenshots_for_segment(
            args.dataset_root, seg["session_id"], seg["start"], seg["end"]
        )
        print(f"\n--- session={seg['session_id']}  {seg['start']} -> {seg['end']} ({dur(seg):.1f}s) ---")
        if err:
            print(f"  ERROR: {err}")
            continue
        if not matches:
            print("  (no screenshots in this window)")
            continue
        for m in matches:
            status = "OK" if m["exists_on_disk"] else "MISSING ON DISK"
            print(f"  [{status}] {m['full_path']}  (trigger: {m['trigger_reason']})")
        shown += 1

    print("\nDone. Pick 2-3 of the [OK] file paths above and upload those .jpg files for the gut-check.")


if __name__ == "__main__":
    main()