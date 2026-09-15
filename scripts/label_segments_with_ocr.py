"""
Run this LOCALLY on your machine, from your project root (where dataset_a/,
scripts/, etc. live). Requires: pip install pytesseract pillow --break-system-packages
and Tesseract itself with the Japanese pack installed:
    sudo apt-get install tesseract-ocr tesseract-ocr-jpn   (Linux)
    brew install tesseract tesseract-lang                   (Mac)

WHAT THIS DOES
Same idea as label_segments_with_text.py (your rejected extracted_text
experiment), but the new signal comes from OCR-ing screenshots instead of
the sparse extracted_text field. For every segment that has NO URL path
(i.e. would otherwise fall into "<App> (no_url_generic)"), it:
  1. finds screenshot_smart events whose timestamp falls in the segment window
  2. picks the LAST one (most "settled" state)
  3. runs Tesseract OCR (Japanese) on it, with in-memory caching by image path
  4. folds a tail-slice of the OCR text into the fingerprint as a new signal

Then it re-runs your exact purity metric (validate_labeling.label_purity)
across all Dataset A sessions with ground truth, and reports the average,
same as before -- compare directly to the 46.8% baseline.

USAGE
    python label_segments_with_ocr.py --dataset-root dataset_a --sessions 10
    python label_segments_with_ocr.py --dataset-root dataset_a   # full 63, slower
"""
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

import pytesseract
from PIL import Image

from detect_boundaries import detect_boundaries_v2
from build_segments import boundaries_to_segments
from validate_labeling import get_ground_truth_intervals, match_segment_to_ground_truth, label_purity
from label_segments import fingerprint_segment as fingerprint_baseline

_ocr_cache = {}  # image path -> normalized OCR text, avoids re-OCRing the same image
_cache_dirty = False  # tracks whether we've OCR'd anything new since loading the cache file


def load_ocr_cache(cache_path):
    """Load previously-OCR'd text from disk, if it exists, so re-runs don't
    re-OCR images whose text we already have."""
    global _ocr_cache
    p = Path(cache_path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _ocr_cache = json.load(f)
        print(f"Loaded {len(_ocr_cache)} cached OCR results from {cache_path}")
    else:
        print(f"No existing OCR cache found at {cache_path} -- starting fresh")


def save_ocr_cache(cache_path):
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(_ocr_cache, f, ensure_ascii=False)
    print(f"Saved {len(_ocr_cache)} OCR results to {cache_path}")


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_session_events_with_chunkdir(session_dir):
    """Like load_session_events, but tags each event with its chunk directory
    so we can resolve screenshot file paths later."""
    events = []
    for chunk_dir in sorted(glob.glob(str(Path(session_dir) / "chunk_*"))):
        ev_path = Path(chunk_dir) / "events.jsonl"
        if not ev_path.exists():
            continue
        with open(ev_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                ev["_chunk_dir"] = chunk_dir
                events.append(ev)
    events.sort(key=lambda e: e["timestamp_iso"])
    return events


def events_in_range(events, start, end):
    s, e = to_dt(start), to_dt(end)
    return [ev for ev in events if s <= to_dt(ev["timestamp_iso"]) < e]


def ocr_image(image_path):
    """OCR one image, checking the (possibly disk-loaded) cache first.
    Returns normalized text, or '' on any failure."""
    global _cache_dirty
    key = str(image_path)
    if key in _ocr_cache:
        return _ocr_cache[key]  # already OCR'd, either this run or a previous one
    text = ""
    try:
        if Path(image_path).exists():
            img = Image.open(image_path)
            raw = pytesseract.image_to_string(img, lang="jpn")
            text = " ".join(raw.split())  # collapse whitespace/newlines
    except Exception:
        text = ""
    _ocr_cache[key] = text
    _cache_dirty = True  # new work done -> worth saving at the end
    return text


def get_screenshot_text(segment_events):
    """Find the last screenshot_smart event in this segment's window and OCR it."""
    shots = [e for e in segment_events if e.get("event_type") == "screenshot_smart"]
    if not shots:
        return ""
    shots.sort(key=lambda e: e["timestamp_iso"])
    last = shots[-1]
    fname = (last.get("payload", {}) or {}).get("file_reference", {}).get("filename")
    if not fname:
        return ""
    img_path = Path(last["_chunk_dir"]) / "screenshots" / fname
    return ocr_image(img_path)


def fingerprint_with_ocr(segment_events):
    apps, paths = set(), set()
    for e in segment_events:
        aa = e.get("context", {}).get("active_app") or {}
        if aa.get("app_name"):
            apps.add(aa["app_name"])
        tab = e.get("context", {}).get("active_browser_tab") or {}
        url = tab.get("url")
        if url:
            path_part = url.split("://", 1)[1].split("?")[0] if "://" in url else url.split("?")[0]
            paths.add(path_part)

    ocr_snippet = ""
    if not paths:
        # only pay the OCR cost where it can actually help -- segments with
        # no URL signal, i.e. the ones currently collapsing into
        # "<App> (no_url_generic)"
        text = get_screenshot_text(segment_events)
        # tail-slice: in our benchmark, Word's ribbon/toolbar OCRs to garbage
        # and reads first (top of screen); real document body text reads
        # later in natural top-to-bottom order, so the tail is more likely
        # to carry the distinguishing content.
        ocr_snippet = text[-150:] if text else ""

    return (frozenset(apps), frozenset(paths), ocr_snippet)


def label_generic(events, segments, fingerprint_fn):
    """Generic labeler parameterized by whichever fingerprint function to use,
    so baseline and OCR versions run on the IDENTICAL segment list."""
    fp_to_label = {}
    labeled = []
    for start, end in segments:
        seg_events = events_in_range(events, start, end)
        fp = fingerprint_fn(seg_events)
        if fp not in fp_to_label:
            apps_str = "+".join(sorted(fp[0])) if fp[0] else "none"
            paths_str = "+".join(sorted(fp[1]))[:60] if fp[1] else ""
            if paths_str:
                label = paths_str
            elif len(fp) > 2 and fp[2]:
                label = f"{apps_str} (ocr:{fp[2][:40]})"
            else:
                label = f"{apps_str} (no_url_generic)"
            fp_to_label[fp] = label
        labeled.append({"start": start, "end": end, "label": fp_to_label[fp]})
    return labeled


def run_session(session_dir):
    events = load_session_events_with_chunkdir(session_dir)
    if not events:
        return None
    boundaries = detect_boundaries_v2(events)
    s0, s1 = events[0]["timestamp_iso"], events[-1]["timestamp_iso"]
    segments = boundaries_to_segments(boundaries, s0, s1)

    with open(Path(session_dir) / "gt_manifest.json", encoding="utf-8") as f:
        gt = json.load(f)
    gt_intervals = get_ground_truth_intervals(gt)
    true = [match_segment_to_ground_truth(s, e, gt_intervals) for s, e in segments]

    # SAME segments, SAME session, two different fingerprint functions --
    # this is what makes the comparison apples-to-apples.
    baseline_labeled = label_generic(events, segments, fingerprint_baseline)
    ocr_labeled = label_generic(events, segments, fingerprint_with_ocr)

    baseline_pred = [item["label"] for item in baseline_labeled]
    ocr_pred = [item["label"] for item in ocr_labeled]

    return label_purity(baseline_pred, true), label_purity(ocr_pred, true)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="dataset_a")
    ap.add_argument("--sessions", type=int, default=None,
                     help="Limit to first N sessions for a quick partial read (default: all 63)")
    ap.add_argument("--ocr-cache", default="ocr_text_cache.json",
                     help="Where OCR'd text is saved/loaded from, so re-runs skip already-OCR'd images")
    args = ap.parse_args()

    load_ocr_cache(args.ocr_cache)

    session_dirs = sorted(d for d in glob.glob(str(Path(args.dataset_root) / "ses_*")) if Path(d).is_dir())
    session_dirs = [d for d in session_dirs if (Path(d) / "gt_manifest.json").exists()]
    if args.sessions:
        session_dirs = session_dirs[:args.sessions]

    print(f"Testing on {len(session_dirs)} sessions (baseline vs OCR, same segments each time)...")
    baseline_purities, ocr_purities = [], []
    for i, session_dir in enumerate(session_dirs, 1):
        result = run_session(session_dir)
        if result is not None:
            b, o = result
            baseline_purities.append(b)
            ocr_purities.append(o)
            print(f"  [{i}/{len(session_dirs)}] {Path(session_dir).name}: baseline={b*100:.1f}%  ocr={o*100:.1f}%  delta={100*(o-b):+.1f}")

    avg_baseline = sum(baseline_purities) / len(baseline_purities) * 100
    avg_ocr = sum(ocr_purities) / len(ocr_purities) * 100
    print(f"\nAverage baseline purity (these {len(baseline_purities)} sessions, no OCR): {avg_baseline:.1f}%")
    print(f"Average purity WITH OCR added (same sessions):                  {avg_ocr:.1f}%")
    print(f"Delta (apples-to-apples, same sessions):                       {avg_ocr - avg_baseline:+.1f} points")
    print(f"\n(For reference, your full 63-session baseline was 46.8% -- the 'Average baseline'")
    print(f" line above is what THESE specific sessions score without OCR, which is the correct")
    print(f" number to compare against, not the full-dataset 46.8%.)")
    print(f"\nTotal unique images in cache: {len(_ocr_cache)}")

    if _cache_dirty:
        save_ocr_cache(args.ocr_cache)
    else:
        print("(No new OCR work done this run -- everything came from the existing cache file.)")


if __name__ == "__main__":
    main()