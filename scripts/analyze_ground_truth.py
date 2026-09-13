import json
from pathlib import Path
from collections import Counter, defaultdict

data_path = Path("dataset_a")

process_count = Counter()
variant_count = Counter()
process_variant = defaultdict(Counter)

total_executions = 0

for manifest in data_path.glob("**/gt_manifest.json"):
    with open(manifest, "r", encoding="utf-8") as f:
        data = json.load(f)

    for process in data.get("processes", []):
        code = process.get("code")

        for execution in process.get("executions", []):
            variant = execution.get("variant")

            total_executions += 1
            process_count[code] += 1
            variant_count[variant] += 1
            process_variant[code][variant] += 1

print("Total executions:", total_executions)

print("\nExecutions by process:")
for process, count in process_count.most_common():
    print(f"  {process}: {count}")

print("\nExecutions by variant:")
for variant, count in variant_count.most_common():
    print(f"  {variant}: {count}")

print("\nProcess × variant:")
for process in sorted(process_variant):
    print(f"  {process}:")
    for variant, count in process_variant[process].most_common():
        print(f"    {variant}: {count}")