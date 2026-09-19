# Final Report

**Task:** From operation logs to an automation proposal (Steps 1 to 3)

## 1. Summary

The client wants to know where automation would have the greatest impact, and wants to see something that works. The logs only record operations, so I first had to recover the business work from them.

- **Step 1.** I recovered units of work from the raw event streams. On Dataset A (with ground truth) my final boundary detector reaches recall 85.1%, precision 36.6% and F1 50.8%, and my labeling reaches an average purity of about 46 to 47%. These numbers are modest, and I explain why I accepted them. I applied the pipeline to Dataset B and produced `segments.jsonl` (1,016 segments, 79 labels).
- **Step 2.** In Dataset B the payroll portal route (`payroll-items`) is the largest block of work: 48.7 minutes, 143 occurrences, 14 of 15 sessions, about twice the next process. Leave applications, onboarding, social insurance and resident tax follow. Section 4 gives the full priority order with reasons.
- **Step 3.** I first chose onboarding as the safest process and built a small **UI automation** prototype for it. I then dropped it for two reasons: the return was small, and onboarding turned out to be one of the seven kinds of case that flow through the payroll route. I built a **payroll back-office automation tool** instead. It works **entirely through system APIs and connectors, with no UI automation.** It reads one spreadsheet of cases, checks each case against the systems and documents, executes the follow-up actions, and returns the spreadsheet with a decision and a reason for every row. It covers seven sub-processes: expense reimbursement, invoice approval, order management, leave request, inventory adjustment, budget variance and onboarding match.
- **Expected impact.** I cannot give absolute hours, because the logs come from a test environment. The realistic claim is relative: the target is the largest measured block of work, and the tool removes the lookup, comparison and notification work while people keep the decisions. Section 5.6 gives an illustrative range and states its assumptions.
- **Main risks.** The client's real systems may not offer the APIs the tool assumes. About half of the recorded work cannot be attributed to a process. My rule values are defaults that the business must confirm. My test results are self-generated. Section 5.7 lists the risks that I judged genuine.

**Where to find things**

| What | Where |
|---|---|
| Step 1 output | `segments.jsonl` (and `outputs/segments.jsonl`) |
| Step 1 results | `docs/baseline_results.md`, `docs/work_log.md` |
| Step 2 analysis | `docs/dataset_b_proposal.md` |
| Step 3 tool (API and connectors) | `Payroll_automation/` (run `python app.py`) |
| Earlier UI attempt (dropped) | `prototype/` |
| Work log | `docs/work_log.md` |

## 2. Pipeline overview

The solution is one chain from raw logs to a working tool. Each stage feeds the next.

```
Raw event logs (Dataset A with ground truth, Dataset B without)
   |
   v
[Step 1a] Boundary detection      app_switch + browser_navigation events
   |
   v
[Step 1b] Segmentation + labeling  fingerprint = application + URL route (with port)
   |
   v
[Step 1c] Merging                  neighbouring segments with the same label
   |                               -> segments.jsonl (1,016 segments, 79 labels)
   v
[Step 2]  Analysis + prioritization  time, occurrences, sessions, apps, variability
   |                               -> ranked list of processes
   v
[Step 3a] Target selection         ROI comparison -> payroll back-office
   |
   v
[Step 3b] Automation tool          spreadsheet in -> API/connector checks -> rules
                                   -> decision + actions -> spreadsheet out + audit log
```

| Stage | Input | Output | Validated how |
|---|---|---|---|
| 1a Boundary detection | Event stream | Candidate boundaries | Recall, precision and F1 against ground truth, all 63 sessions of Dataset A |
| 1b Labeling | Segments | A label per segment | Purity on Dataset A |
| 1c Merging | Labeled segments | Units of work | Segment count before and after, spot checks |
| 2 Analysis | `segments.jsonl` | Ranked processes | Relative comparison only (test-environment timings) |
| 3a Selection | Ranking + case extraction | One automation target | ROI table, Section 5.1 |
| 3b Tool | Case spreadsheet | Decisions, actions, audit log | 350 of 350 expected results on simulated data |

**Two different "pipelines" are in this report.** Steps 1 and 2 are an analysis pipeline that runs once on logs. The Step 3 tool is an operational pipeline that would run on every batch of payroll cases (Section 5.4).

## 3. Step 1: recovering units of work

### Approach

1. **Boundary detection.** Candidate boundaries come from `app_switch` and `browser_navigation` events.
2. **Segments and labels.** Segments are built between boundaries. A fingerprint of the application and the URL route (including the port) gives each segment a label.
3. **Merging.** Neighbouring segments with the same label are merged into one unit of work.

### How I validated it

I built an evaluation function that compares predicted boundaries with the ground truth (3-second tolerance) and I ran everything on all 63 sessions of Dataset A, not on one session. Single sessions were misleading: a baseline of 53.1% on one session became 88.2% on another, and individual sessions ranged from about 31% to 96%.

| Detector | Recall | Precision | F1 |
|---|---|---|---|
| v1: app switches only | 64.6% | 35.2% | 45.3% |
| v2: plus browser navigation | 85.1% | 36.6% | **50.8%** |

The high recall was partly inflated: v2 predicted 52,313 boundaries against 2,009 real executions. Precision is the real weak point.

**Why I accepted 36.6% precision.** The two errors do not cost the same. A false boundary splits one task into two segments, which usually get the same label and are merged again. A missed boundary merges two tasks under one label and cannot be repaired afterwards. So I chose recall over precision. The merge step confirmed this: on one session it reduced 1,079 raw segments to 109.

### Ideas I tested and rejected

Every idea was measured on all 63 sessions before I kept or dropped it.

| Idea | Result | Decision |
|---|---|---|
| Merge boundaries that are close in time (nine thresholds from 1 to 20 seconds) | F1 between 30% and 49%, always below v2 | Rejected. Real transitions can be fast (some real executions lasted about 16.6 seconds) |
| Keep a boundary only when the application changed | Recall 75.0%, precision 25.9%, F1 38.3% | Rejected. Same application does not mean same task |
| Add on-screen text to the fingerprint | Purity unchanged (46.8%) | Rejected. The text exists on too few events |
| Add OCR text of screenshots to the fingerprint | Purity +1.3 on Dataset A (45.9% to 47.1%, no session worse), but the labels on Dataset B grew from 79 to 423 | Rejected. OCR text differs for every document, so it fragments one process into many labels. Purity favours smaller clusters, so the gain on Dataset A did not prove better grouping. The Dataset A gain was also limited because only 14.8% of its referenced screenshots exist on disk (Dataset B: 100%) |
| Remove the port number from the label | Purity fell from 46.8% to 38.3% | Rejected. The same route on another port is another process |

What worked: labeling by the full URL route instead of the domain raised purity from 28.6% on a first session to an average of 46.8% (range 26% to 62%). Dropping the incidental application prefix (which apps happened to be open next to the browser) cost almost nothing (45.9%) and removed a label inconsistency between Step 1 and Step 2, so I adopted it.

### Result on Dataset B

I ran the complete pipeline on all 15 sessions without failures. The submitted file `segments.jsonl` has 1,016 segments and 79 distinct labels. The OCR variant (`outputs/segments_with_ocr.jsonl`) stays in the repository only as a documented rejected experiment.

### Limits

- **Generic desktop applications.** About half of the segments (506 of 1,016) are Word, Notepad, Excel or terminal windows without a URL. They cannot be attributed to a process. A spot check found two Word segments with unrelated content under the same label.
- **Routes are not perfect.** One segment labeled `payroll-items` was actually inventory adjustment. (This turned out to be a clue for Step 3: the route contains several kinds of case.)
- **No ground truth for Dataset B.** The Dataset A purity of about 46% is the only measure I have. I assume that Dataset B behaves similarly.

## 4. Step 2: analysis and priorities

### What is done, how often, by how many

The processes below are the routes that could be identified by their URL. The time is the sum of the segment durations. The logs were recorded in a test environment, so I only compare processes with each other.

| Rank | Process | Total time | Share of attributable time | Occurrences | Sessions (of 15) | Average segment length | Apps involved | Duration variability |
|---|---|---|---|---|---|---|---|---|
| 1 | payroll-items | 48.7 min | 39% | 143 | 14 | about 20 s | 10 | wide variety of apps |
| 2 | leave-applications | 26.0 min | 21% | 120 | 13 | about 13 s | n/a | highest (std about 15.3 s) |
| 3 | onboarding | 21.4 min | 17% | 96 | 9 | about 13 s | 7 | lowest (std about 6.4 s) |
| 4 | social-insurance | 16.8 min | 13% | 57 | 8 | about 18 s | n/a | n/a |
| 5 | resident-tax | 11.0 min | 9% | 34 | 8 | about 19 s | n/a | n/a |
| - | dashboard | 1.8 min | 1% | n/a | n/a | n/a | n/a | excluded |

"Share of attributable time" is the share of the 125.7 minutes that fall into these routes. The dashboard route is excluded because it looks like navigation, not a task. The average segment length is my own calculation (total time divided by occurrences) and is only a rough guide, because segments are merged units.

### How many people

Dataset B has no operator field, so I use the number of sessions as a proxy for reach. The proxy can be wrong in both directions: one person with several sessions is counted several times, and people who share a machine count as one. Payroll-items appears in 14 of 15 sessions, so it reaches almost every worker in the sample. I treat this as an indication of reach, not as a headcount.

### Different handling patterns inside a process

- Payroll-items involves 10 different applications, the widest spread of all. That points to many valid paths through the same route. Section 5.2 shows the reason: the route carries seven different kinds of case.
- Leave applications have the highest duration variability, so the cases branch a lot.
- Onboarding is the most regular process, but Word, Notepad, Windows Explorer and sometimes a terminal appear next to the portal. It is not pure form filling.

### Priority order and reasoning

Priority is based on impact (total time, occurrences, session reach). Feasibility risk is a proxy: application spread and duration variability. Neither is a measured effort estimate.

| Priority | Process | Impact | Feasibility signal | Reasoning |
|---|---|---|---|---|
| 1 | payroll-items | Highest: 48.7 min, 143 occurrences, 14/15 sessions | Riskiest: 10 applications | About twice the impact of the next process and reaches almost every session. Its complexity is the price, so it needs a careful scope |
| 2 | leave-applications | 26.0 min, 120 occurrences, 13/15 sessions | Highest duration variability (std about 15.3 s) | High volume and reach, but the variability means I would first need to understand what drives the different paths |
| 3 | onboarding | 21.4 min, 96 occurrences, 9/15 sessions | Lowest variability (std about 6.4 s) | Smaller and narrower, but the most predictable. Lowest-risk candidate for a first proof of concept |
| 4 | social-insurance | 16.8 min, 57 occurrences, 8/15 sessions | n/a | Meaningful, but lower volume |
| 5 | resident-tax | 11.0 min, 34 occurrences, 8/15 sessions | n/a | Lowest volume of the real processes. Worth automating eventually, not a near-term priority |
| Excluded | dashboard | 1.8 min | n/a | Navigation or orientation, not a task |

**Blind spot.** About half of the recorded activity (generic applications) is not in this ranking. The ranking is directionally useful, but it is built on roughly half of the work.

## 5. Step 3: the automation tool

### 5.1 First a UI prototype for onboarding, then a change of direction

**First attempt (UI automation).** My first choice was onboarding, the lowest-risk candidate. I built a prototype in `prototype/`: a Playwright script against a mock page that repeats the observed loop (open case, read data, paste note, submit), with a dry-run mode and an audit log with masked identifiers. At that stage I was also weighing UI automation against an API approach, because the logs only show what happened on screen.

**Why I dropped it.** I looked at the return on investment again, and onboarding was not convincing:

| | onboarding | payroll-items |
|---|---|---|
| Time share (attributable) | 17% | 39% |
| Occurrences | 96 | 143 |
| Sessions reached | 9 of 15 | 14 of 15 |
| Average segment length | about 13 s | about 20 s |

- The loop I could automate is short (about 13 seconds per occurrence), so each automated case saves little.
- The prototype covers only the browser part. The Word, Notepad and Explorer steps were out of scope because I cannot see inside them.
- UI automation depends on element ids and layout, so it needs maintenance whenever the portal changes.
- **Onboarding is part of the payroll work.** When I extracted the individual cases behind the payroll route (145 cases), onboarding (`onboarding_match`) was one of seven kinds of case. Automating the payroll route therefore includes onboarding instead of leaving it as a separate small project.

**Where I ended up.** The final tool uses **APIs and connectors only.** It does not click through any screen. The ideas of the prototype were kept: a human check before risky actions became the approval loop, and the audit log with masked identifiers carried over. The browser control panel in the final tool is only a front end to start and monitor runs. It is not part of the automation.

### 5.2 Why payroll, and what the seven sub-processes are

`payroll-items` is the name of the portal route. It is not only payroll in the narrow HR sense: the 145 cases that I extracted from it fall into seven kinds. This explains why the route touches 10 applications and shows many handling paths. It is one queue that carries seven different processes.

| Sub-process | Cases in sample | Share | What the tool does with a case (default rules, configurable) |
|---|---|---|---|
| `expense_reimbursement` | 45 | 31% | Compares the claim in the sheet with the record in the ERP and the receipt document. Approves within the limit, sends above-limit cases to the approver |
| `invoice_approval` | 27 | 19% | Compares invoice, purchase record and amounts within a tolerance. Approves, rejects or sends to review on a mismatch |
| `order_management` | 26 | 18% | Checks the order against stock in the warehouse system. Creates the purchase order or posts the stock movement |
| `leave_request` | 23 | 16% | Reads the leave balance from the HR system and applies the per-type rules. Deducts the leave and replies by mail |
| `inventory_adjustment` | 15 | 10% | Compares the requested adjustment with the warehouse record and the supporting document. Posts the movement or sends to review |
| `budget_variance` | 5 | 3% | Compares actual spending with the budget in the ERP. Flags variances above the threshold for review |
| `onboarding_match` | 4 | 3% | Matches the new-hire record in the HR system with the submitted documents. Approves complete matches, flags mismatches |

The seven processes share one shape: look up a record, open a document, compare, decide, notify. That is why one shared engine pays off.

**Why payroll is the right target.**

1. **Impact.** It is the largest measured block of work (39% of attributable time, 14 of 15 sessions), about twice the next route.
2. **It contains onboarding.** My original choice is covered as one of the seven sub-processes, so nothing is lost by switching.
3. **Shared foundation.** One engine, one rule file, one connector layer serve all seven kinds. Expense, invoice, order and leave alone are 83% of the cases, so a single-process script would have left most of the work untouched.
4. **Repeatable rules.** The checks (compare, apply a limit, notify) are deterministic, which suits a rule engine.

**A limit to be clear about.** Two sub-process names (`leave_request`, `onboarding_match`) resemble the separate Step 2 routes `leave-applications` (rank 2) and `onboarding` (rank 3). The tool covers those kinds of case as they appear in the payroll cases. It does not claim to cover the whole of those two routes. The counts also differ by design: Step 2 counts 143 occurrences (merged segments), while the case extraction found 145 cases.

### 5.3 Scope: what I covered and what I deferred

**Covered.** All seven sub-processes, on one shared foundation: one engine, one small rule set per process, one configuration file for thresholds, and one connector layer for all systems (mail, HR, ERP, procurement, warehouse, shared drive). Building all seven costs more than building one. I judged it worth it for the reasons in Section 5.2.

**Deferred.** Connections to the client's real systems (I built a simulated company behind the same API calls), text recognition for scanned documents, integration with the client's approval tool, scheduling, and a web dashboard for live monitoring.

### 5.4 How the tool is built: API and connectors

The tool is a deterministic Python pipeline. Every system is reached through a **connector**: a small API client with a fixed interface. Rules live in a configuration file. The input and the output are one spreadsheet.

**Operational pipeline (one run):**

```
Case spreadsheet
   |  1. backup the workbook
   |  2. health-check every connector (API reachable?)
   |  3. route each row to its process engine (7 engines)
   |  4. look up records through connectors: mail, HR, ERP, procurement, warehouse, shared drive
   |  5. open the documents: Word, PDF, Excel
   |  6. compare sheet vs system record vs document
   |  7. apply the configured rules -> APPROVED / REJECTED / NEEDS_REVIEW
   |  8. carry out the actions: reply mail, leave deducted, purchase order, stock movement
   |  9. write decision + reason next to the original columns
   v
Updated spreadsheet + dashboard + mailbox view + payroll adjustment export + audit log + decision memo per case
```

**Approval loop.** If a case only lacks a person's approval, the approver gets a mail. The next run reads the reply and finishes the case. Reminder after 3 days, escalation after 5.

**Alternatives I rejected.**

| Alternative | Why I rejected it |
|---|---|
| UI automation / RPA (my first attempt, `prototype/`) | It depends on element ids and layout, covers only what is visible on screen, mixes rules with clicks and breaks silently when the portal changes. The final tool does not use it |
| AI agent that decides | The tool makes decisions about money and HR records. They must be repeatable and explainable. A rule engine gives the same answer for the same input and a reason for every decision. An agent would need a much heavier review process |
| Workflow tools (n8n, Power Automate) | Good for triggers and connectors, but the branching (per-type leave rules, tolerances, cross-checks between sheet, system and document) and the testing are easier to control in code. They remain an option for scheduling and notifications |
| Desktop application | No benefit over a browser page for this use |

**API status.** In my test world the connectors talk to a simulated company through the same API calls that real systems would need. Whether the client's real systems offer such APIs is not confirmed. My check of the logs found no action or method attributes in 367 onboarding events, but that is inconclusive for a JavaScript application. This is the main open technical question (Section 5.7).

### 5.5 Test world and verification

Client systems are not available, so I generated a simulated company: 350 cases (50 per process) with employees, mails, invoices, orders, claims, stock and about 225 real documents, and the correct result for each case.

On the default data, the run matched 350 of 350 expected results, the resumed cases after approver replies also matched 350 of 350, and a second run changed nothing. This proves that the rules behave as I designed them. It does **not** prove that they equal the client's real policy, because data and expected results come from the same generator.

The process is documented in `Payroll_automation/docs/Payroll_Automation_Process_Manual.docx`. `python app.py` starts the control panel.

### 5.6 What manual work remains, and the realistic impact

**Work that stays with people.**

- Approvals above limits, by design. The tool never approves beyond its configured authority.
- Cases where sheet, system and document disagree (`NEEDS_REVIEW`).
- Follow-up with requesters and vendors after rejections.
- Scanned or handwritten documents until text recognition exists.
- Ownership of the rules (limits, tolerances, document lists) and maintenance of the connectors.
- Monitoring of the run reports and the error rows.

**Impact.** On my test data 271 of 350 cases (77%) were decided without a person. I planned that mix in the generator, so it is not a forecast. The real share can only be measured in shadow mode. To show how much the result depends on the assumptions, here is an illustration. It uses the 39% time share of payroll-items from Step 2 and assumptions that I did not measure:

| Scenario | Cases closed without a person | Handling time saved on those cases | Saved share of payroll-items time | Saved share of attributable time |
|---|---|---|---|---|
| Conservative | 40% | 50% | 20% | about 8% |
| Medium | 60% | 70% | 42% | about 16% |
| Optimistic | 80% | 80% | 64% | about 25% |

The logs cover only about half of the recorded work as attributable, and their time values come from a test environment. I therefore claim no hours. My claim is: this is the largest measured block of work, and even a conservative outcome removes a meaningful share of it, while people keep every decision that needs judgment.

### 5.7 Risks (reviewed)

I re-checked every risk against the current design (API and connectors) and kept only those that apply to the final tool and are backed by evidence. Two changes from the earlier draft:

- **Removed:** UI fragility and portal-change maintenance. These applied to the dropped prototype, not to the API-based tool. The equivalent risk for the final tool is API change, which is listed below.
- **Reworded:** "many handling paths in payroll". The route carries seven kinds of case (Section 5.2), so the risk is now about exceptions inside each sub-process.

| # | Risk | Evidence | How I would address it |
|---|---|---|---|
| 1 | The client's real systems may not offer usable APIs, or not the ones my connectors assume | The tool is only tested against a simulated company. No action or method attributes in 367 onboarding events (inconclusive for a JavaScript application) | Confirm systems, APIs and credentials with the client's engineers in discovery. Connectors are separate modules, so only the adapters change, not the rules. A UI adapter is a possible fallback for a system without an API, but I did not build one |
| 2 | Validation is circular | Test data and expected results come from the same generator (350 of 350 proves the rules run as designed, not that they match policy) | Shadow mode on real cases, comparing tool recommendations with human decisions |
| 3 | Rule values are my defaults | Limits, tolerances and document lists cannot be read from logs | The business owner confirms them. They change in one configuration file, not in code |
| 4 | The process ranking may be wrong | About 50% of segments are generic applications. Purity is about 46%. A route labeled `payroll-items` contained inventory work | Treat the ranking as an estimate. Confirm with observation or interviews before the full rollout |
| 5 | Timings and reach are only indicative | Test-environment logs. No operator field, so sessions are only a proxy for people | Compare processes only relatively. Ask the client for user counts. Measure real handling times in shadow mode |
| 6 | Exceptions inside each sub-process | Payroll-items shows 10 applications and many paths | Start with the sub-processes with the clearest rules (expense and invoice are about half of the sample). Track the share of `NEEDS_REVIEW` and add rules from real exceptions |
| 7 | Steps I cannot see | Word, Notepad and Explorer content is not visible in most segments, so my document checks are assumptions | A discovery phase with the staff to confirm the real steps and documents |
| 8 | A case cannot be linked to a person, vendor or candidate | The sample sheet only has a case id | Add an identifier column, or take the mapping from the client's workflow system. Without it a row ends as "record not found" |
| 9 | Documents in other layouts, and scans | Only text-based PDF, Word and Excel are read. Dataset B screenshots are legible (Tesseract with Japanese, 100% of screenshots exist), so text recognition is feasible later | Map fields per document type in configuration and test on real samples. Add text recognition in a later phase |
| 10 | Personal and payroll data | HR and payroll records are handled | Audit log for every decision, human approval above limits, masked identifiers, least-privilege service account |
| 11 | Users may not trust automated decisions | Decisions affect pay and approvals | Shadow mode first, reasons on every decision, the approval loop, and a reviewed sample in the assisted phase |

### 5.8 Rollout plan

1. **Discovery.** Confirm systems, APIs, credentials, document locations and the policy values for two sub-processes. Expense and invoice make up about half of the sample cases.
2. **Shadow mode.** The tool recommends, people decide, and I compare the results and the share of cases that need review.
3. **Assisted mode.** Notifications and low-risk bookings are carried out by the tool. Staff review a sample.
4. **Full automation** for those two processes, then order management and leave, and later the rest. A rollback is always possible because every action is tied to a case and logged.

## 6. How I used the 7 days

| Day | Time | Work | Why |
|---|---|---|---|
| 1 | 4-5 h | Studied both datasets | I needed to know which signals exist before designing anything |
| 2 | 6-7 h | Boundary detector and evaluation; two filters rejected | Precision was the weak point, and the numbers decided |
| 3 | 5-6 h | Labeling, merging, first run on Dataset B, spot checks | I needed labeled segments for Step 2 |
| 4 | 4-5 h | API check, label consistency fix, onboarding UI prototype | Keep Step 1 and 2 consistent, test feasibility early |
| 5 | 3-4 h | OCR investigation| Test whether screen content could fix generic-application labels |
| 6 | 2-3 h | Ranked all processes, chose payroll (7 sub-processes) as the target; midsem exams limited the time | Choose the Step 3 target and start thinking about turning the pipeline into a tool |
| 7 | 6-7 h | Built and tested the payroll tool (API and connectors), control panel, manual, demo video | Deliver something that works |

In total this is about 30 to 37 hours. These are estimates that I reconstructed at the end. Roughly three quarters of the time (Days 1 to 5) went into Step 1 and the early prototype, where the accuracy ceiling was low. I stopped refining when further tests stopped paying off (the Day 2 decision and the Day 5 rejection). In hindsight I would leave more time for Step 3, because it decides the ROI. That is also why the Step 3 tool is a prototype with simulated systems and not a production system.

## 7. Use of generative AI

I used AI assistants during the project. They helped me write code (the analysis scripts and the Step 3 tool), suggested options, and helped me write parts of the documents. I decided what to test, which results were good enough, which ideas to keep or drop, the choice of payroll and the requirements of the tool. I ran the code on my laptop, checked the results and found problems by running things. The work log describes this for each day.