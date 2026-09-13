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

    run_all(dataset_dir, detect_boundaries_v2, "v2 (no filter)")
    run_all(dataset_dir, detect_boundaries_v3, "v3 (min_gap=10s)", min_gap_seconds=10)