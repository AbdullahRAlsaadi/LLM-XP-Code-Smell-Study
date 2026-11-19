# LLM-Assisted Code Smell Detection in the XP Refactoring Step

Replication package for the MSCS811 (Advanced Software Design and Development) project report:

> *Evaluating Prompting Strategies for LLM-Assisted Code Smell Detection in the Refactoring Step of Extreme Programming*
> Abdullah Raji AlSaadi, College of Computer Science and Engineering, Taibah University, 2026.

The study places an LLM review inside the Refactor step of XP's Red-Green-Refactor cycle and compares three prompting strategies (zero-shot, two-shot, role-based) with the Pylint static analyser on five code smells.

## Repository structure

| Path | Content |
|---|---|
| `dataset/` | The 25 benchmark items (`item_01.py` to `item_25.py`), in shuffled order |
| `ground_truth.csv` | Target smell, label (1 = smelly, 0 = not smelly) and provenance of every item |
| `prompts/` | The three prompt templates; `{CODE}` is replaced with the file content |
| `results/chatgpt_raw_answers.csv` | The 75 ChatGPT answers, recorded verbatim |
| `results/pylint_output.txt` | Pylint output for the 25 items |
| `results/scores.txt` | Precision, recall and F1 per smell and method |
| `scripts/evaluate.py` | Recomputes all scores from the raw answers and the ground truth |
| `scripts/run_pylint.sh` | Runs Pylint with the settings used in the study |
| `worked_example/` | One full Red-Green-Refactor cycle on `item_14.py`, with pytest tests |

## Dataset

| Target smell | Source | Smelly | Not smelly |
|---|---|---|---|
| Long Method | Pysmell validation set (real code) | 3 | 2 + 4 clean |
| Large Class | Pysmell validation set (real code) | 3 | 2 + 4 clean |
| Long Parameter List | Pysmell validation set (real code) | 3 | 2 + 4 clean |
| Duplicate Code | Seeded | 3 | 4 clean |
| Feature Envy | Seeded | 3 | 4 clean |

- **Real items (15)** come from the manually inspected validation set of the Pysmell study (Chen et al., IEEE SATE 2016, doi:10.1109/SATE.2016.10; data at https://github.com/chenzhifei731/Pysmell). Each function or class was extracted unchanged from the project revision listed in `ground_truth.csv` (project, commit or tag, file path and line).
- **Seeded items (6)** were written for this study with a known smell planted in each, because no labelled real Python data was found for Duplicate Code or Feature Envy.
- **Clean items (4)** contain none of the five smells and serve as negatives for every smell.

The real code fragments remain under the licences of their original projects.

## Experimental setup

- **LLM:** ChatGPT, model shown in the interface as GPT-6, 1 Jumada al-Akhirah 1448 AH (11 November 2026). Each of the 75 runs (25 items × 3 prompts) used a new temporary chat. Answers were not corrected or re-run.
- **Baseline:** Pylint 4.1.2, default limits, each file run separately, checks R0801, R0902, R0904, R0912, R0913, R0914, R0915 and R0917.
- **Scoring:** a smell is scored only on the items that target it and on the four clean items. Macro averages give each smell equal weight.

## Results (macro average over five smells)

| Method | Precision | Recall | F1 |
|---|---|---|---|
| ChatGPT zero-shot | 82.0% | 93.3% | 85.3% |
| ChatGPT two-shot | 87.0% | 100% | **92.1%** |
| ChatGPT role-based | 82.0% | 100% | 89.3% |
| Pylint 4.1.2 | 46.7% | 40.0% | 42.7% |

Per-smell results are in `results/scores.txt`.

## Reproducing the results

Requires Python 3.10 or later.

```bash
# Recompute all scores from the recorded answers
python scripts/evaluate.py

# Re-run the Pylint baseline
pip install pylint==4.1.2
bash scripts/run_pylint.sh

# Worked example: copy test_billing.py into v0, v1 or v2, then run pytest there
pip install pytest
cp worked_example/test_billing.py worked_example/v1/
cd worked_example/v1 && python -m pytest -q
```

Expected worked-example results: `v0` 4 failed, `v1` 4 passed, `v2` 4 passed.
