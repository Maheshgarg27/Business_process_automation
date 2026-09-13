# Work Log

## Day 1 — Dataset Understanding and Exploration

### Objective

Understand the structure of Dataset A and Dataset B and determine what information is available for business-process discovery and execution segmentation.

### Work Completed

- Inspected the directory structure of Dataset A and Dataset B.
- Analyzed sessions, chunks, events, and event layers.
- Examined event-type distributions in both datasets.
- Analyzed application usage and application transitions.
- Studied Dataset A ground-truth process executions.
- Analyzed process execution frequencies and variants.
- Analyzed execution durations.
- Examined executions that continue across recording chunks.
- Explored Dataset B session durations and event timing.
- Examined screenshot events and available screenshot files.
- Investigated extracted text availability in screenshot events.

### Key Findings

- Dataset A contains ground-truth information about process executions and variants.
- Dataset B does not contain ground-truth process labels.
- A session represents a continuous recording, while a chunk is a recording bucket and is not necessarily a business-process boundary.
- Dataset B therefore requires execution segmentation and process discovery from the raw activity logs.
- Event-to-event temporal gaps may provide a useful signal for identifying execution boundaries, but a time gap alone is not sufficient.
- Dataset A and Dataset B have the same general event-log structure but differ in the processes, departments, and applications represented.

### Initial Direction

Use Dataset A to study general behavioral signals associated with execution boundaries and validate the approach using its ground truth. The resulting general approach should then be applied to Dataset B, where executions and process labels must be discovered.

### Next Step

Investigate and develop an execution-segmentation approach using the ground truth available in Dataset A.

## Day 2

**What I built:**
- `evaluate()` / `evaluate_full()` — a metric function that compares predicted
  task-boundary timestamps against ground truth (`gt_manifest.json`), computing
  recall, precision, and F1 (3-second match tolerance). Validated against known
  answers before trusting it (sanity check: correct answers score 100%).
- `detect_boundaries_v1()` — simplest possible boundary detector: treats every
  `app_switch` event as a candidate task boundary.
- `detect_boundaries_v2()` — same as v1, plus also treats `browser_navigation`
  events as candidate boundaries.
- `run_all_sessions.py` — runs the detector + metric across all 63 sessions in
  Dataset A and averages the results, instead of trusting a single session.

**Results (averaged across all 63 sessions in Dataset A):**

| Detector | Recall | Precision | F1 |
|---|---|---|---|
| v1: app_switch only | 64.6% | 35.2% | 45.3% |
| v2: + browser_navigation | 85.1% | 36.6% | **50.8%** |

**Key finding:** Recall alone was misleading — the detector predicts ~52,000
candidate boundaries total vs. only 2,009 real ones (26x over-prediction), so
high recall was partly inflated by simply predicting more. Precision (~36%)
is the real bottleneck and the next thing to improve, not just adding more
signals.

**Next step:** reduce false-positive predictions (e.g. collapsing rapid
back-to-back app switches into a single boundary) to raise precision without
losing recall.


**Diagnosed false positives before fixing (Step G):**
Inspected actual false-positive predictions instead of guessing a fix.
Found a clear pattern: rapid, same-app clusters of `app_switch` events
firing within 50-200ms of each other (e.g. "Chrome -> Chrome -> Chrome"),
clearly UI noise rather than real task transitions (real segments are
~31.7s on average).

**Built a filter based on that diagnosis (Step H):**
Implemented `merge_close_boundaries()` — merges candidate boundaries that
occur within a minimum time gap (tested 5s, 10s, 15s thresholds), since
no real task execution was shorter than ~16.6s.

**Result: the filter did NOT improve performance — it was measured and rejected.**

| Version | Recall | Precision | F1 |
|---|---|---|---|
| v2 (no filter) | 85.1% | 36.6% | **50.8%** |
| v3, min_gap=10s | 78.9% | 35.4% | 48.7% |
| v3, min_gap=5s | 83.6% | 24.3% | 37.6% |
| v3, min_gap=15s | 43.2% | 23.3% | 30.2% |

**Why it failed:** the merge logic collapsed not just noisy clusters, but
also legitimate, closely-spaced real transitions, which hurt recall without
a corresponding gain in precision.

**Decision:** v2 remains the best validated detector. v3 was not adopted.
This is a deliberate example of testing a well-justified idea empirically
rather than assuming it works, and rejecting it when the data disagreed.

## Day 2 (continued): threshold sweep

Swept `min_gap_seconds` across 9 values (1s, 2s, 3s, 5s, 7s, 10s, 12s, 15s, 20s)
on the full 63-session dataset, to check if a different threshold could make
the merge filter work where 10s didn't.

| min_gap | Recall | Precision | F1 |
|---|---|---|---|
| 0 (v2, no filter) | 85.1% | 36.6% | **50.8%** |
| 1s | 85.1% | 28.0% | 42.0% |
| 5s | 83.6% | 24.3% | 37.6% |
| 10s | 78.9% | 35.4% | 48.7% |
| 15s | 43.2% | 23.3% | 30.2% |
| 20s | 37.4% | 26.1% | 30.6% |

**No threshold beat v2 on both recall and precision.** The merge-filter
approach itself is rejected, not just one bad threshold choice - confirmed
across the full range, not a single arbitrary guess.

**Decision:** v2 (app_switch + browser_navigation, no filtering) remains
the best validated detector: recall 85.1%, precision 36.6%, F1 50.8%.

## Day 2 (continued): identity-based filter 

Tried filtering by app identity instead of time proximity — keep a boundary
only if the app/URL actually changed from the last kept one. Reasoning: this
should collapse pure same-app noise (Chrome->Chrome->Chrome) regardless of
timing, without touching genuine fast different-app transitions.

**Result: also rejected, based on evidence.**

| Detector | Recall | Precision | F1 |
|---|---|---|---|
| v2 (no filter, baseline) | 85.1% | 36.6% | **50.8%** |
| v3 (min_gap=10s merge) | 78.9% | 35.4% | 48.7% |
| v4 (app-identity filter) | 75.0% | 25.9% | 38.3% |

Total predicted boundaries dropped sharply (52,313 -> 8,598, a 6x cut),
confirming the filter is aggressively removing candidates. But precision
*also* dropped instead of improving, which is unexpected for a filter that's
supposedly only removing noise. This suggests the "keep first event in a
same-identity streak" rule discards genuinely useful predictions along with
the noise, and mixing two different identity types (app names for
app_switch, URLs for browser_navigation) may cause unintended behavior at
the boundary between event types.

**Decision:** v2 remains the best validated detector so far. Both v3 (time-
based merge) and v4 (identity-based filter) were tested rigorously and
rejected based on full-dataset evidence, not single-session results.

## Day 2 (final): decision to stop filter refinement

**Comparison table (all 63 sessions, Dataset A):**

| Detector | Recall | Precision | F1 |
|---|---|---|---|
| v2 (app_switch + browser_navigation, no filter) | 85.1% | 36.6% | **50.8%** |
| v3 (min_gap=10s time-based merge) | 78.9% | 35.4% | 48.7% |
| v4 (app-identity filter) | 75.0% | 25.9% | 38.3% |

**Why v4 failed — the core diagnosis:**
The filter assumed "same app name = same task, no boundary" and "different
app name = task changed, keep boundary." This assumption doesn't hold:
same-app-name is not the same thing as same-task. A single business process
can span multiple app switches internally (e.g. checking Excel, then
Chrome, then back to Excel, all within one task), and conversely, two
different processes can occur back-to-back within the exact same app with
no app-switch event marking the transition at all. App identity and task
identity are two different granularities that don't map cleanly onto each
other, so filtering purely on identity-change discards real signal along
with noise, and fails to add signal where the app never changes between
tasks.

**Decision:** Stopping boundary-filtering refinement after two systematic
rejections (v3, v4), each tested across the full 63-session dataset rather
than assumed from a single case. Adopting v2 (recall 85.1%, precision
36.6%, F1 50.8%) as the final detector. Further precision gains would
require a fundamentally different signal (e.g. content-based task
identification, not just activity-timing heuristics) rather than another
filter on the same event types - out of scope for this phase. Proceeding
to segment construction and labeling using v2's boundaries.