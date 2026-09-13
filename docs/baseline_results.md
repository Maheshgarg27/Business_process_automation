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

## Final: full dataset (all 63 sessions)

Ran both detectors across every session in Dataset A and averaged the score.

| Detector | Average score across 63 sessions |
|---|---|
| v1 (app_switch only) | 64.6% |
| v2 (+ browser_navigation) | **85.1%** |

Sessions failed: 0 (both versions)

## Interpretation
The single-session tests (53%, 73.5% -> 88.2%) were in the right ballpark but
not fully representative — per-session scores vary quite a bit (individual
sessions ranged from ~31% up to ~96%). The 63-session average is the number
that should actually go in a report, since it's not vulnerable to picking a
lucky or unlucky single session.


## Important finding: recall alone was misleading

Total real process-executions across all 63 sessions: **2009**
Total boundaries predicted by v2: **52,313** (26x more than real)

This meant the 85.1% "recall" number, while technically correct, was
achievable partly just by over-predicting. Added precision and F1:

| Detector | Recall | Precision | F1 |
|---|---|---|---|
| v1 (app_switch only) | 64.6% | 35.2% | 45.3% |
| v2 (+browser_navigation) | 85.1% | 36.6% | **50.8%** |

v2 is still genuinely better (F1 improved), but the gain in recall mostly
came from predicting more candidates overall, not from being more precise.
Precision (~35%) is the real bottleneck going forward — future improvements
should focus on cutting noisy/spurious predicted boundaries, not just
adding more signals.