import json
from collections import Counter

counts = Counter()
with open("outputs/segments.jsonl", encoding="utf-8") as f:
    for line in f:
        seg = json.loads(line)
        counts[seg["session_id"]] += 1

summary = {
    "per_session_counts": dict(sorted(counts.items())),
    "total_sessions": len(counts),
    "total_segments": sum(counts.values()),
}

with open("outputs/segment_counts_per_session.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("Saved.")
print(f"Total sessions: {summary['total_sessions']}")
print(f"Total segments: {summary['total_segments']}")