from detect_boundaries import load_session_events, detect_boundaries_v2

def boundaries_to_segments(boundaries, session_start, session_end):
    """Turn sorted boundary timestamps into (start, end) segment pairs."""
    boundaries = sorted(boundaries)
    points = sorted(set([session_start] + boundaries + [session_end]))
    return [(points[i], points[i+1]) for i in range(len(points) - 1)]


if __name__ == "__main__":
    from datetime import datetime

    def to_dt(ts):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    session_dir = "dataset_a/ses_20260630-124826-CHAITANYA0BCF"
    events = load_session_events(session_dir)
    boundaries = detect_boundaries_v2(events)

    session_start = events[0]["timestamp_iso"]
    session_end = events[-1]["timestamp_iso"]

    segments = boundaries_to_segments(boundaries, session_start, session_end)
    durations = sorted((to_dt(e) - to_dt(s)).total_seconds() for s, e in segments)

    print(f"Total segments: {len(segments)}")
    print(f"Min duration: {durations[0]:.3f}s")
    print(f"Max duration: {durations[-1]:.1f}s")
    print(f"Median duration: {durations[len(durations)//2]:.3f}s")
    print(f"Segments under 1s: {sum(1 for d in durations if d < 1)} "
          f"({sum(1 for d in durations if d < 1)/len(durations)*100:.1f}%)")