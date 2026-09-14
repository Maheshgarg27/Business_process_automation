import json
import glob
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

from detect_boundaries import load_session_events, detect_boundaries_v2
from build_segments import boundaries_to_segments
from validate_labeling import get_ground_truth_intervals, match_segment_to_ground_truth, label_purity


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def events_in_range(events, start, end):
    s, e = to_dt(start), to_dt(end)
    return [ev for ev in events if s <= to_dt(ev["timestamp_iso"]) < e]


def fingerprint_with_text(segment_events):
    """
    Same as fingerprint_segment (app + URL path), but also includes a
    snippet of extracted_text where available - testing whether screen
    content helps distinguish segments that share the same app/URL.
    """
    apps, paths, texts = set(), set(), set()
    for e in segment_events:
        aa = e.get("context", {}).get("active_app") or {}
        if aa.get("app_name"):
            apps.add(aa["app_name"])
        tab = e.get("context", {}).get("active_browser_tab") or {}
        url = tab.get("url")
        if url:
            path_part = url.split("://", 1)[1].split("?")[0] if "://" in url else url.split("?")[0]
            paths.add(path_part)
        et = e.get("context", {}).get("extracted_text")
        if et and isinstance(et, dict):
            text = et.get("text", "")
            snippet = text.strip()[:40] if text else ""
            if snippet:
                texts.add(snippet)
    return (frozenset(apps), frozenset(paths), frozenset(texts))


def label_with_text(events, segments):
    fp_to_label = {}
    labeled = []
    for start, end in segments:
        seg_events = events_in_range(events, start, end)
        fp = fingerprint_with_text(seg_events)
        if fp not in fp_to_label:
            apps_str = "+".join(sorted(fp[0])) if fp[0] else "none"
            paths_str = "+".join(sorted(fp[1]))[:60] if fp[1] else ""
            label = apps_str + (f"|{paths_str}" if paths_str else "")
            fp_to_label[fp] = label
        labeled.append({"start": start, "end": end, "label": fp_to_label[fp]})
    return labeled


def run_session(session_dir):
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)
    s0, s1 = events[0]["timestamp_iso"], events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, s0, s1)
    labeled = label_with_text(events, segments)

    with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
        gt = json.load(f)
    gt_intervals = get_ground_truth_intervals(gt)

    pred = [item["label"] for item in labeled]
    true = [match_segment_to_ground_truth(item["start"], item["end"], gt_intervals) for item in labeled]
    return label_purity(pred, true)


if __name__ == "__main__":
    dataset_dir = "dataset_a"
    purities = []

    session_dirs = sorted(d for d in glob.glob(str(Path(dataset_dir) / "ses_*")) if Path(d).is_dir())
    for session_dir in session_dirs:
        if not (Path(session_dir) / "gt_manifest.json").exists():
            continue
        purities.append(run_session(session_dir))

    print(f"Tested on {len(purities)} sessions")
    print(f"Average purity WITH extracted_text added: {sum(purities)/len(purities)*100:.1f}%")
    print(f"(Compare to path-only baseline: 46.8%)")