# Step 2: Automation Priority Proposal

Analysis of Dataset B (15 sessions, 1196 segments) identified 5 distinct
business processes plus a low-value "dashboard" catch-all. Ranked below
by combined impact and feasibility.


## Note on methodology and limitations

**Headcount proxy:** Dataset B has no explicit operator/department field
(unlike Dataset A's gt.jsonl). `num_sessions` is used as the best available
proxy for "how many people are involved," under the assumption each
session corresponds to one worker/machine. This likely undercounts true
headcount if the same person appears across multiple sessions, and is
stated here as an explicit limitation rather than an implicit assumption.

**Handling pattern variation:** The complexity signals gathered (distinct
apps involved, duration variability) directly answer the "are there
different handling patterns within the same process?" question. For
example, payroll-items shows the widest app variety (10 distinct apps)
of any process, suggesting inconsistent handling paths across cases or
operators - itself a risk factor to weigh before automating, since a
process with many valid paths is harder to automate reliably than one
with few.

## Priority 1: payroll-items
- Impact: highest by far - 48.7 min total, 218 occurrences, 14/15 sessions
- Feasibility risk: touches the most distinct applications (10) of any
  process, suggesting the most branching/complex workflow
- Reasoning: Despite being the most complex candidate, its impact is
  roughly double the next-highest process and touches nearly every
  worker - the ROI ceiling is too large to ignore. Recommend as the
  primary automation target, but scoped carefully (see Step 3) rather
  than attempting full end-to-end automation immediately.

## Priority 2: leave-applications
- Impact: 26.0 min total, 143 occurrences, 13/15 sessions
- Feasibility risk: highest duration variability of all processes
  (std ~15.3s), suggesting inconsistent paths per case
- Reasoning: High frequency and reach, but the variability suggests
  cases branch significantly - would need deeper investigation into
  what drives that variance before committing engineering effort.

## Priority 3: onboarding
- Impact: 21.4 min total, 137 occurrences, but narrower reach (9/15
  sessions)
- Feasibility: lowest duration variability (std ~6.4s) - the most
  consistent, predictable process observed
- Reasoning: Lower total impact than payroll-items or leave-applications,
  but its consistency makes it the lowest-risk, fastest-to-build
  candidate. Strong option as a first proof-of-concept before tackling
  payroll-items.

## Priority 4: social-insurance
- Impact: 16.8 min total, 76 occurrences, 8/15 sessions
- Reasoning: Meaningful but secondary - lower volume than the above three.

## Priority 5: resident-tax
- Impact: 11.0 min total, 41 occurrences, 8/15 sessions
- Reasoning: Lowest volume of the real business processes - worth
  automating eventually, but not a near-term priority.

## Excluded: "dashboard"
- Only 1.8 min total time, appears to be brief navigation/orientation
  activity rather than a substantive task - not a meaningful automation
  target.

## Overall recommendation
**payroll-items** is the highest-ROI target by volume, but **onboarding**
is the safer, faster first build given its consistency. A reasonable
strategy: build a proof-of-concept on onboarding first to validate the
approach, then apply lessons learned to the higher-impact but
higher-complexity payroll-items process.


## Step 3 scoping: feasibility assessment for "onboarding" (before building)

**Data access:** onboarding activity happens through a locally-hosted web
portal (127.0.0.1:5132/5133 - i.e. an internal system accessed via
browser, not a public/cloud API). We only observe this through UI-level
events (clicks, navigation, app switches) - we do NOT have confirmed API
access to the underlying onboarding system. This means automation
options are most realistically either (a) UI-automation/RPA against the
existing portal, or (b) a real backend API integration IF the client's
engineering team confirms one exists. Given only log-level visibility, we
cannot assume an API exists - this must be confirmed with the client
before committing to an integration approach, and the prototype should be
built assuming UI-level automation as the safer default.

**Business logic complexity:** onboarding shows the lowest duration
variability of the analyzed processes (std ~6.4s), and touches a moderate
number of apps (7, vs payroll-items' 10) - both signals suggest a
relatively standardized, low-branching workflow compared to the
alternatives. However, Word, Notepad, Windows Explorer, and occasionally
a terminal all appear alongside the portal during onboarding segments,
meaning the process is not purely form-filling - it likely also involves
document handling and file lookups, which adds real (if modest) branching
that a naive "fill this web form" automation would miss.

**Operational/governance constraints (anticipated, not confirmed):**
Onboarding activity likely touches new-employee personal data (a
sensitive category), so any automation here probably needs: audit
logging of automated actions, a human-in-the-loop approval step before
final submission (rather than fully autonomous submission), and
alignment with the client's existing data-handling policy for HR
records - none of which we can verify from logs alone, but are reasonable
risks to flag given the domain.

**Anticipated implementation risks:**
- The portal's UI could change without notice, breaking any UI-automation
  approach silently - this is a known fragility of RPA-style solutions
  and should be flagged as an ongoing maintenance cost, not a one-time
  build cost.
- Since 9/15 sessions touch onboarding (not all 15), the process may not
  be universally standardized across departments/roles - the prototype's
  scope should be validated against a broader sample before wider
  rollout, since our current view is based on log data only, with no
  confirmation of full organizational coverage.
- We cannot see what happens inside the Word/Notepad/File Explorer steps
  from event logs alone (no screen content in most segments) - meaning
  parts of this workflow may currently be invisible to us, and a
  prototype might need a discovery/interview phase with actual onboarding
  staff to fill gaps the logs cannot show.

**Decision:** Proceeding with "onboarding" as the Step 3 prototype target,
scoped to the browser-portal-visible portion of the workflow (not the
Word/Notepad file-handling steps, which need further discovery). This is
a deliberately narrower scope than "fully automate onboarding end-to-end,"
chosen because a working, honestly-scoped prototype is more valuable than
an ambitious one that breaks on the parts we can't currently see.


## Step 3: Prototype built and verified

Built and successfully ran a working automation prototype for the
"verify case -> write note -> submit" loop identified within onboarding
segments (see Data Access section above for why UI-automation was chosen
over an assumed API integration).

**What it does:** Using Playwright (browser automation), the script
identifies each pending case in the case list, clicks it, fills in a
verification note, and submits - replicating the exact manual sequence
observed in the real event logs (click row -> read data -> paste note ->
submit), repeated for every case.

**How it was tested:** Since the real portal only exists on the recording
machine (127.0.0.1) with no confirmed external access, the prototype was
validated against a local mock page replicating the real system's exact
DOM structure (same element IDs: #ob-note textarea, #btn-ob-ok button,
sourced directly from the real onboarding event logs). Ran successfully:
all 4 test cases processed automatically and correctly in sequence.

**What would change for real deployment:** Only the target URL and the
case-data source would need to change (e.g. reading from the real
portal's rendered table, or an API if the client confirms one exists) -
the interaction logic itself is already proven to work.


## Step 3: Dry-run safeguard added (governance risk mitigation)

Added a DRY_RUN mode to the prototype - when enabled (the default), the
script clicks through each case and fills in the note text exactly as it
would live, but stops short of clicking the final submit button, printing
a preview of what it *would* do instead. This directly implements the
human-in-the-loop safeguard anticipated in the governance risk section
above: HR/employee data should not be blind-submitted by an automated
process without a human reviewing the intended changes first.

Verified both modes work correctly: DRY_RUN=True previewed all 4 cases
with zero actual submissions; DRY_RUN=False then executed the same 4
cases live, submitting each one successfully. In a real deployment, the
recommended workflow would be: run in dry-run mode, have a human review
the generated notes/actions, then re-run in live mode only after approval
- rather than defaulting to full autonomous execution.