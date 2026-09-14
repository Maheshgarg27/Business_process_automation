import json
import re
import pandas as pd


def extract_route_only(label):
    if "|" in label:
        url = label.split("|", 1)[1]
        m = re.search(r"#/([a-zA-Z0-9\-]+)", url)
        return m.group(1) if m else None
    return None


def apps_in_label(label):
    if "|" in label:
        app_part = label.split("|", 1)[0]
    else:
        app_part = label.split(" (")[0]
    return set(app_part.split("+"))


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
    df["apps"] = df["label"].apply(apps_in_label)
    df_routes = df[df["route"].notna()].copy()

    # base stats: frequency, time, sessions
    summary = df_routes.groupby("route").agg(
        frequency=("route", "count"),
        total_time_sec=("duration_sec", "sum"),
        avg_duration_sec=("duration_sec", "mean"),
        num_sessions=("session_id", "nunique"),
    ).reset_index()
    summary["total_time_min"] = summary["total_time_sec"] / 60

    # complexity stats: distinct apps, duration std
    complexity_rows = []
    for route in summary["route"]:
        sub = df_routes[df_routes["route"] == route]
        all_apps = set()
        for a in sub["apps"]:
            all_apps |= a
        complexity_rows.append({
            "route": route,
            "num_distinct_apps": len(all_apps),
            "apps_involved": "+".join(sorted(all_apps)),
            "duration_std_sec": sub["duration_sec"].std(),
            "duration_min_sec": sub["duration_sec"].min(),
            "duration_max_sec": sub["duration_sec"].max(),
        })
    complexity_df = pd.DataFrame(complexity_rows)

    final = summary.merge(complexity_df, on="route").sort_values("total_time_sec", ascending=False)

    print(final.to_string())
    final.to_csv("outputs/automation_candidates_full.csv", index=False)
    print("\nSaved to outputs/automation_candidates_full.csv")