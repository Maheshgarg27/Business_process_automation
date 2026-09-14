import json
import glob
from pathlib import Path

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments
from label_segments import label_segments
from validate_labeling import get_ground_truth_intervals, match_segment_to_ground_truth, label_purity


def run_session(session_dir):
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)

    session_start = events[0]["timestamp_iso"]
    session_end = events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, session_start, session_end)
    labeled = label_segments(events, segments)

    gt_path = Path(session_dir) / "gt_manifest.json"
    with open(gt_path, encoding="utf-8") as f:
        gt_manifest = json.load(f)
    gt_intervals = get_ground_truth_intervals(gt_manifest)

    predicted_labels, true_labels = [], []
    for item in labeled:
        true_label = match_segment_to_ground_truth(item["start"], item["end"], gt_intervals)
        predicted_labels.append(item["label"])
        true_labels.append(true_label)

    purity = label_purity(predicted_labels, true_labels)
    return purity, len(labeled), len(set(predicted_labels))


if __name__ == "__main__":
    dataset_dir = "dataset_a"
    purities = []
    errors = []

    session_dirs = sorted(
        d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir()
    )

    for session_dir in session_dirs:
        session_name = Path(session_dir).name
        gt_path = Path(session_dir) / "gt_manifest.json"
        if not gt_path.exists():
            continue
        try:
            purity, num_segments, num_labels = run_session(session_dir)
            purities.append(purity)
            print(f"{session_name}: purity={purity*100:.1f}%  segments={num_segments}  labels={num_labels}")
        except Exception as e:
            errors.append((session_name, str(e)))
            print(f"{session_name}: FAILED ({e})")

    print("\n--- Summary ---")
    print(f"Sessions processed: {len(purities)}")
    print(f"Sessions failed: {len(errors)}")
    if purities:
        print(f"Average purity: {sum(purities)/len(purities)*100:.1f}%")
        print(f"Min purity: {min(purities)*100:.1f}%")
        print(f"Max purity: {max(purities)*100:.1f}%")

    if errors:
        print("\nFailed sessions:")
        for name, err in errors:
            print(f"  {name}: {err}")