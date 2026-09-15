import json
import pandas as pd


if __name__ == "__main__":
    segments = []
    with open("outputs/segments.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                segments.append(json.loads(line))

    df = pd.DataFrame(segments)
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df["duration_sec"] = (df["end"] - df["start"]).dt.total_seconds()

    # Labels are already clean (app-combo dropped, port kept) directly
    # from label_segments.py - no reprocessing needed here anymore.
    print(f"Total labels: {df['label'].nunique()}")

    df_clean = df[df["duration_sec"] >= 1.0].copy()
    print(f"Dropped {len(df) - len(df_clean)} noise segments out of {len(df)}")

    summary = df_clean.groupby("label").agg(
        frequency=("label", "count"),
        total_time_sec=("duration_sec", "sum"),
        avg_duration_sec=("duration_sec", "mean"),
        num_sessions=("session_id", "nunique"),
    ).reset_index().sort_values("total_time_sec", ascending=False)
    summary["total_time_min"] = summary["total_time_sec"] / 60

    print(summary.to_string())
    summary.to_csv("outputs/label_analysis_summary_final.csv", index=False)
    print(f"\nTotal unique clean labels: {len(summary)}")
    print("Saved to outputs/label_analysis_summary_final.csv")