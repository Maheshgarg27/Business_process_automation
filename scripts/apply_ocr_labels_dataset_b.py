"""
Run this LOCALLY, from your scripts/ folder. Applies the OCR-augmentation
idea (validated on Dataset A: +1.3pts under only 14.8% screenshot coverage)
to your real deliverable: segments.jsonl for Dataset B, which has 100%
screenshot coverage. Only segments whose label contains "(no_url_generic)"
are touched -- every URL-based label is copied through unchanged.

Usage:
    python apply_ocr_labels_dataset_b.py --dataset-root ../dataset_b --segments ../outputs/segments.jsonl --out ../outputs/segments_with_ocr.jsonl

Adjust paths to match wherever your real dataset_b and segments.jsonl live.
"""
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime

import pytesseract
from PIL import Image

_ocr_cache = {}
_cache_dirty = False
_session_events_cache = {}


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_ocr_cache(path):
    global _ocr_cache
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _ocr_cache = json.load(f)
        print(f"Loaded {len(_ocr_cache)} cached OCR results from {path}")
    else:
        print(f"No existing cache at {path} -- starting fresh")


def save_ocr_cache(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_ocr_cache, f, ensure_ascii=False)
    print(f"Saved {len(_ocr_cache)} OCR results to {path}")


def ocr_image(image_path):
    global _cache_dirty
    key = str(image_path)
    if key in _ocr_cache:
        return _ocr_cache[key]
    text = ""
    try:
        if Path(image_path).exists():
            img = Image.open(image_path)
            img.load()
            raw = pytesseract.image_to_string(img, lang="jpn")
            text = " ".join(raw.split())
    except Exception:
        text = ""
    _ocr_cache[key] = text
    _cache_dirty = True
    return text


def load_session_events(session_dir):
    key = str(session_dir)
    if key in _session_events_cache:
        return _session_events_cache[key]
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
    _session_events_cache[key] = events
    return events


def find_last_screenshot_text(dataset_root, session_id, start, end):
    session_dir = Path(dataset_root) / session_id
    if not session_dir.exists():
        return ""
    events = load_session_events(session_dir)
    s, e = to_dt(start), to_dt(end)
    shots = [ev for ev in events if ev.get("event_type") == "screenshot_smart"
             and s <= to_dt(ev["timestamp_iso"]) < e]
    if not shots:
        return ""
    shots.sort(key=lambda ev: ev["timestamp_iso"])
    last = shots[-1]
    fname = (last.get("payload", {}) or {}).get("file_reference", {}).get("filename")
    if not fname:
        return ""
    img_path = Path(last["_chunk_dir"]) / "screenshots" / fname
    return ocr_image(img_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="dataset_b")
    ap.add_argument("--segments", default="segments.jsonl")
    ap.add_argument("--out", default="segments_with_ocr.jsonl")
    ap.add_argument("--ocr-cache", default="ocr_text_cache_dataset_b.json")
    args = ap.parse_args()

    load_ocr_cache(args.ocr_cache)

    segs = []
    with open(args.segments, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segs.append(json.loads(line))
    print(f"Loaded {len(segs)} segments from {args.segments}")

    generic_count = upgraded_count = still_generic_count = 0
    labels_before, labels_after = set(), set()
    out_segs = []

    for seg in segs:
        label = seg["label"]
        labels_before.add(label)
        if "(no_url_generic)" not in label:
            out_segs.append(seg)
            labels_after.add(label)
            continue

        generic_count += 1
        app_name = label.replace(" (no_url_generic)", "")
        text = find_last_screenshot_text(args.dataset_root, seg["session_id"], seg["start"], seg["end"])
        snippet = text[-150:] if text else ""

        new_seg = dict(seg)
        if snippet:
            new_label = f"{app_name} (ocr:{snippet[:40]})"
            new_seg["label"] = new_label
            new_seg["ocr_text"] = snippet
            upgraded_count += 1
            labels_after.add(new_label)
        else:
            still_generic_count += 1
            labels_after.add(label)

        out_segs.append(new_seg)

    with open(args.out, "w", encoding="utf-8") as f:
        for seg in out_segs:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")

    print(f"\n=== RESULTS ===")
    print(f"Total segments:                        {len(segs)}")
    print(f"no_url_generic segments:               {generic_count}")
    print(f"  -> upgraded with real OCR text:      {upgraded_count}")
    print(f"  -> still generic (no shot/empty OCR): {still_generic_count}")
    print(f"\nUnique labels BEFORE: {len(labels_before)}")
    print(f"Unique labels AFTER:  {len(labels_after)}")
    print(f"\nOutput written to: {args.out}")

    if _cache_dirty:
        save_ocr_cache(args.ocr_cache)


if __name__ == "__main__":
    main()