import json
import glob
from pathlib import Path

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments, merge_same_label_segments
from label_segments import label_segments


def process_session(session_dir):
    """Run the full pipeline on one session: boundaries -> segments -> labels -> merge."""
    session_id = Path(session_dir).name
    events = load_session_events(session_dir)
    if not events:
        return []

    boundaries = detect_boundaries_v2(events)
    session_start = events[0]["timestamp_iso"]
    session_end = events[-1]["timestamp_iso"]

    segments = boundaries_to_segments(boundaries, session_start, session_end)
    labeled = label_segments(events, segments)
    merged = merge_same_label_segments(labeled)

    results = []
    for seg in merged:
        results.append({
            "session_id": session_id,
            "start": seg["start"],
            "end": seg["end"],
            "label": seg["label"],
        })
    return results


if __name__ == "__main__":
    dataset_dir = "dataset_b"
    output_path = "outputs/segments.jsonl"

    session_dirs = sorted(
        d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir()
    )

    all_segments = []
    errors = []

    for session_dir in session_dirs:
        session_name = Path(session_dir).name
        try:
            segs = process_session(session_dir)
            all_segments.extend(segs)
            print(f"{session_name}: {len(segs)} segments")
        except Exception as e:
            errors.append((session_name, str(e)))
            print(f"{session_name}: FAILED ({e})")

    Path("outputs").mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in all_segments:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")

    print(f"\n--- Summary ---")
    print(f"Sessions processed: {len(session_dirs) - len(errors)}")
    print(f"Sessions failed: {len(errors)}")
    print(f"Total segments written: {len(all_segments)}")
    print(f"Output saved to: {output_path}")

    if errors:
        print("\nFailed sessions:")
        for name, err in errors:
            print(f"  {name}: {err}")