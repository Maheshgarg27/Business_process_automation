# Baseline: app_switch-only boundary detection

**Method:** `detect_boundaries()` treats every `app_switch` event as a candidate
task boundary. No idle-gap detection, no browser navigation signals.

**Evaluated with:** `evaluate()` (3-second tolerance) against `gt_manifest.json`
ground truth.

## Session tested
- Session: `ses_20260630-121953-LAPTOP-R36BQBTE` (dataset_a)
- Events loaded: 2348
- Predicted boundaries (app_switch count): 671
- **Score: 53.1%**

## Interpretation
Roughly half of true task boundaries coincide with an app switch. The other
half happen without one (e.g. two tasks in the same app back-to-back, or a
task spanning multiple apps mid-task). This is the number every future
improvement must beat.