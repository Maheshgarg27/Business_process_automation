import json
import glob
from pathlib import Path

from evaluate import evaluate
from detect_boundaries import load_session_events, detect_boundaries_v1, detect_boundaries_v2


def run_all_sessions(dataset_dir, detector_fn):
    """
    Run `detector_fn` + evaluate() over every session in dataset_dir.
    Returns (list of per-session scores, list of (session_name, error) for
    any sessions that failed to process).
    """
    scores = []
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

            score = evaluate(predicted, gt_manifest)
            scores.append(score)
            print(f"{session_name}: {score:.1f}%  ({len(predicted)} predicted boundaries)")

        except Exception as e:
            errors.append((session_name, str(e)))
            print(f"{session_name}: FAILED ({e})")

    return scores, errors


if __name__ == "__main__":
    dataset_dir = "dataset_a"  # adjust if your folder is named differently

    print("=== v1: app_switch only ===")
    scores_v1, errors_v1 = run_all_sessions(dataset_dir, detect_boundaries_v1)

    print("\n=== v2: app_switch + browser_navigation ===")
    scores_v2, errors_v2 = run_all_sessions(dataset_dir, detect_boundaries_v2)

    print("\n--- Summary ---")
    print(f"Sessions processed (v1): {len(scores_v1)}")
    print(f"Sessions failed (v1): {len(errors_v1)}")
    if scores_v1:
        print(f"v1 average score: {sum(scores_v1) / len(scores_v1):.1f}%")

    print()
    print(f"Sessions processed (v2): {len(scores_v2)}")
    print(f"Sessions failed (v2): {len(errors_v2)}")
    if scores_v2:
        print(f"v2 average score: {sum(scores_v2) / len(scores_v2):.1f}%")

    if errors_v2:
        print("\nSessions that failed (v2):")
        for name, err in errors_v2:
            print(f"  {name}: {err}")