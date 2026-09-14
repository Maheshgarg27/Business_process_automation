import json
from pathlib import Path
from datetime import datetime
from collections import Counter

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def fingerprint_segment(segment_events):
    """
    Cheap signature: apps active + browser URL path (not just domain) -
    this internal portal hosts multiple business processes on the same
    domain, distinguished only by path, so domain-only was too coarse.
    """
    apps = set()
    paths = set()
    for e in segment_events:
        aa = e.get("context", {}).get("active_app") or {}
        if aa.get("app_name"):
            apps.add(aa["app_name"])
        tab = e.get("context", {}).get("active_browser_tab") or {}
        url = tab.get("url")
        if url:
            if "://" in url:
                after_scheme = url.split("://", 1)[1]
                path_part = after_scheme.split("?")[0]
            else:
                path_part = url.split("?")[0]
            paths.add(path_part)
    return (frozenset(apps), frozenset(paths))


def events_in_range(events, start, end):
    start_dt, end_dt = to_dt(start), to_dt(end)
    return [e for e in events if start_dt <= to_dt(e["timestamp_iso"]) < end_dt]


def label_segments(events, segments):
    """Assign a label per segment based on fingerprint matching."""
    fingerprint_to_label = {}
    labeled = []

    for start, end in segments:
        seg_events = events_in_range(events, start, end)
        fp = fingerprint_segment(seg_events)

        if fp not in fingerprint_to_label:
            apps_str = "+".join(sorted(fp[0])) if fp[0] else "none"
            paths_str = "+".join(sorted(fp[1]))[:80] if fp[1] else ""
            label = f"{apps_str}" + (f"|{paths_str}" if paths_str else "")
            fingerprint_to_label[fp] = label

        labeled.append({
            "start": start, "end": end,
            "label": fingerprint_to_label[fp], "fingerprint": fp,
        })

    return labeled


if __name__ == "__main__":
    session_dir = "dataset_a/ses_20260630-124826-CHAITANYA0BCF"
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)

    session_start = events[0]["timestamp_iso"]
    session_end = events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, session_start, session_end)

    labeled = label_segments(events, segments)

    unique_labels = set(item["label"] for item in labeled)
    print(f"Total segments: {len(labeled)}")
    print(f"Unique labels: {len(unique_labels)}")

    counts = Counter(item["label"] for item in labeled)
    print("\nTop 10 most common labels:")
    for label, count in counts.most_common(10):
        print(f"  {count:4d}x  {label}")

    print("\nFirst 10 labeled segments:")
    for item in labeled[:10]:
        print(f"  {item['start']} -> {item['end']}  [{item['label']}]")