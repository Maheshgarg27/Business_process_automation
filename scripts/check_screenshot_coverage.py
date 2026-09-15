
"""
Run this LOCALLY, from your scripts/ folder.
Checks, for every session and chunk in dataset_a, how many screenshot_smart
events REFERENCE a file, versus how many of those files ACTUALLY EXIST on
disk in that chunk's screenshots/ folder. This tells us whether the missing
files we found are a one-session fluke or a dataset-wide gap.

Usage:
    python check_screenshot_coverage.py --dataset-root ../dataset_a
"""
import json
import glob
import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="dataset_a")
    args = ap.parse_args()

    session_dirs = sorted(d for d in glob.glob(str(Path(args.dataset_root) / "ses_*")) if Path(d).is_dir())
    print(f"Found {len(session_dirs)} sessions\n")

    total_expected = 0
    total_present = 0
    session_summaries = []

    for session_dir in session_dirs:
        session_name = Path(session_dir).name
        session_expected = 0
        session_present = 0

        for chunk_dir in sorted(glob.glob(str(Path(session_dir) / "chunk_*"))):
            events_path = Path(chunk_dir) / "events.jsonl"
            screenshots_dir = Path(chunk_dir) / "screenshots"
            if not events_path.exists():
                continue

            expected_files = set()
            with open(events_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ev = json.loads(line)
                    if ev.get("event_type") == "screenshot_smart":
                        fname = (ev.get("payload", {}) or {}).get("file_reference", {}).get("filename")
                        if fname:
                            expected_files.add(fname)

            actual_files = set()
            if screenshots_dir.exists():
                actual_files = {p.name for p in screenshots_dir.glob("*.jpg")}

            present = len(expected_files & actual_files)
            session_expected += len(expected_files)
            session_present += present

        total_expected += session_expected
        total_present += session_present
        rate = (100 * session_present / session_expected) if session_expected else 100
        session_summaries.append((session_name, session_expected, session_present, rate))
        flag = "  <-- MOSTLY MISSING" if rate < 50 else ""
        print(f"{session_name}: expected={session_expected}  present={session_present}  coverage={rate:.0f}%{flag}")

    print(f"\n=== TOTALS ===")
    overall_rate = (100 * total_present / total_expected) if total_expected else 0
    print(f"Total screenshot files referenced across all sessions: {total_expected}")
    print(f"Total actually present on disk:                        {total_present}")
    print(f"Overall coverage:                                      {overall_rate:.1f}%")

    bad_sessions = [s for s in session_summaries if s[3] < 50]
    print(f"\nSessions with <50% screenshot coverage: {len(bad_sessions)} / {len(session_summaries)}")
    for name, exp, pres, rate in bad_sessions:
        print(f"  {name}: {pres}/{exp} ({rate:.0f}%)")


if __name__ == "__main__":
    main()