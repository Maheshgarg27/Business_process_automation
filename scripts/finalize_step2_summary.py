import json
import pandas as pd


def extract_port_path_label(fingerprint_label):
    """
    Drops only the app-combination prefix, keeps port+path - the
    evidence-based version (see work log: dropping port hurt purity
    46.8% -> 38.3%, so port was kept).
    """
    if "|" in fingerprint_label:
        return fingerprint_label.split("|", 1)[1]
    return fingerprint_label.split("|")[0] + " (no_url_generic)"


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
    df["clean_label"] = df["label"].apply(extract_port_path_label)

    print(f"Unique raw labels: {df['label'].nunique()}")
    print(f"Unique clean labels: {df['clean_label'].nunique()}")

    df_clean = df[df["duration_sec"] >= 1.0].copy()
    print(f"Dropped {len(df) - len(df_clean)} noise segments out of {len(df)}")

    summary_final = df_clean.groupby("clean_label").agg(
        frequency=("clean_label", "count"),
        total_time_sec=("duration_sec", "sum"),
        avg_duration_sec=("duration_sec", "mean"),
        num_sessions=("session_id", "nunique"),
    ).reset_index().sort_values("total_time_sec", ascending=False)
    summary_final["total_time_min"] = summary_final["total_time_sec"] / 60

    print(summary_final.to_string())
    summary_final.to_csv("outputs/label_analysis_summary_final.csv", index=False)
    print(f"\nTotal unique clean labels: {len(summary_final)}")
    print("Saved to outputs/label_analysis_summary_final.csv")