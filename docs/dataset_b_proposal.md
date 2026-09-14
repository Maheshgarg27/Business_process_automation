# Step 2: Automation Priority Proposal

Analysis of Dataset B (15 sessions, 1196 segments) identified 5 distinct
business processes plus a low-value "dashboard" catch-all. Ranked below
by combined impact and feasibility.

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