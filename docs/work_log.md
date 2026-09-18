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

**Why v3 failed — the core diagnosis:**
The time-gap merge filter assumed "boundaries occurring close together in
time are noise, not real transitions." This assumption doesn't hold in
general: real task transitions can genuinely happen fast (some real
executions were as short as ~16.6s), so a blanket time threshold collapses
genuine closely-spaced transitions along with true noise. Swept 9
thresholds (1s-20s) across all 63 sessions - none beat v2 on the combined
recall/precision tradeoff, ruling out the entire time-based approach rather
than just one bad threshold guess.

**Decision:** Stopping boundary-filtering refinement after two systematic
rejections (v3, v4), each tested across the full 63-session dataset rather
than assumed from a single case. Adopting v2 (recall 85.1%, precision
36.6%, F1 50.8%) as the final detector. Further precision gains would
require a fundamentally different signal (e.g. content-based task
identification, not just activity-timing heuristics) rather than another
filter on the same event types - out of scope for this phase. Proceeding
to segment construction and labeling using v2's boundaries.

**Why precision of 36.6% is acceptable for this use case:**
The next phase (segment construction and labeling) aggregates raw
boundaries into labeled segments. In that context, the two error types are
not equally costly. Over-segmentation (a false-positive boundary splitting
one real task into two segments) is relatively cheap - the resulting
segments likely still carry the same or adjacent label and can be merged
during aggregation. Under-segmentation (a missed real boundary, merging two
different tasks into one) is more costly, since it corrupts the label of
the entire merged segment with no clean way to recover the split
afterward. Given this asymmetry, prioritizing recall (85.1%) over precision
(36.6%) is the right tradeoff for this pipeline, even though 36.6%
precision looks weak in isolation.


## Day 3: Labeling segments by business process

**Goal:** Once boundaries were detected (Day 2), the next problem was
assigning each resulting segment a consistent label - the same underlying
business process should get the same label every time it recurs.

**First approach:** Built a lightweight "fingerprint" per segment based on
which application was active and, for browser activity, which domain was
visited. Segments with matching fingerprints were grouped under the same
label - no ML clustering, just exact-match grouping to start simple.

**Initial validation:** Tested this against Dataset A's ground truth by
matching each labeled segment to whichever real process-execution overlaps
it in time, then measuring "purity" - what fraction of segments under a
given label actually belong to the same real process. Result: only 28.6%
purity on the first session tested.

**Diagnosis:** Looking at the breakdown, one label was mixing 9 different
real process codes together. The cause: this internal portal hosts several
different business processes on the exact same domain, distinguished only
by the URL path (e.g. a specific route like a resident-tax page vs a
social-insurance page). Fingerprinting on domain alone couldn't
distinguish them.

**Fix:** Changed the fingerprint to use the full URL path instead of just
the domain. Retested on the same session: purity rose to 48.5%. Ran across
all 63 sessions in Dataset A to get a trustworthy number rather than
trusting one session: **average purity 46.8%** (range 26.0%-62.0%,
0 failures).

**Further diagnosis:** 46.8% is a real improvement but still leaves a lot
of mislabeling. Investigated why: generic applications (notably a plain
text editor used as a scratchpad) get reused across many unrelated
processes, so app/URL identity alone carries no signal there - there's
nothing to fingerprint against.

**Tried one incremental fix:** Added on-screen text snippets (available on
a minority of events) into the fingerprint, hoping screen content could
distinguish segments that share the same app/URL. Tested across all 63
sessions: purity was unchanged (46.8% -> 46.8%). Rejected - this signal
is present on too small a fraction of events to move the result, and
occasional additions fragment labels about as often as they help
distinguish them.

**Considered but deferred:** Running OCR directly on screenshots to get
broader text coverage than the sparse on-screen-text field already
provided. Not pursued: screenshots themselves are only captured at
specific moments (not continuously), the source text is in Japanese which
adds real setup complexity, and the prior text experiment already showed
that even where text is available, simple exact-match fingerprinting
doesn't help - so the bottleneck appears to be the matching approach, not
the amount of available text. Given the overall 7-day budget for the full
project, this was judged not worth the investment right now.

**Decision:** Adopting the URL-path-based fingerprint labeling as final
(46.8% average purity across Dataset A). Next step is to merge consecutive
segments that share the same label into single, coherent units of work -
this both cleans up the heavy over-segmentation from Day 2's boundary
detector and produces a sensible final output - then apply the complete
pipeline to Dataset B to produce the required segments.jsonl.

## Merging and applying the pipeline to Dataset B

**Merge step:** Implemented `merge_same_label_segments()` - collapses
consecutive segments sharing the same label into one continuous segment.
Tested on the same Dataset A session used throughout: raw segment count
dropped from 1079 to 109, with segment durations now falling in a
realistic 20-45 second range instead of millisecond fragments. This
confirmed the merge step successfully "heals" the heavy over-segmentation
inherited from boundary detection (Day 2's known 36.6% precision).

**Full pipeline on Dataset B:** Combined the complete pipeline - detect
boundaries -> construct segments -> label -> merge - and ran it across
all 15 sessions in Dataset B (the production dataset with no ground
truth). All 15 sessions processed successfully, 0 failures. Per-session
segment counts ranged from 40 to 134, totaling **1196 segments** across
the dataset. Output written to `outputs/segments.jsonl` in the required
format (session_id, start, end, label - one JSON object per line).
Per-session counts also saved separately to
`outputs/segment_counts_per_session.json` for reference.

## Spot-check on Dataset B segments.jsonl

Manually inspected 8 random segments, pulling and translating real
extracted_text content.

Found a clear, concrete example of the known Word/Notepad limitation:
two segments both labeled simply "Microsoft Word" contained completely
different business content when translated - one a contract termination
procedure ("契約解除手続き"), the other a family allowance regulation
("家族手当規程"). Since desktop apps have no URL to fingerprint against,
the current labeling approach cannot distinguish different documents
opened in the same application.

Also found one path-based label ("payroll-items") whose actual content
was inventory adjustment, not payroll - suggesting the portal's URL
routes are not always a fully reliable proxy for business content.

These findings are consistent with Dataset A's purity ceiling (46.8%)
and confirm the same limitation applies to Dataset B, where no ground
truth exists to measure it numerically.

## Analyzing segments.jsonl output

Loaded and inspected the Dataset B segments.jsonl output for sanity:
shape (1196, 5), 15 unique sessions, 177 unique labels - matches expected
totals from the pipeline run.

Aggregated per-label statistics (frequency, total time, avg duration,
number of sessions touching each label). Top finding by total time:
"Microsoft Word" (generic, no URL) - 268 occurrences, ~26.7 minutes total,
present in all 15 sessions.

**Key observation:** significant label fragmentation. The same real
business process (e.g. "payroll-items") appears under multiple different
labels depending on which secondary app happened to be open alongside the
browser (e.g. "Edge|payroll-items" vs "Edge+Word|payroll-items" vs
"Edge+Notepad|payroll-items") - these are very likely the same underlying
process, split apart by incidental co-occurring apps. This means the raw
177-label count overstates the true number of distinct business processes;
before finalizing automation-priority analysis, related labels sharing the
same URL path need to be grouped together regardless of secondary app.

Saved full breakdown to outputs/label_analysis_summary.csv.

## Testing label consolidation 

Hypothesis (from review): raw labels were over-fragmented by two things
assumed to be noise - (a) port number (5122/5123/5124) and (b) incidental
app-combinations (whether Word/Notepad/Excel happened to be open
alongside the browser).

Built and ran a test comparing three variants across all 63 Dataset A
sessions:
- Raw label (baseline): 46.8% purity
- Drop app-combo only, keep port: 45.9% purity (no meaningful change)
- Drop BOTH port and app-combo: 38.3% purity (a real drop)

**Finding: the port-number part of the hypothesis was wrong.** Checking
the earlier per-label ground-truth breakdown, the same URL path on
different ports maps to different real process codes (e.g.
.../5123/#/resident-tax and .../5122/#/resident-tax have substantially
different ground-truth code distributions) - so port carries real signal,
not noise.

**Decision:** adopted the corrected, evidence-based version - drop only
the incidental app-combination prefix (negligible effect on purity,
45.9% vs 46.8%) but keep the port number in the label. Rejected dropping
port, since it measurably hurt accuracy. This corrected label will be
used to re-aggregate the Dataset B process-frequency analysis for Step 2.


## Day 4 : checked for API evidence before choosing implementation approach

Before committing to UI-automation, checked DOM attributes on onboarding
events for signs of a callable API (action/method attributes). Found
none across 367 events - inconclusive given this is a JS SPA, but
informed the decision to build UI-level automation rather than assume
an API. See dataset_b_proposal.md for the full reasoning. Saved raw
check results to outputs/api_evidence_check.json.

## Day 4 (continued): Step 1/Step 2 consistency fix

Discovered `segments.jsonl` (the actual deliverable) still used the raw,
fragmented fingerprint labels (app-combo + full path) from before the
Step 2 label-cleanup logic was built — meaning the same real process
(e.g. onboarding) could appear under several different labels depending
on which app happened to be focused at that moment. Fixed by applying
the cleaned `extract_process_label` logic directly into segment
generation, dropping app-combo noise while keeping the URL route (and
port, validated via purity check as carrying real signal). Regenerated
and overwrote `outputs/segments.jsonl` with corrected, consistent
labels. Verified: same route now always produces the same label
regardless of concurrent app usage.

Also revisited `dataset_b_proposal.md` to fix related issues found
during review:
- Corrected stale segment/occurrence counts after the relabeling
- Removed a duplicate headcount-proxy paragraph
- Expanded the headcount-proxy limitation to explicitly cover both
  over- and under-counting risk (session count as a proxy for people
  involved, since Dataset B has no operator field)
- Disclosed that ~50% of segments (generic desktop apps like
  Notepad/Word with no URL) are excluded from the process-priority
  ranking, since they can't be reliably attributed to a specific
  business route

## Day 4 (continued): Step 3 prototype build

Built the working automation prototype for the `onboarding` process
(selected in Step 2 as the safer first build vs. higher-impact but
riskier `payroll-items`):

- `prototype/mock_onboarding_portal.html` — local replica of the real
  portal's structure (same element IDs found in real logs: `#ob-note`,
  `#btn-ob-ok`)
- `prototype/automate_onboarding.py` — Playwright script automating the
  repetitive loop found in real segments (click row -> read data ->
  paste note -> submit), looped across cases

Added risk mitigations directly into the prototype rather than
polishing UI (per README: polish isn't evaluated, judgment is):
- Dry-run mode — previews actions without submitting, so a real
  deployment doesn't blind-submit HR record changes
- Logging with masked employee identifiers (SHA-256 truncated hash) —
  auditable trail without exposing PII in logs
- Basic edge-case handling (e.g. missing note field) instead of
  crashing
- Documented current prototype limitations (UI fragility, headless
  mode, note template) in the work log/report rather than hiding them

## Day 5: OCR investigation (screen content as a labeling signal)

Explored whether OCR on screenshots could improve label purity for the
~50% of segments with no URL signal (generic apps), and separately give
better insight into what onboarding actually involves.

**Setup and validation**
- Legibility gut-check on 5 real screenshots: passed. Tesseract (jpn)
  correctly extracted document titles, company names, transaction
  types and dates
- Built an OCR-augmented fingerprint + purity test script. Fingerprint
  is `(apps, paths, ocr_snippet)`, with `ocr_snippet` computed only when
  `paths` is empty. OCR text is fed into the grouping itself, not just
  extracted as metadata

**Dataset A testing**
- First 10-session run compared against the wrong baseline (63-session
  global 46.8% vs a 10-session subset). Caught this and re-ran
  apples-to-apples
- Fixed 10-session test: purity 39.9% -> 41.5% (+1.6, same sessions,
  same segments)
- Full 63-session run: 45.9% -> 47.1% (+1.3), zero sessions regressed.
  This is mathematically expected, since OCR only refines existing
  groups and never merges them
- Diagnosed the zero-delta sessions with `check_screenshot_coverage.py`:
  only 14.8% of Dataset A's referenced screenshots exist on disk
- Spot-checked 50 empty-text cache entries: 50/50 were `missing_file`,
  0 `genuinely_empty`, 0 `tesseract_error`. The modest gain is a
  missing-file constraint, not an OCR quality issue

**Dataset B testing**
- Checked Dataset B coverage: 100% (4746/4746), so no missing-file
  constraint. This is the method's real ceiling
- Ran `apply_ocr_labels_dataset_b.py` on the 1016-segment deliverable,
  writing to a new file (original left untouched)
- **Result: label count exploded from 79 -> 423.** Diagnosed cause: raw
  OCR text is instance-specific (dates, amounts, names differ per
  document even for the same process type), so exact-match fingerprinting
  fragments repeated executions of the same process into near-unique
  labels instead of grouping them
- Recognized this as a metric-validity flaw, not just a weak result:
  purity trivially favors smaller clusters, so the purity increase on
  Dataset A didn't actually confirm correct grouping. It can reward
  over-fragmentation the same way recall-without-precision did in Day 2

**Decision: rejected.** OCR-augmented labeling not adopted for the
final deliverable. `outputs/segments.jsonl` (URL/route-based +
clean generic-app tags) remains the submitted file.
`outputs/segments_with_ocr.jsonl` kept in the repo for transparency
only, explicitly marked as a rejected experiment, not the deliverable.

This is the fourth tested-and-rejected Step 1 refinement (after v3
time-merge, v4 identity-filter, and the earlier `extracted_text`
signal test), alongside the one that did work (v2 boundary detection +
route-based labeling).

I forgot to commit my worklog on day 5,6

## Day 6: Process prioritization and automation target selection

Reduced-capacity day, since midsem exams overlapped with the project. Spent
the working time on prioritizing which processes to automate and starting
to think about how the pipeline could become a usable tool rather than
just an analysis.

**Prioritization**
- Ranked the candidate processes by impact (total time, occurrences,
  session reach) and weighed each against feasibility risk (application
  spread, duration variability)
- Ranking: 1) payroll-items (48.7 min, 143 occurrences, 14/15 sessions),
  2) leave-applications (26.0 min, 120 occurrences), 3) onboarding
  (21.4 min, 96 occurrences, lowest variability at std ~6.4s),
  4) social-insurance (16.8 min), 5) resident-tax (11.0 min)
- Excluded "dashboard": only 1.8 min total, and it looks like
  navigation/orientation rather than a real task
- payroll-items has roughly double the impact of the next process and
  touches nearly every worker, but it is also the most complex (10
  distinct applications). The recommendation was to scope it carefully
  rather than attempt full end-to-end automation right away
- onboarding remains the lowest-risk, most predictable candidate and a
  good proof-of-concept option

**Decision**
- Chose payroll as the automation target. It breaks down into 7
  sub-processes: `budget_variance`, `expense_reimbursement`,
  `inventory_adjustment`, `invoice_approval`, `leave_request`,
  `onboarding_match`, `order_management`
- Started thinking through how the pipeline (segmentation, labeling,
  prioritization) could be packaged as a tool, and which of these
  sub-processes are the best candidates to automate first

Made limited progress beyond this because the rest of the day went to
exam preparation. Next step is to scope the 7 sub-processes and pick the
first one to build (Step 3).