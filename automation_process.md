# Payroll Automation Tool — Complete Process Manual

## 1. Purpose

Fully automate the `payroll-items` business process discovered in Dataset B —
the highest time-consuming, highest-frequency process found in Step 2
analysis — including the note-drafting step, which was originally assumed to
require human judgment. This is achieved by delegating note drafting to an
LLM at runtime, grounded in real case data, rather than trying to train a
model (infeasible — no ground-truth note data exists in the logs).

**End-to-end flow**: input case list -> read case data -> mask sensitive
fields -> LLM drafts note -> unmask/map back into real form -> fill note
field -> (optional review checkpoint) -> submit -> log result.

## 2. The real business process (as discovered from event logs)

Two related but distinct systems were found under the `payroll-items` label:

- **Port 5133 — Finance/Accounting system** (財務会計システム): invoice
  approval workflow (請求書承認). Each case: an ID (`P6-...`), vendor ID,
  vendor name (取引先), a reference/category (区分, e.g. "請求書承認
  INV-2026-XXXX"), a type tag (種別: 定常 "standard" / 調整 "adjustment"),
  an amount (金額), and a status (ステータス). A note field
  (処理内容・確認コメント, `#pi-note`) and submit button (承認/保留 —
  approve/hold, `#btn-pi-ok`) complete each case.
- **Port 5132 — HR Payroll system** (HR人事給与システム): salary/expense
  adjustment workflow (経費精算・給与変更). Similar structure: case ID
  (`P1-...`/`P4-...`), employee ID, employee name (氏名), category (e.g.
  扶養控除変更 "dependent deduction change", 残業手当調整 "overtime
  adjustment"), amount, type, status.
- Real people cross-reference a separate Excel sheet (経費照合) during this
  process to manually verify amounts against a reference figure —
  confirmed via screenshot inspection (formula-driven variance columns).

**Discovered UI interaction pattern** (from real `browser_click` /
`browser_form_input` events): click a case row -> read displayed fields ->
type into the note textarea -> click the approve/hold button -> move to
next case.

## 3. Why this process (business justification)

- Highest total time consumption found in Step 2 analysis (~48.7 min
  across Dataset B sample) — largest recurring time-sink identified.
- Recurring every processing cycle, touches many vendors/employees per run.
- Involves manual cross-system reconciliation (portal <-> Excel), which is
  slow and error-prone by nature — a classic automation-appropriate pattern.
- High cost of error: incorrect payroll/invoice processing has real
  financial and compliance consequences, unlike lower-stakes processes
  (e.g. onboarding).
- App-usage analysis showed payroll-items uses the same number of distinct
  apps as onboarding (5) — the earlier "10 apps, too complex" estimate was
  incorrect and has been corrected in the report. Actual added risk comes
  from duration variability (~15% higher than onboarding) and the
  two-sub-system split (finance vs HR), not raw app count.

## 4. Input

A structured list of cases to process, retrieved from the portal (or
supplied as a batch file for the prototype):

```json
[
  {
    "case_id": "P6-07010448-002",
    "system": "finance",
    "vendor_or_employee_id": "V3006",
    "vendor_or_employee_name": "北陸部品工業株式会社",
    "category": "請求書承認 INV-2026-7345",
    "type_tag": "調整",
    "amount_jpy": 455128,
    "reference": "発注番号照合：INV-2026-7345"
  }
]
```

## 5. Security / PII handling — mask before sending to the LLM

**Principle**: the LLM only needs enough context to draft a plausible,
correctly-toned processing note. It does not need real identities.

**Before calling the LLM**, replace identifying fields with anonymous
tokens:

| Real field | Sent to LLM as |
|---|---|
| `vendor_or_employee_name` | `"Party_1"`, `"Party_2"`, ... (session-local mapping) |
| `vendor_or_employee_id` | omitted entirely |
| `case_id` | omitted entirely (tracked only locally) |
| `amount_jpy`, `category`, `type_tag`, `reference` | sent as-is — needed for a sensible note, not personally identifying on their own |

```python
import hashlib

def mask_case_for_llm(case, token_map):
    name = case["vendor_or_employee_name"]
    if name not in token_map:
        token_map[name] = f"Party_{len(token_map) + 1}"
    return {
        "party": token_map[name],
        "category": case["category"],
        "type_tag": case["type_tag"],
        "amount_jpy": case["amount_jpy"],
        "reference": case["reference"],
    }
```

**After the LLM responds**, the drafted note is generic/templated text
(e.g. "Party_1's adjustment of ¥455,128 for INV-2026-7345 reviewed and
approved.") — before filling the real form, replace the token back with
the real name using the same local `token_map` (never send the map itself
anywhere external):

```python
def unmask_note(note_text, token_map):
    reverse_map = {v: k for k, v in token_map.items()}
    for token, real_name in reverse_map.items():
        note_text = note_text.replace(token, real_name)
    return note_text
```

**Additional safeguards**:
- `token_map` lives only in memory for the duration of one run — never
  persisted to disk or logs.
- Only the masked payload is sent over the network to the LLM API; the
  real name substitution happens locally, after the response returns.
- Audit log (Section 8) records the masked/hashed identifier, never the
  real name or ID, consistent with the existing onboarding prototype's
  logging approach.

## 6. LLM prompting approach

```python
PROMPT_TEMPLATE = """
You are drafting a short, professional payroll/invoice processing note in
Japanese, for an internal financial system. Given the case details below,
write a 1-2 sentence note stating what was reviewed and the outcome
(approved / on hold), matching the tone of a financial approval comment.

Party: {party}
Category: {category}
Type: {type_tag}
Amount: JPY {amount_jpy}
Reference: {reference}

Respond with ONLY the note text, in Japanese, nothing else.
"""
```

Call via the standard `/v1/messages` API (or whichever LLM endpoint is
configured), parse the plain-text response, run `unmask_note()`, then
proceed to fill the form.

## 7. Human checkpoint (recommended, toggleable)

Even with LLM-drafted notes, keep a **dry-run/review mode** as a toggle:

- `DRY_RUN = True` (default): draft the note, print/log it for review,
  do NOT click submit.
- `DRY_RUN = False`: after drafting, auto-fill and submit without pausing.

This is a deliberate, stated design choice — not a capability gap. Payroll
touches real financial/compliance-sensitive records; a real deployment
should allow enabling a review step, even if the prototype demonstrates
full end-to-end automation with it switched off.

## 8. Output

1. **`outputs/payroll_automation_results.json`** — per case:
```json
{"case_id": "P6-07010448-002", "status": "submitted", "note_used": "<final note text>", "timestamp": "..."}
```
2. **`outputs/payroll_automation_log.txt`** — audit trail, masked identifiers only (SHA-256 truncated hash), consistent with the onboarding prototype's logging.

## 9. Architecture / tech stack

- **Python + Playwright** — browser automation (no confirmed API found in
  logs; same reasoning as onboarding).
- **LLM API call** — for note drafting, using masked input (Section 5/6).
- **Mock portal(s)**: `prototype/mock_payroll_finance_portal.html` (port
  5133 style) and/or `prototype/mock_payroll_hr_portal.html` (port 5132
  style), built the same way as `mock_onboarding_portal.html` — replicating
  the real element IDs (`#pi-note`, `#btn-pi-ok`) found in actual logs.
- Reuses existing dry-run + masked-logging infrastructure from the
  onboarding prototype where possible.

## 10. Edge cases to handle

- Missing/empty note field on page -> log and skip case, continue batch
- LLM call failure/timeout -> fall back to a generic templated note
  (non-LLM), flag case as `status: "fallback_note_used"` for later human
  review
- Case with no `reference` field (some categories may lack it, e.g. HR
  adjustments) -> prompt template must handle optional fields gracefully

## 11. What remains explicitly NOT automated / manual

- Verifying the LLM-drafted note is factually and contextually correct
  before high-stakes submission (mitigated by optional dry-run review)
- Initial case list extraction/export from the real portal into the
  input format
- Real authentication/session handling with the live systems
- Cross-system reconciliation logic itself (the Excel variance-checking
  step) is not automated in this prototype — noted as a follow-on
  opportunity, not attempted given time constraints
- Idempotency (preventing double-submission on reruns) — same limitation
  as the onboarding prototype

## 12. Summary of what makes this "full automation"

| Step | Automated? |
|---|---|
| Reading case data | Yes |
| Masking PII before external LLM call | Yes |
| Drafting the processing note | Yes (via LLM) |
| Unmasking / inserting real identity into final note | Yes |
| Filling the form | Yes |
| Submitting | Yes (toggle: auto or after review) |
| Looping across all cases | Yes |
| Logging / audit trail (masked) | Yes |

The only non-automated element is an **optional** human review checkpoint,
included by design for financial-data safety — not because any step is
technically incapable of running unattended.