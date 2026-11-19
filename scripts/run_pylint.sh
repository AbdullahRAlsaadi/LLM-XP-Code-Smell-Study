#!/usr/bin/env bash
# Runs Pylint 4.1.2 on each dataset file separately, design checks only.
# Usage (from the repository root): bash scripts/run_pylint.sh
for f in dataset/item_*.py; do
  pylint --disable=all \
    --enable=R0801,R0902,R0904,R0912,R0913,R0914,R0915,R0917 \
    --score=n "$f"
done
