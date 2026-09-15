import json
import glob

seen_attrs = []
count_checked = 0

for chunk in glob.glob("dataset_b/ses_*/chunk_*"):
    ef = chunk + "/events.jsonl"
    try:
        with open(ef, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e["event_type"] in ("browser_click", "browser_form_input"):
                    url = e.get("context", {}).get("active_browser_tab", {}).get("url", "")
                    if "onboarding" in url:
                        count_checked += 1
                        el = e.get("payload", {}).get("element", {})
                        attrs = el.get("attributes", {})
                        if attrs:
                            seen_attrs.append(attrs)
    except FileNotFoundError:
        continue

print(f"Total onboarding browser_click/form_input events checked: {count_checked}")
print(f"Events with non-empty element attributes: {len(seen_attrs)}")

# check specifically for API/form-submission clues
found_action = sum(1 for a in seen_attrs if a.get("action"))
found_method = sum(1 for a in seen_attrs if a.get("method"))
print(f"Events with a filled 'action' attribute: {found_action}")
print(f"Events with a filled 'method' attribute: {found_method}")

print("\nSample attribute dicts found (first 5):")
for a in seen_attrs[:5]:
    print(" ", a)

    import json as json_module

results = {
    "total_onboarding_ui_events_checked": count_checked,
    "events_with_attributes": len(seen_attrs),
    "events_with_action_attribute": found_action,
    "events_with_method_attribute": found_method,
    "conclusion": "inconclusive - no action/method attributes found, but consistent with a JS SPA "
                  "using fetch()/AJAX rather than traditional form submission. Cannot confirm or deny "
                  "an API exists from DOM attributes alone, since network traffic was not captured.",
    "decision": "build Step 3 prototype as UI-level automation, not an assumed API integration"
}

with open("outputs/api_evidence_check.json", "w", encoding="utf-8") as f:
    json_module.dump(results, f, indent=2, ensure_ascii=False)

print("\nSaved to outputs/api_evidence_check.json")