"""Recompute precision, recall and F1 for ChatGPT and Pylint.

Usage (from the repository root):
    python scripts/evaluate.py

Scoring rule: a smell is scored only on the items that target it and on the
four clean items (label NONE). A smell reported on a smelly item with a
different target is not scored, because its true label is unknown.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMELLS = ["Long Method", "Large Class", "Long Parameter List",
          "Duplicate Code", "Feature Envy"]
PATTERNS = {
    "Long Method": r"long\s+method",
    "Large Class": r"large\s+class",
    "Long Parameter List": r"long\s+parameter\s+list",
    "Duplicate Code": r"duplicat(e|ed)\s+code",
    "Feature Envy": r"feature\s+envy",
}
PYLINT_MAP = {
    "R0912": "Long Method", "R0914": "Long Method", "R0915": "Long Method",
    "R0902": "Large Class", "R0904": "Large Class",
    "R0913": "Long Parameter List", "R0917": "Long Parameter List",
    "R0801": "Duplicate Code",
}


def load_truth():
    with open(ROOT / "ground_truth.csv", newline="") as fh:
        return {r["file"]: r for r in csv.DictReader(fh)}


def scores(truth, predicted):
    """predicted(file, smell) -> bool. Returns per-smell rows and macro averages."""
    rows = []
    for smell in SMELLS:
        tp = fp = fn = 0
        for name, item in truth.items():
            if item["target_smell"] == smell:
                label = item["label"] == "1"
            elif item["target_smell"] == "NONE":
                label = False
            else:
                continue
            hit = predicted(name, smell)
            tp += label and hit
            fp += (not label) and hit
            fn += label and not hit
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        rows.append((smell, tp, fp, fn, p, r, f1))
    macro = [sum(row[i] for row in rows) / len(rows) for i in (4, 5, 6)]
    return rows, macro


def main():
    truth = load_truth()
    answers = {}
    with open(ROOT / "results" / "chatgpt_raw_answers.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            answers.setdefault(r["strategy"], {})[r["file"]] = r["answer"]

    methods = {}
    for strategy, by_file in answers.items():
        methods[f"ChatGPT {strategy}"] = (
            lambda f, s, b=by_file: bool(re.search(PATTERNS[s], b[f], re.I)))
    methods["Pylint 4.1.2"] = lambda f, s: s in {
        PYLINT_MAP[c] for c in truth[f]["pylint_messages"].split(";") if c}

    for name, pred in methods.items():
        rows, macro = scores(truth, pred)
        print(f"\n{name}")
        print(f"  {'Smell':<22}{'TP':>4}{'FP':>4}{'FN':>4}{'P':>8}{'R':>8}{'F1':>8}")
        for smell, tp, fp, fn, p, r, f1 in rows:
            print(f"  {smell:<22}{tp:>4}{fp:>4}{fn:>4}{p:>8.1%}{r:>8.1%}{f1:>8.1%}")
        print(f"  {'Macro average':<34}{macro[0]:>8.1%}{macro[1]:>8.1%}{macro[2]:>8.1%}")


if __name__ == "__main__":
    main()
