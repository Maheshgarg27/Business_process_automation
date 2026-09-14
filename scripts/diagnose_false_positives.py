import json
from pathlib import Path

from evaluate import _to_epoch_seconds
from detect_boundaries import load_session_events, detect_boundaries_v2


def get_app_name(event):
    payload = event.get("payload", {})
    if "new_app" in payload:
        return payload["new_app"].get("app_name", "?")
    ctx = event.get("context", {})
    active = ctx.get("active_app")
    if active:
        return active.get("app_name", "?")
    return "?"


def diagnose_false_positives(session_dir, tolerance_seconds=3, max_examples=8):
    events = load_session_events(session_dir)

    with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
        gt = json.load(f)
    real_boundaries = [
        _to_epoch_seconds(ex["start_ts"])
        for proc in gt["processes"] for ex in proc["executions"]
    ]

    candidate_events = [
        e for e in events if e["event_type"] in ("app_switch", "browser_navigation")
    ]
    candidate_events.sort(key=lambda e: e["timestamp_iso"])
    predicted_ts = [_to_epoch_seconds(e["timestamp_iso"]) for e in candidate_events]

    false_positive_indices = []
    for i, p in enumerate(predicted_ts):
        if min(abs(p - r) for r in real_boundaries) > tolerance_seconds:
            false_positive_indices.append(i)

    print(f"Session: {Path(session_dir).name}")
    print(f"Total candidate (predicted) boundaries: {len(predicted_ts)}")
    print(f"Total false positives: {len(false_positive_indices)}")
    print(f"Showing first {max_examples} false positives with surrounding context:\n")

    for idx in false_positive_indices[:max_examples]:
        e = candidate_events[idx]
        ms_since_last = e.get("correlation", {}).get("ms_since_last_event")

        if idx + 1 < len(predicted_ts):
            duration_to_next = predicted_ts[idx + 1] - predicted_ts[idx]
        else:
            duration_to_next = None

        prev_app = get_app_name(candidate_events[idx - 1]) if idx > 0 else None
        this_app = get_app_name(e)
        next_app = get_app_name(candidate_events[idx + 1]) if idx + 1 < len(candidate_events) else None

        print(f"--- False positive #{idx} ---")
        print(f"  time: {e['timestamp_iso']}")
        print(f"  event_type: {e['event_type']}")
        print(f"  app sequence: {prev_app} -> {this_app} -> {next_app}")
        print(f"  ms_since_last_event: {ms_since_last}")
        print(
            f"  duration_to_next_candidate_boundary: "
            f"{duration_to_next:.2f}s" if duration_to_next is not None else "  (last one)"
        )
        print()


if __name__ == "__main__":
    diagnose_false_positives("dataset_a/ses_20260630-124826-CHAITANYA0BCF")