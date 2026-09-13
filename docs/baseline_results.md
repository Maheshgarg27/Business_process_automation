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

## Update: added browser_navigation signal

**Method:** `detect_boundaries_v2()` — same as v1, but also treats
`browser_navigation` events as candidate boundaries.

### Session tested
- Session: `ses_20260630-124826-CHAITANYA0BCF` (dataset_a)
  *(different session from the v1 baseline test above, because this one has
  gt_manifest.json, and this session actually contains browser_navigation
  events — the v1 test session had none, since its browser extension
  wasn't capturing navigation for that recording)*
- Events loaded: 3163
- v1 (app_switch only): 1044 boundaries -> 73.5%
- v2 (+ browser_navigation): 1078 boundaries -> 88.2%

## Interpretation
Adding browser_navigation as a second signal closed a large part of the gap
left by app_switch alone — confirming that many task boundaries happen
*within* the same app (e.g. navigating between pages on a portal) rather
than only when switching apps entirely.