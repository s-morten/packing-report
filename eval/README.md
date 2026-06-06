# Evaluation Scripts

This directory contains scripts for evaluating model development
and generating plots. Each script is self-contained and produces
visualizations in the `output/` subdirectory.

## Usage

```bash
uv run eval/some_script.py
```

## Adding a new evaluation

Add a Python script to this directory. It can import from
`database_io` (data access) and `insights` (analytics code).
