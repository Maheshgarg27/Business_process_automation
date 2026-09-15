import json
import re
import pandas as pd


def extract_route_only(label):
    """Labels are already clean - just search the label directly for the URL route."""
    m = re.search(r"#/([a-zA-Z0-9\-]+)", label)
    return m.group(1) if m else None


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
    df = df[df["duration_sec"] >= 1.0].copy()
    df["route"] = df["label"].apply(extract_route_only)
    df_routes = df[df["route"].notna()].copy()

    summary = df_routes.groupby("route").agg(
        frequency=("route", "count"),
        total_time_sec=("duration_sec", "sum"),
        avg_duration_sec=("duration_sec", "mean"),
        num_sessions=("session_id", "nunique"),
    ).reset_index().sort_values("total_time_sec", ascending=False)
    summary["total_time_min"] = summary["total_time_sec"] / 60

    print(summary.to_string())
    summary.to_csv("outputs/automation_candidates_by_route.csv", index=False)
    print("\nSaved to outputs/automation_candidates_by_route.csv")