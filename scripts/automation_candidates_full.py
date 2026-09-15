import json
import re
from pathlib import Path
from datetime import datetime
import pandas as pd


def to_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def extract_route_only(label):
    m = re.search(r"#/([a-zA-Z0-9\-]+)", label)
    return m.group(1) if m else None


_session_events_cache = {}


def get_session_events(session_id, dataset_dir="dataset_b"):
    """Load and cache raw events for a session, so repeated lookups are fast."""
    if session_id not in _session_events_cache:
        events = []
        session_dir = Path(dataset_dir) / session_id
        for chunk_dir in sorted(session_dir.glob("chunk_*")):
            ef = chunk_dir / "events.jsonl"
            if not ef.exists():
                continue
            with open(ef, encoding="utf-8") as f:
                for line in f:
                    events.append(json.loads(line))
        events.sort(key=lambda e: e["timestamp_iso"])
        _session_events_cache[session_id] = events
    return _session_events_cache[session_id]


def apps_in_range(session_id, start, end):
    """Apps active during a segment's time range - read from raw events,
    since the final segment label no longer carries app-combo info
    (intentionally dropped for label consistency)."""
    events = get_session_events(session_id)
    apps = set()
    for e in events:
        ets = to_dt(e["timestamp_iso"])
        if start <= ets < end:
            aa = e.get("context", {}).get("active_app") or {}
            if aa.get("app_name"):
                apps.add(aa["app_name"])
    return apps


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
    ).reset_index()
    summary["total_time_min"] = summary["total_time_sec"] / 60

    complexity_rows = []
    for route in summary["route"]:
        sub = df_routes[df_routes["route"] == route]
        all_apps = set()
        for _, row in sub.iterrows():
            all_apps |= apps_in_range(row["session_id"], row["start"], row["end"])
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