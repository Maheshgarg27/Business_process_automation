import json
import glob
from pathlib import Path

from evaluate import evaluate_full
from detect_boundaries import load_session_events, detect_boundaries_v2, detect_boundaries_v3


def run_all(dataset_dir, detector_fn, label, **kwargs):
    recalls, precisions, f1s = [], [], []
    for session_dir in sorted(d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir()):
        gt_path = Path(session_dir) / "gt_manifest.json"
        if not gt_path.exists():
            continue
        with open(gt_path, encoding="utf-8") as f:
            gt = json.load(f)
        events = load_session_events(session_dir)
        predicted = detector_fn(events, **kwargs) if kwargs else detector_fn(events)
        r = evaluate_full(predicted, gt)
        recalls.append(r["recall"])
        precisions.append(r["precision"])
        f1s.append(r["f1"])
    avg_r = sum(recalls) / len(recalls)
    avg_p = sum(precisions) / len(precisions)
    avg_f1 = sum(f1s) / len(f1s)
    print(f"{label}: recall={avg_r:.1f}%  precision={avg_p:.1f}%  f1={avg_f1:.1f}%")


if __name__ == "__main__":
    dataset_dir = "dataset_a"

    run_all(dataset_dir, detect_boundaries_v2, "v2 (no filter, baseline)")
    for gap in [1, 2, 3, 5, 7, 10, 12, 15, 20]:
        run_all(dataset_dir, detect_boundaries_v3, f"v3 (min_gap={gap}s)", min_gap_seconds=gap)

        import csv

sweep_results = [
    {"threshold": "v2_baseline", "recall": 85.1, "precision": 36.6, "f1": 50.8},
    {"threshold": 1, "recall": 85.1, "precision": 28.0, "f1": 42.0},
    {"threshold": 2, "recall": 85.0, "precision": 25.1, "f1": 38.6},
    {"threshold": 3, "recall": 85.0, "precision": 24.6, "f1": 38.0},
    {"threshold": 5, "recall": 83.6, "precision": 24.3, "f1": 37.6},
    {"threshold": 7, "recall": 81.8, "precision": 29.2, "f1": 42.9},
    {"threshold": 10, "recall": 78.9, "precision": 35.4, "f1": 48.7},
    {"threshold": 12, "recall": 64.0, "precision": 30.9, "f1": 41.5},
    {"threshold": 15, "recall": 43.2, "precision": 23.3, "f1": 30.2},
    {"threshold": 20, "recall": 37.4, "precision": 26.1, "f1": 30.6},
]

with open("outputs/day2_threshold_sweep.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["threshold", "recall", "precision", "f1"])
    writer.writeheader()
    writer.writerows(sweep_results)

print("Saved sweep results to outputs/day2_threshold_sweep.csv")