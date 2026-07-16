# Data

Benchmark data is intentionally not included in this repository.

The full experiments use LogiOR/ORThought-compatible optimization benchmark files. Keep your local dataset outside Git, then point the code to it with either:

```bash
export LOGIOR_DATASET_ROOT=/absolute/path/to/LogiOR
```

or:

```bash
python scripts/run_pilot.py --config configs/final/baseline_exec_only.yaml --dataset-root /absolute/path/to/LogiOR
```

The adapter accepts a directory containing `prob_*` folders directly, or an ORThought-style layout such as `datasets/processed/LogiOR` plus optional `datasets/summary/summary_logior.json`.

Check the dataset provider's license and access terms before using or redistributing any benchmark files. Do not commit raw benchmark data, generated code dumps, model outputs, Gurobi licenses, or API credentials.

The default test suite uses synthetic temporary fixtures and does not require the external benchmark.