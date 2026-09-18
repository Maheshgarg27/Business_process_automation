"""Append-only audit trail: one JSON line per decision (who/what/why/when)."""
import json
from core.common import RUNTIME

AUDIT_FILE = RUNTIME / "audit_log.jsonl"


def record(entry: dict):
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
