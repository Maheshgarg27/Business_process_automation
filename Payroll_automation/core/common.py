"""Shared helpers: paths, config loading, result and context objects."""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
RUNTIME.mkdir(exist_ok=True)


def load_config(path=None):
    path = Path(path) if path else ROOT / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_date(cfg) -> date:
    v = cfg.get("run_date")
    return date.fromisoformat(str(v)) if v else date.today()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Result:
    """What every processor returns for one spreadsheet row."""
    status: str                          # APPROVED | REJECTED | NEEDS_REVIEW | ERROR
    detail: str                          # plain-language reason (goes into the sheet)
    reference: str = ""                  # id of the record created in the target system
    codes: list = field(default_factory=list)      # machine-readable codes of the rules that fired
    approval: dict = None                # set when a human approval can complete the case
    extra: dict = field(default_factory=dict)      # data for exports (employee, amount, days ...)


@dataclass
class Context:
    """Carries a human approver's answer into a re-run of a processor."""
    approved: frozenset = frozenset()
    denied: frozenset = frozenset()
    approver: str = ""

    def resolve(self, review):
        """review = [(code, text)]. Returns (still_open, extra_reject_texts, notes)."""
        open_, rejects, notes = [], [], []
        for code, text in review:
            if code in self.approved:
                notes.append(f"承認済み({self.approver}): {text}")
            elif code in self.denied:
                rejects.append(f"承認者が却下({self.approver}): {text}")
            else:
                open_.append((code, text))
        return open_, rejects, notes
