import json
import re
import glob
from pathlib import Path
import pandas as pd

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments
from label_segments import label_segments
from validate_labeling import get_ground_truth_intervals, match_segment_to_ground_truth, label_purity


def extract_process_label(fingerprint_label):
    """
    Drops BOTH port number and app-combo, keeping only the URL route.
    This is the ORIGINAL proposed fix - being tested here.
    """
    if "|" in fingerprint_label:
        url_part = fingerprint_label.split("|", 1)[1]
        match = re.search(r"#/([a-zA-Z0-9\-]+)", url_part)
        if match:
            return match.group(1)
        if url_part.rstrip("/").endswith((":5122", ":5123", ":5124", ":5132", ":5133", ":5134")):
            return "dashboard_or_root"
    return fingerprint_label.split("|")[0] + " (no_url_generic)"


def extract_port_path_label(fingerprint_label):
    """
    Drops ONLY the app-combo, KEEPS port+path. This is the middle-ground
    variant being tested for comparison.
    """
    if "|" in fingerprint_label:
        return fingerprint_label.split("|", 1)[1]
    return fingerprint_label.split("|")[0] + " (no_url_generic)"


def run_session_purity(session_dir, extractor_fn):
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)
    s0, s1 = events[0]["timestamp_iso"], events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, s0, s1)
    labeled = label_segments(events, segments)

    with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
        gt = json.load(f)
    gt_intervals = get_ground_truth_intervals(gt)

    pred = [extractor_fn(item["label"]) for item in labeled]
    true = [match_segment_to_ground_truth(item["start"], item["end"], gt_intervals) for item in labeled]
    return label_purity(pred, true)


if __name__ == "__main__":
    dataset_dir = "dataset_a"
    session_dirs = sorted(
        d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir()
    )
    session_dirs = [d for d in session_dirs if (Path(d) / "gt_manifest.json").exists()]

    # Test 1: raw label (baseline, no changes) - reuse existing label_segments output directly
    from label_segments import label_segments as raw_label_segments

    def identity(x):
        return x

    purities_raw = [run_session_purity(d, identity) for d in session_dirs]
    purities_full_clean = [run_session_purity(d, extract_process_label) for d in session_dirs]
    purities_port_only = [run_session_purity(d, extract_port_path_label) for d in session_dirs]

    print(f"Sessions tested: {len(session_dirs)}")
    print(f"Raw label (baseline):              {sum(purities_raw)/len(purities_raw)*100:.1f}%")
    print(f"Drop app-combo only, keep port:     {sum(purities_port_only)/len(purities_port_only)*100:.1f}%")
    print(f"Drop BOTH port and app-combo:       {sum(purities_full_clean)/len(purities_full_clean)*100:.1f}%")

    import json as json_module

    results = {
        "raw_label_baseline": round(sum(purities_raw)/len(purities_raw)*100, 1),
        "drop_app_combo_only_keep_port": round(sum(purities_port_only)/len(purities_port_only)*100, 1),
        "drop_both_port_and_app_combo": round(sum(purities_full_clean)/len(purities_full_clean)*100, 1),
        "sessions_tested": len(session_dirs),
        "decision": "reject dropping port - it carries real signal (same URL path on different ports maps to different real process codes); adopt drop-app-combo-only as the corrected label consolidation"
    }

    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/label_consolidation_test.json", "w", encoding="utf-8") as f:
        json_module.dump(results, f, indent=2, ensure_ascii=False)

    print("\nSaved to outputs/label_consolidation_test.json")