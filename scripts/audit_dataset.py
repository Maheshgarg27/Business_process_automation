import json
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(path):
    """Read a JSONL file one line at a time."""
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: invalid JSON in {path} at line {line_number}")

    return records


def audit_dataset(dataset_name):
    dataset_dir = ROOT / dataset_name

    sessions = [
        p for p in dataset_dir.iterdir()
        if p.is_dir() and p.name.startswith("ses_")
    ]

    total_chunks = 0
    total_events = 0

    event_types = Counter()
    layers = Counter()
    applications = Counter()

    earliest_timestamp = None
    latest_timestamp = None

    ground_truth_processes = Counter()
    ground_truth_variants = Counter()

    print("\n" + "=" * 60)
    print(dataset_name.upper())
    print("=" * 60)

    print(f"Sessions: {len(sessions)}")

    for session in sorted(sessions):

        # Find all chunk directories automatically.
        chunks = [
            p for p in session.iterdir()
            if p.is_dir() and p.name.startswith("chunk_")
        ]

        total_chunks += len(chunks)

        for chunk in chunks:

            # Support both possible event-file naming styles.
            event_files = list(chunk.glob("events.jsonl"))

            for event_file in event_files:

                events = load_jsonl(event_file)
                total_events += len(events)

                for event in events:

                    event_type = event.get("event_type")
                    layer = event.get("layer")

                    if event_type:
                        event_types[event_type] += 1

                    if layer:
                        layers[layer] += 1

                    context = event.get("context", {})

                    if isinstance(context, dict):
                        app = context.get("active_app")

                        if isinstance(app,str):
                            applications[app] += 1

                    timestamp = event.get("timestamp_ms")

                    if isinstance(timestamp, (int, float)):
                        if earliest_timestamp is None or timestamp < earliest_timestamp:
                            earliest_timestamp = timestamp

                        if latest_timestamp is None or timestamp > latest_timestamp:
                            latest_timestamp = timestamp

        # Dataset A contains ground truth.
        gt_file = session / "gt.jsonl"

        if gt_file.exists():

            gt_records = load_jsonl(gt_file)

            for record in gt_records:

                process = record.get("current_process")
                variant = record.get("process_variant")

                if process:
                    ground_truth_processes[process] += 1

                if variant:
                    ground_truth_variants[variant] += 1

    print(f"Chunks: {total_chunks}")
    print(f"Events: {total_events}")

    if earliest_timestamp and latest_timestamp:
        start = datetime.fromtimestamp(
            earliest_timestamp / 1000,
            tz=timezone.utc
        )
        end = datetime.fromtimestamp(
            latest_timestamp / 1000,
            tz=timezone.utc
        )

        print(f"Time range: {start} → {end}")

    print("\nEvent types:")
    for name, count in event_types.most_common():
        print(f"  {name}: {count}")

    print("\nLayers:")
    for name, count in layers.most_common():
        print(f"  {name}: {count}")

    print("\nTop applications:")
    for name, count in applications.most_common(20):
        print(f"  {name}: {count}")

    if ground_truth_processes:
        print("\nGround-truth processes:")
        for name, count in ground_truth_processes.most_common():
            print(f"  {name}: {count}")

    if ground_truth_variants:
        print("\nGround-truth variants:")
        for name, count in ground_truth_variants.most_common():
            print(f"  {name}: {count}")


if __name__ == "__main__":
    audit_dataset("dataset_a")
    audit_dataset("dataset_b")