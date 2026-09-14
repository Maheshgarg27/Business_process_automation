import json
import random
from pathlib import Path
from datetime import datetime


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


if __name__ == "__main__":
    segments = []
    with open("outputs/segments.jsonl", encoding="utf-8") as f:
        for line in f:
            segments.append(json.loads(line))

    random.seed(42)
    sample = random.sample(segments, min(8, len(segments)))

    for seg in sample:
        print(f"--- {seg['session_id']}  [{seg['label']}] ---")
        print(f"    {seg['start']} -> {seg['end']}")

        session_dir = Path("dataset_b") / seg["session_id"]
        seg_start, seg_end = to_dt(seg["start"]), to_dt(seg["end"])
        found_text = None

        for chunk_dir in sorted(session_dir.glob("chunk_*")):
            ef = chunk_dir / "events.jsonl"
            if not ef.exists():
                continue
            with open(ef, encoding="utf-8") as f:
                for line in f:
                    e = json.loads(line)
                    ets = to_dt(e["timestamp_iso"])
                    if seg_start <= ets < seg_end:
                        et = e.get("context", {}).get("extracted_text")
                        if et and isinstance(et, dict) and et.get("text", "").strip():
                            found_text = et["text"].strip()[:150]
                            break
            if found_text:
                break

        if found_text:
            print(f"    extracted_text: {found_text!r}")
        else:
            print("    (no extracted_text found in this segment)")
        print()