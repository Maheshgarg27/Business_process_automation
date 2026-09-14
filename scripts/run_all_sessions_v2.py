import json
import glob
from pathlib import Path

from evaluate import evaluate_full
from detect_boundaries import load_session_events, detect_boundaries_v1, detect_boundaries_v2


def run_all_sessions(dataset_dir, detector_fn):
    """
    Run `detector_fn` + evaluate_full() over every session in dataset_dir.
    Returns (list of per-session result dicts, list of (session_name, error)).
    """
    results = []
    errors = []

    session_dirs = sorted(
        d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir()
    )

    for session_dir in session_dirs:
        session_name = Path(session_dir).name
        gt_path = Path(session_dir) / "gt_manifest.json"

        if not gt_path.exists():
            errors.append((session_name, "no gt_manifest.json found"))
            continue

        try:
            events = load_session_events(session_dir)
            predicted = detector_fn(events)

            with open(gt_path, encoding="utf-8") as f:
                gt_manifest = json.load(f)

            result = evaluate_full(predicted, gt_manifest)
            results.append(result)
            print(
                f"{session_name}: recall={result['recall']:.1f}%  "
                f"precision={result['precision']:.1f}%  f1={result['f1']:.1f}%"
            )

        except Exception as e:
            errors.append((session_name, str(e)))
            print(f"{session_name}: FAILED ({e})")

    return results, errors


def summarize(results, label):
    if not results:
        print(f"{label}: no sessions processed")
        return
    avg_recall = sum(r["recall"] for r in results) / len(results)
    avg_precision = sum(r["precision"] for r in results) / len(results)
    avg_f1 = sum(r["f1"] for r in results) / len(results)
    print(f"\n--- {label} ---")
    print(f"Sessions processed: {len(results)}")
    print(f"Avg recall:    {avg_recall:.1f}%")
    print(f"Avg precision: {avg_precision:.1f}%")
    print(f"Avg F1:        {avg_f1:.1f}%")


if __name__ == "__main__":
    dataset_dir = "dataset_a"  # adjust if your folder is named differently

    print("=== v1: app_switch only ===")
    results_v1, errors_v1 = run_all_sessions(dataset_dir, detect_boundaries_v1)

    print("\n=== v2: app_switch + browser_navigation ===")
    results_v2, errors_v2 = run_all_sessions(dataset_dir, detect_boundaries_v2)

    summarize(results_v1, "v1: app_switch only")
    summarize(results_v2, "v2: app_switch + browser_navigation")

    if errors_v2:
        print("\nSessions that failed (v2):")
        for name, err in errors_v2:
            print(f"  {name}: {err}")