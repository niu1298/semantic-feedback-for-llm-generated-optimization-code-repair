# V3 Module Validation Summary

| Module | Label | Scale | Solved | Parse health | Max prompt | Max feedback | Classification |
|---|---|---|---:|---:|---:|---:|---|
| execution_baseline | baseline_medium | medium | 6/24 | n/a | 10459 | 3185 | baseline_reference |
| performance_reference | original_advisory_medium | medium | 8/24 | 1 | 16172 | 9243 | main_repair_candidate |
| adaptive_compressed_direct_advisory | adaptive_compressed_medium | medium | 7/24 | 1 | 10985 | 3000 | main_repair_candidate |
| formulation_spec_generation_spec_then_code | pilot_20260518_052118 | pilot8 | 5/8 | 1 | 10395 | 2654 | main_repair_candidate |
| formulation_spec_generation_spec_then_code | pilot_20260518_061825 | mini12 | 8/12 | 0.944 | 13424 | 3590 | main_repair_candidate |
| code_to_spec_spec_comparison | pilot_20260518_062741 | pilot8 | 3/8 | 1 | 6691 | 2000 | diagnostic_only |
| code_to_spec_spec_comparison | pilot_20260518_064101 | mini12 | 7/12 | 0.905 | 8313 | 2000 | diagnostic_only |
| code_to_spec_diagnostic_only | pilot_20260518_065837 | pilot8 | 1/8 | 0.875 | 7365 | 2991 | diagnostic_only |
| hybrid_static_spec_semantic_diagnosis | pilot_20260518_071131 | pilot8 | 2/8 | 1 | 7736 | 3000 | future_work_not_ready |
| multi_advisor_aggregation | pilot_20260518_072708 | pilot8 | 1/8 | 1 | 7892 | 3000 | diagnostic_only |
| multi_advisor_aggregation | pilot_20260518_073406 | pilot8 | 5/8 | 1 | 7904 | 3000 | main_repair_candidate |
| multi_advisor_aggregation | pilot_20260518_074236 | mini12 | 8/12 | 1 | 9544 | 3000 | main_repair_candidate |
| feedback_uptake_scoring | feedback_uptake_adaptive_compressed | offline_medium | n/a | n/a | n/a | n/a | retrospective_analysis_tool |
| feedback_uptake_scoring | feedback_uptake_original_advisory | offline_medium | n/a | n/a | n/a | n/a | retrospective_analysis_tool |
| retrospective_gate_analysis | retrospective_gate_policy_analysis | offline_medium | n/a | n/a | n/a | n/a | retrospective_only |

## Interpretation

- `main_repair_candidate` means the module is a candidate for the next scaled repair comparison.
- `diagnostic_only` means the module may be useful for analysis or qualitative failure explanation without becoming the main repair loop.
- `retrospective_only` means the module should remain offline and must not enable `hard_gate` yet.
- `future_work_not_ready` means either prompt/cost/noise risks or insufficient performance signal remain.
