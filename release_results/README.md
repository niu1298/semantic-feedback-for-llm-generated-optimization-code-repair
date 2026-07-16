# Release Results

This directory is the canonical public evidence snapshot for the repository. It keeps small, human-readable summaries and selected figures so the results are browsable on GitHub.

Raw experiment outputs are intentionally excluded. The excluded local output tree contained generated code, prompts, stdout/stderr captures, per-attempt JSON, raw run directories, and many generated Python files. Those artifacts can be regenerated from the retained configs with a valid LogiOR dataset path, Gurobi setup, and model API credentials.

## Retained Files

- `final_results.md` - protocol-labelled result tables for the README.
- `full92_candidate_comparison.md` - final four-method comparison summary.
- `full92_candidate_band_breakdown.md` - final comparison by difficulty band.
- `full92_candidate_solve_overlap.md` - overlap among solved problem sets.
- `full92_candidate_cost_tradeoff.md` - API call and cost-efficiency summary.
- `convergence_summary.md` - convergence summary for the final comparison.
- `medium_candidate_comparison.md`, `v3_module_validation_summary.md`, `gate_policy_summary.md`, and `feedback_uptake_summary.md` - small ablation/provenance summaries used by the report.
- `figures/` - selected report figures copied from the final report assets.

## Excluded Files

The repository does not include `outputs/`, `raw_runs/`, prompt transcripts, generated code dumps, benchmark data, model checkpoints, caches, solver licenses, or API credentials.