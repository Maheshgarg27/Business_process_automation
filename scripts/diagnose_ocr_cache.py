"""
Run this LOCALLY, from your scripts/ folder, next to ocr_text_cache.json.
Figures out WHY so many cached OCR entries are empty strings:
  - file doesn't exist at that path?
  - file exists but is 0 bytes / corrupt?
  - file exists and opens fine, but Tesseract crashed (hidden by the
    silent try/except in the original script)?
  - file exists, opens fine, Tesseract runs fine, but genuinely found no text?

Usage:
    python diagnose_ocr_cache.py --cache ocr_text_cache.json --sample 10
"""
import json
import argparse
from pathlib import Path

import pytesseract
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="ocr_text_cache.json")
    ap.add_argument("--sample", type=int, default=10, help="How many empty entries to inspect closely")
    args = ap.parse_args()

    with open(args.cache, encoding="utf-8") as f:
        cache = json.load(f)

    total = len(cache)
    empty = [k for k, v in cache.items() if not v.strip()]
    nonempty = total - len(empty)

    print(f"Total cached images: {total}")
    print(f"Non-empty OCR text:  {nonempty}  ({100*nonempty/total:.1f}%)")
    print(f"Empty OCR text:      {len(empty)}  ({100*len(empty)/total:.1f}%)")
    print()

    if not empty:
        print("No empty entries -- nothing to diagnose.")
        return

    print(f"--- Inspecting first {min(args.sample, len(empty))} empty entries ---\n")
    reasons = {"missing_file": 0, "zero_byte_file": 0, "pil_error": 0,
               "tesseract_error": 0, "genuinely_empty": 0}

    for path_str in empty[:args.sample]:
        p = Path(path_str)
        print(f"Path: {path_str}")

        if not p.exists():
            print("  -> FILE DOES NOT EXIST at this path\n")
            reasons["missing_file"] += 1
            continue

        size = p.stat().st_size
        print(f"  File exists, size = {size} bytes")
        if size == 0:
            print("  -> ZERO-BYTE FILE (corrupt/empty capture)\n")
            reasons["zero_byte_file"] += 1
            continue

        try:
            img = Image.open(p)
            img.load()  # force actual decode, not just header read
            print(f"  Opens fine with PIL, dimensions = {img.size}")
        except Exception as e:
            print(f"  -> PIL FAILED TO OPEN: {type(e).__name__}: {e}\n")
            reasons["pil_error"] += 1
            continue

        try:
            raw = pytesseract.image_to_string(img, lang="jpn")
            text = " ".join(raw.split())
            if text:
                print(f"  -> RE-RUN NOW PRODUCES TEXT: '{text[:80]}...' (was empty in cache -- transient issue?)\n")
                reasons["genuinely_empty"] += 1  # inconsistent, but not a hard error
            else:
                print(f"  -> Tesseract ran fine, genuinely found no text in this image\n")
                reasons["genuinely_empty"] += 1
        except Exception as e:
            print(f"  -> TESSERACT CALL FAILED: {type(e).__name__}: {e}\n")
            reasons["tesseract_error"] += 1

    print("--- Summary of sampled empty entries ---")
    for reason, count in reasons.items():
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()