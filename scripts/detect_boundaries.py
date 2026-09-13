import json
import glob
from pathlib import Path

from evaluate import evaluate  # your Step A function


def load_session_events(session_dir):
    """Load and time-sort all events across all chunks in a session."""
    events = []
    for chunk_dir in sorted(glob.glob(str(Path(session_dir) / "chunk_*"))):
        events_file = Path(chunk_dir) / "events.jsonl"
        if not events_file.exists():
            # skip empty/placeholder chunk folders (zip artifacts)
            continue
        with open(events_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))
    events.sort(key=lambda e: e["timestamp_iso"])
    return events


def detect_boundaries_v1(events):
    """Baseline: treat every app_switch event as a candidate process boundary."""
    boundaries = []
    for e in events:
        if e["event_type"] == "app_switch":
            boundaries.append(e["timestamp_iso"])
    return boundaries


def detect_boundaries_v2(events):
    """Improved: app_switch OR browser_navigation events as candidate boundaries."""
    boundaries = []
    for e in events:
        if e["event_type"] in ("app_switch", "browser_navigation"):
            boundaries.append(e["timestamp_iso"])
    return boundaries

def merge_close_boundaries(boundaries, min_gap_seconds=10):
    """
    Merge candidate boundaries that occur too close together to be real
    segment breaks. Works on ISO 8601 timestamp strings.
    """
    if not boundaries:
        return []

    from datetime import datetime

    def to_dt(ts):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    sorted_boundaries = sorted(boundaries, key=to_dt)
    merged = [sorted_boundaries[0]]
    last_kept_dt = to_dt(sorted_boundaries[0])

    for b in sorted_boundaries[1:]:
        b_dt = to_dt(b)
        if (b_dt - last_kept_dt).total_seconds() >= min_gap_seconds:
            merged.append(b)
            last_kept_dt = b_dt

    return merged


def detect_boundaries_v3(events, min_gap_seconds=10):
    """v2 + minimum-segment-duration merge filter."""
    raw_boundaries = detect_boundaries_v2(events)
    return merge_close_boundaries(raw_boundaries, min_gap_seconds=min_gap_seconds)

# ---- Run baseline on one session ----

session_dir = "dataset_a/ses_20260630-124826-CHAITANYA0BCF"# pick any session you have

events = load_session_events(session_dir)
predicted = detect_boundaries_v2(events)

with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
    gt_manifest = json.load(f)

print(f"Events loaded: {len(events)}")
print(f"Predicted boundaries (app_switch count): {len(predicted)}")

score = evaluate(predicted, gt_manifest)  # evaluate() extracts real boundaries itself
print(f"\nBoundary detection score (app_switch only): {score:.1f}%")