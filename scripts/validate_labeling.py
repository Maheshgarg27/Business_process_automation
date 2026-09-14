import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments
from label_segments import label_segments


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def get_ground_truth_intervals(gt_manifest):
    intervals = []
    for proc in gt_manifest["processes"]:
        code = proc["code"]
        for ex in proc["executions"]:
            if not ex.get("start_ts") or not ex.get("end_ts"):
                continue
            start = to_dt(ex["start_ts"])
            end = to_dt(ex["end_ts"])
            intervals.append((start, end, code))
    return intervals


def match_segment_to_ground_truth(seg_start, seg_end, gt_intervals):
    seg_start_dt, seg_end_dt = to_dt(seg_start), to_dt(seg_end)
    best_overlap = 0
    best_label = "NO_MATCH"
    for gt_start, gt_end, code in gt_intervals:
        overlap_start = max(seg_start_dt, gt_start)
        overlap_end = min(seg_end_dt, gt_end)
        overlap = (overlap_end - overlap_start).total_seconds()
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = code
    return best_label


def label_purity(predicted_labels, true_labels):
    groups = defaultdict(Counter)
    for pred, true in zip(predicted_labels, true_labels):
        groups[pred][true] += 1
    total = len(predicted_labels)
    correct = sum(max(c.values()) for c in groups.values())
    return correct / total


if __name__ == "__main__":
    session_dir = "dataset_a/ses_20260630-124826-CHAITANYA0BCF"
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)

    session_start = events[0]["timestamp_iso"]
    session_end = events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, session_start, session_end)
    labeled = label_segments(events, segments)

    with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
        gt_manifest = json.load(f)
    gt_intervals = get_ground_truth_intervals(gt_manifest)

    predicted_labels, true_labels = [], []
    for item in labeled:
        true_label = match_segment_to_ground_truth(item["start"], item["end"], gt_intervals)
        predicted_labels.append(item["label"])
        true_labels.append(true_label)

    purity = label_purity(predicted_labels, true_labels)

    print(f"Total segments: {len(labeled)}")
    print(f"Segments with NO_MATCH: {true_labels.count('NO_MATCH')}")
    print(f"Purity score: {purity*100:.1f}%")

    groups = defaultdict(Counter)
    for pred, true in zip(predicted_labels, true_labels):
        groups[pred][true] += 1

    print("\nBreakdown per predicted label (top 10 by size):")
    sorted_groups = sorted(groups.items(), key=lambda x: -sum(x[1].values()))
    for pred_label, true_counter in sorted_groups[:10]:
        total = sum(true_counter.values())
        print(f"  [{pred_label}] ({total} segments): {dict(true_counter)}")