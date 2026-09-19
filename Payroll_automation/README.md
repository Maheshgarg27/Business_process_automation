# Payroll process automation

Takes one Excel sheet of mixed back-office cases, decides each one by calling the company systems
over REST APIs, and writes the decision back into the same sheet.

Processes: onboarding, invoice approval, leave request, expense reimbursement, inventory adjustment,
budget variance, order management.

## Control panel (one command)

    python app.py

Builds a fresh dummy sheet with all supporting records and documents, then opens a page in the browser:
select the spreadsheet, press Start, follow the live log, and open the dashboard, the spreadsheet and the
mailbox (Japanese or English). Each start of the app replaces the previous dummy data.

## Quick start (command line)

    pip install -r requirements.txt
    python -m tools.generate_dataset                                    # test world: 350 cases, systems, documents
    python run_pipeline.py --input data/input/payroll_cases_test.xlsx   # run
    python -m tools.verify_results --input data/input/payroll_cases_test.xlsx

Approval loop (people answer the approval mails; the second command stands in for them in the prototype):

    python -m tools.simulate_approvers
    python run_pipeline.py --input data/input/payroll_cases_test.xlsx   # picks up the replies, finishes the cases
    python -m tools.verify_results --input data/input/payroll_cases_test.xlsx --after-approvals

After a run open `runtime/dashboard.html` and `runtime/mailbox.html` in a browser.
`runtime/exports/payroll_adjustments.xlsx` holds approved reimbursements and leave deductions for payroll.

## Layout

    config/config.yaml     thresholds, document paths, approval settings
    app.py                 web control panel (start button, live log, results)
    ui/index.html          the page served by app.py
    run_pipeline.py        orchestrator
    core/                  api client, excel i/o, audit log, document parsing, workflow state, JA->EN translation
    processors/            one module per process (the business rules)
    services/              simulated enterprise systems (mail, HRIS, ERP, procurement, WMS, shared drive)
    reports/               mailbox page (JA/EN), spreadsheet view, dashboard, payroll export
    tools/                 dataset generator, approver simulator, result verification
    docs/                  design and process manual

## Connecting real systems

Processors talk only to `core/api_client.py`. Point `api.base_url` / `api_key` at the real gateway, map the
endpoint paths in the processors, and set the document path templates under `paths:` in the config.
`services/` and `tools/generate_dataset.py` are only needed for the prototype.

## Notes

- Input columns are never changed; result columns are appended (`result_status`, `result_detail`,
  `result_reference`, `processed_at`, `run_id`). A backup goes to `backups/` before every run.
- Finished rows are skipped on re-run, ERROR rows are retried, `--retry-review` re-checks corrected rows.
- Every decision is appended to `runtime/audit_log.jsonl`; a memo per case is stored on the shared drive.
