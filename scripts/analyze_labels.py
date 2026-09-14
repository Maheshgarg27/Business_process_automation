import json
import pandas as pd

segments = []
with open("outputs/segments.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            segments.append(json.loads(line))

df = pd.DataFrame(segments)
df["start"] = pd.to_datetime(df["start"])
df["end"] = pd.to_datetime(df["end"])
df["duration_sec"] = (df["end"] - df["start"]).dt.total_seconds()

summary = df.groupby("label").agg(
    frequency=("label", "count"),
    total_time_sec=("duration_sec", "sum"),
    avg_duration_sec=("duration_sec", "mean"),
    num_sessions=("session_id", "nunique"),
).reset_index()

summary["total_time_min"] = summary["total_time_sec"] / 60
summary = summary.sort_values("total_time_sec", ascending=False)

print(summary.to_string())
summary.to_csv("outputs/label_analysis_summary.csv", index=False)
print(f"\nSaved to outputs/label_analysis_summary.csv")
print(f"Total unique labels: {len(summary)}")