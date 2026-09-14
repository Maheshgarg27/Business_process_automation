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

print(df.shape)
print(df["label"].nunique(), "unique labels")
print(df["session_id"].nunique(), "unique sessions")
print(df.head(10))