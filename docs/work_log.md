# Work Log

## About this log

### The seven days in short

| Day | Time (approx.) | What I did |
|---|---|---|
| 1 | 4-5 hours | Studied the structure of Dataset A and B and what the logs can tell us |
| 2 | 6-7 hours | Built the boundary detector and an evaluation metric; tested two filters and rejected both |
| 3 | 5-6 hours | Labeled segments by process, merged them, ran the full pipeline on Dataset B, spot-checked the result |
| 4 | 4-5 hours | Checked for API evidence, fixed a label inconsistency between Step 1 and Step 2, built a first prototype |
| 5 | 3-4 hours | Investigated OCR as a labeling signal and rejected it |
| 6 | 2-3 hours | Ranked the processes and chose payroll as the automation target (midsem exam day) |
| 7 | 6-7 hours | Built and tested the payroll automation tool with a control panel, wrote the process manual, recorded a demo video |

In total this is about 30-37 hours. I did not track my time while working. These are estimates that I reconstructed on the last day from memory and from my laptop's battery report.

### How I worked

I worked on the project every day. The midsem exam affected only Day 6. On the other days I did the project work first and studied afterwards. In Step 1 I tried to test every idea on the data before I kept or dropped it, and four ideas were dropped that way (see Days 2, 3 and 5). For Step 3 I first had to decide what kind of tool would make sense for a real company, and I changed direction once (see Day 7).

### How I used AI

I used AI assistants during the project, which the task allows. In short:

- **What the AI did:** it helped me write code  and it helped me write parts of this log.
- **What I did:** I decided what to test and what counted as a good enough result, I chose which ideas to keep or reject based on the numbers, I chose payroll as the target, and I defined what the Step 3 tool must do. I ran the code on my laptop, looked at the results, and found problems by running things.
- **Suggestions:** the AI suggested several options,but i didn't follow them blindly i used just them to understand and then i add my suggestion , my ideas and then I proceed I explored amny things and choose the best one.


### How this log was kept

I wrote the entries during the week .I forgot to commit the entries of Day 5, so they were committed late. On the last day (Day 7) I went through the log once more and added this "About this log" section, the time per day, the Day 7 description and the closing note. I did not change the technical content, numbers or decisions of the earlier entries.

---

## Day 1 — Dataset Understanding and Exploration

**Time:** about 4-5 hours.

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

**Time:** about 6-7 hours.

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

**Time:** about 5-6 hours.

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

**Time:** about 4-5 hours.

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

**Time:** about 3-4 hours.

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

**Time:** about 2-3 hours.

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

## Day 7 - Step 3 tool: build, test and wrap-up

**Time:** about 6-7 hours.

### Goal for the day
Finish the Step 3 automation tool and make it demonstrable end to end: one input spreadsheet in, a decision and reason for every row out, with the supporting evidence (mails, documents, system updates) visible afterwards.


### The two folders, and how Day 7 went, in order
There are two tool folders in the repository. They are two different attempts:

- **`prototype/`** is my first attempt. On Day 4 I built the onboarding automation there (a Playwright script against a mock portal). After I chose payroll as the target, I tried to automate the payroll process in the same way, with mock portals and scripts that drive the screens and Excel (`mock_payroll_portal*.html`, `automate_payroll*.py`, `payroll_tool_app.py`). I dropped this approach. I kept the folder because it shows how my idea developed.
- **`Payroll_automation/`** is the final Step 3 tool. It is a new approach that I started with the help of an AI assistant. Everything below, except the first point, is about this folder.

1. **Dropping the first approach.** The scripts in `prototype/` depended on screens and windows, and I had already noted on Day 4 that this kind of automation is fragile. A real company would not work like that. They would hand over a spreadsheet and expect the tool to work in the background, reading mails, documents and system records through APIs and connectors, and writing the result back. So I decided to start again with a tool that runs without opening any application, with the systems behind connectors.
2. **Sample data from the logs.** In the prototype phase I extracted a sample sheet of real payroll cases from the recorded logs (`prototype/extract_real_payroll_cases.py`, 145 rows across the seven sub-processes). It only holds a few values per case, so the tool needs the surrounding records and documents to decide anything. I used the same columns as the input format of the new tool.
3. **The pipeline without a user interface.** I first built it as a command-line pipeline: read the sheet, check each row, write the decision back into the same sheet. I insisted that the dummy data should behave like a real company and not like a toy: about 50 cases per process, with rules that go beyond checking that a document is attached, for example experience for onboarding, tolerances for invoices, limits per category for expenses.
4. **Real documents.** I pointed out that many decisions depend on documents that a person would open (receipts, contracts, proofs, price lists). The generator now creates real PDF, Word and Excel files, and the tool opens and reads them.
5. **Approval loop and payroll export.** Cases that only need a person's approval are sent to the approver, and finished on the next run when the reply arrives. Approved expenses and leave go to a payroll export.
6. **A mailbox view.** I wanted to see what an employee or candidate sent and what the tool replied, as in a real mailbox. It became a mailbox page, later in Japanese and English.
7. **The control panel.** Until now I started everything from the terminal. I asked for one command that opens a page with a heading, a Start button and the live log, that shows the dashboard first when the run is finished, and that offers the result spreadsheet and the mailbox after that. Then I added an input preview, a file picker for choosing a spreadsheet from the computer, and a fix for the table header in the spreadsheet view.
8. **Wrap-up.** I tested the whole loop several times, wrote a process manual that explains the pipeline, and recorded a demo video.
### What I built
A payroll back-office automation platform that processes seven kinds of cases from one sheet: onboarding, invoice approval, leave request, expense reimbursement, inventory adjustment, budget variance and order management.

**How one run works**

1. The tool backs up the workbook and checks that every system API answers.
2. Each row is routed by `category_type` to its process engine.
3. The engine looks up the records it needs through REST APIs (mail server, HR system, ERP, procurement, warehouse system, shared drive). It opens the supporting documents (Word, PDF, Excel), reads the values inside them, and compares three sources: the sheet, the system record and the document.
4. Configured rules (thresholds, tolerances, document lists) produce a decision: `APPROVED`, `REJECTED` or `NEEDS_REVIEW` (`ERROR` only for technical failures).
5. The engine performs the follow-up actions: reply mail, leave deducted, purchase order created, stock movement posted, decision booked.
6. The decision and reason are written back into the same workbook in new columns. The original columns are never changed. Every decision is also appended to an audit log, and a short decision memo is stored on the shared drive.

**Approval loop.** When a case only waits for a person's approval (for example a manager approval on an expense), the tool mails the approver and remembers the case. On the next run it reads the approver's reply and finishes the case. It sends a reminder after 3 days and an escalation after 5.

**Outputs.** The updated spreadsheet, a results dashboard, a mailbox view (candidate mails and the tool's replies, in Japanese or English), and a payroll adjustment export of approved reimbursements and leave deductions.

**Control panel.** `python app.py` builds fresh dummy data, then opens a page where I choose a spreadsheet (from the generated one or from my computer), press Start, watch the live log and progress, and then view the dashboard, the spreadsheet and the mailbox.

### The dummy data
The client systems are not available, so I built a simulated company.

- I wrote a generator that creates about 350 cases (50 per process), shuffled together, using the same columns as the sample sheet.
- For every case it also creates the surrounding world: employees and leave balances, application mails with Word attachments, invoices, purchase orders and goods receipts, expense claims, stock levels, quotations and blanket contracts, and about 225 real documents (PDF, Word, Excel) on a simulated shared drive.
- Each process has a planned mix of clean cases, borderline cases and clearly failing cases, so every rule is triggered by at least one row.
- The generator uses a seed. The same seed gives the same data again, which makes tests repeatable. The app picks a new seed each time unless I pass one.
- The generator also writes the result a correct run should produce for each row.

### How I checked it
I compare each run with the expected results the generator wrote. On the default seed the first run matched 350 of 350 rows, and after the simulated approver replies the resumed cases also matched 350 of 350. A second run does nothing and makes no extra mails or postings. A malformed row is marked `ERROR` and the batch continues.

This check has a limit. The expected results and the data come from the same generator, so it proves that the rules behave as I designed them, not that the rules match real company policy.

### What went wrong and how I fixed it
- **Excel file lock.** A run processed all rows and then failed when saving because the workbook was open in Excel. I made the tool check that the file is writable before starting, and save a fallback copy if the file becomes locked during the run.
- **Duplicate mails after a failed run.** A half-finished run leaves side effects behind, so I regenerate the data for a clean start. Server-side idempotency (one action per case) prevents double mails or double deductions on a normal re-run.
- **Spreadsheet view.** In the browser view the rows scrolled above the table header. I put the table in its own scroll area with a sticky header.
- **Git.** I first created a feature branch by mistake and then went back to committing on `main`, so the history stays in one line.

### Decisions and trade-offs
- **Rules in a config file, not in code**, so a policy change does not need a code change.
- **Kept `NEEDS_REVIEW`.** I considered reducing everything to approved or rejected. I kept the third state because a tool that cannot verify something should hand it to a person, not guess. I also discussed making approval a switch and decided against it.
- **English mailbox with a phrase table instead of a translation service.** All sentences come from fixed templates, so a table is enough, works offline and needs no key. Names are romanised with a small dictionary. Unknown text stays unchanged.
- **Simulated systems behind real API calls.** The tool only talks to one API client. Replacing a system means changing an address, credentials and endpoint mappings.

### How I used AI on this tool
- **What I decided and asked for:** the direction (a background tool that reaches systems through APIs, not visible windows), realistic rules and about 50 dummy cases per process, that the tool must open and read the documents, that the input columns stay untouched and results go into new columns, keeping `NEEDS_REVIEW`, the control panel with a Start button and live log, the dashboard first, the Japanese and English mailbox, the input preview and the file picker.
- **What the AI did:** it proposed the architecture (connector layer, rules in a configuration file, approval loop, audit log) and wrote most of the code and the test scripts.
- **What I did myself:** I ran the tool on my laptop, found the Excel lock problem and the layout problem in the spreadsheet view, reviewed the dashboard, spreadsheet and mailbox, and pushed back when something was not what I wanted.

### Next
- Read through each module again so I can explain every rule.
- Finish the final report: risks (identity mapping, document formats, policy ownership), what manual work remains, and the rollout plan (shadow mode first).

After that I recorded a demo video of the tool: the control panel, the live run, the dashboard, the result spreadsheet, the mailbox and the approval loop.

### Closing note
It was a good journey and I enjoyed working on it. I started with raw event logs that said nothing about the work, and I ended with a working tool built on the process I found in them. I learned to test an idea before trusting it, to drop what the data did not support, and to be clear about what a prototype shows and what it does not.

