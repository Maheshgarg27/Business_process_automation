"""
Evaluation function for segment boundary predictions.

Answers one question: given predicted boundary timestamps, how close are
they to the real (ground-truth) boundaries?
"""

import json
from datetime import datetime


def _to_epoch_seconds(ts):
    """
    Accepts either an ISO 8601 timestamp string (e.g.
    '2026-07-01T06:25:21.604982+00:00') or a numeric value already in
    seconds, and returns a float number of seconds since epoch.
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    return datetime.fromisoformat(ts).timestamp()


def evaluate(predicted_segments, gt_manifest, tolerance_seconds=3):
    """
    Compare predicted boundary timestamps against ground-truth boundaries.

    Args:
        predicted_segments: list of boundary timestamps (ISO strings or
            seconds), e.g. ["2026-07-01T06:25:21.60+00:00"] or [12.1, 45.0]
        gt_manifest: dict, the loaded contents of gt_manifest.json.
            Real boundaries come from processes[].executions[].start_ts
        tolerance_seconds: float, how close a predicted boundary must be
            to a real boundary to count as a "match" (default 3s)

    Returns:
        float: percentage (0-100) of real boundaries that had a predicted
            boundary within `tolerance_seconds` of them.
    """
    real_boundaries = [
        _to_epoch_seconds(ex["start_ts"])
        for proc in gt_manifest["processes"]
        for ex in proc["executions"]
    ]

    if not real_boundaries or not predicted_segments:
        return 0.0

    predicted_seconds = [_to_epoch_seconds(ts) for ts in predicted_segments]

    matched = 0
    for real_ts in real_boundaries:
        closest_diff = min(abs(real_ts - pred_ts) for pred_ts in predicted_seconds)
        if closest_diff <= tolerance_seconds:
            matched += 1

    return (matched / len(real_boundaries)) * 100

def evaluate_full(predicted_segments, gt_manifest, tolerance_seconds=3):
    """
    Like evaluate(), but also reports precision and F1, not just recall.

    recall    = of all REAL boundaries, what % had a predicted boundary
                nearby? (this is what evaluate() alone returns)
    precision = of all PREDICTED boundaries, what % were actually near a
                real boundary? (catches "noisy" detectors that over-predict)
    f1        = harmonic mean of precision and recall - a single number
                that only looks good if BOTH are reasonably high.

    Returns a dict: {"recall": ..., "precision": ..., "f1": ...,
                      "num_real": ..., "num_predicted": ...}
    """
    real_boundaries = [
        _to_epoch_seconds(ex["start_ts"])
        for proc in gt_manifest["processes"]
        for ex in proc["executions"]
    ]
    predicted_seconds = [_to_epoch_seconds(ts) for ts in predicted_segments]

    if not real_boundaries or not predicted_seconds:
        return {
            "recall": 0.0, "precision": 0.0, "f1": 0.0,
            "num_real": len(real_boundaries), "num_predicted": len(predicted_seconds),
        }

    matched_real = sum(
        1 for r in real_boundaries
        if min(abs(r - p) for p in predicted_seconds) <= tolerance_seconds
    )
    recall = (matched_real / len(real_boundaries)) * 100

    useful_predictions = sum(
        1 for p in predicted_seconds
        if min(abs(p - r) for r in real_boundaries) <= tolerance_seconds
    )
    precision = (useful_predictions / len(predicted_seconds)) * 100

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return {
        "recall": recall, "precision": precision, "f1": f1,
        "num_real": len(real_boundaries), "num_predicted": len(predicted_seconds),
    }

if __name__ == "__main__":
    # -----------------------------------------------------------------
    # Sanity check: feed the scorer 5 REAL timestamps copied from one
    # session's gt_manifest.json, as "predictions". If this doesn't
    # print 100.0, the scorer itself is broken.
    # -----------------------------------------------------------------

    sample_real_timestamps = [
        "2026-07-01T06:25:21.604982+00:00",
        "2026-07-01T06:29:40.633102+00:00",
        "2026-07-01T06:32:29.761210+00:00",
        "2026-07-01T06:27:06.259796+00:00",
        "2026-07-01T06:31:16.201542+00:00",
    ]

    fake_gt = {
        "processes": [
            {
                "executions": [
                    {"start_ts": ts} for ts in sample_real_timestamps
                ]
            }
        ]
    }

    predictions = list(sample_real_timestamps)

    score = evaluate(predictions, fake_gt)
    print(f"Score with perfect predictions: {score}%")
    assert score == 100.0, "Scorer is broken: perfect predictions didn't score 100%"

    nudged = [
        (datetime.fromisoformat(ts).timestamp() + 1.5)
        for ts in sample_real_timestamps
    ]
    score_nudged = evaluate(nudged, fake_gt)
    print(f"Score with predictions nudged by 1.5s: {score_nudged}%")
    assert score_nudged == 100.0

    way_off = [
        (datetime.fromisoformat(ts).timestamp() + 10)
        for ts in sample_real_timestamps
    ]
    score_off = evaluate(way_off, fake_gt)
    print(f"Score with predictions off by 10s: {score_off}%")
    assert score_off < 100.0

    print("\nAll sanity checks passed. Scorer works as expected.")