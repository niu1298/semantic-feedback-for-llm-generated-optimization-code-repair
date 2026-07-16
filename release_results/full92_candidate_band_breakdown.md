# Full92 Band Breakdown

| method | band | selected_count | solved_count | pass_rate | final_error_distribution |
| --- | --- | --- | --- | --- | --- |
| baseline | band1 | 20 | 6 | 0.3 | {"compile_failed": 1, "no_objective": 1, "objective_mismatch": 7, "runtime_error": 5, "unknown": 6} |
| baseline | band2 | 20 | 9 | 0.45 | {"no_objective": 2, "objective_mismatch": 3, "runtime_error": 6, "unknown": 9} |
| baseline | band3 | 20 | 6 | 0.3 | {"no_objective": 2, "objective_mismatch": 6, "runtime_error": 6, "unknown": 6} |
| baseline | band4 | 32 | 4 | 0.125 | {"compile_failed": 2, "no_objective": 3, "objective_mismatch": 13, "runtime_error": 10, "unknown": 4} |
| original_advisory | band1 | 20 | 14 | 0.7 | {"compile_failed": 1, "no_objective": 1, "objective_mismatch": 4, "unknown": 14} |
| original_advisory | band2 | 20 | 12 | 0.6 | {"no_objective": 1, "objective_mismatch": 5, "runtime_error": 2, "unknown": 12} |
| original_advisory | band3 | 20 | 9 | 0.45 | {"no_objective": 2, "objective_mismatch": 5, "runtime_error": 4, "unknown": 9} |
| original_advisory | band4 | 32 | 11 | 0.344 | {"compile_failed": 1, "no_objective": 3, "objective_mismatch": 6, "runtime_error": 11, "unknown": 11} |
| adaptive_compressed | band1 | 20 | 11 | 0.55 | {"compile_failed": 1, "objective_mismatch": 4, "runtime_error": 4, "unknown": 11} |
| adaptive_compressed | band2 | 20 | 11 | 0.55 | {"no_objective": 1, "objective_mismatch": 3, "runtime_error": 5, "unknown": 11} |
| adaptive_compressed | band3 | 20 | 7 | 0.35 | {"no_objective": 3, "objective_mismatch": 4, "runtime_error": 6, "unknown": 7} |
| adaptive_compressed | band4 | 32 | 8 | 0.25 | {"compile_failed": 3, "no_objective": 3, "objective_mismatch": 7, "runtime_error": 11, "unknown": 8} |
| spec_then_code | band1 | 20 | 14 | 0.7 | {"no_objective": 2, "objective_mismatch": 2, "runtime_error": 2, "unknown": 14} |
| spec_then_code | band2 | 20 | 9 | 0.45 | {"compile_failed": 1, "no_objective": 2, "objective_mismatch": 4, "runtime_error": 3, "timeout": 1, "unknown": 9} |
| spec_then_code | band3 | 20 | 10 | 0.5 | {"compile_failed": 2, "no_objective": 1, "objective_mismatch": 6, "runtime_error": 1, "unknown": 10} |
| spec_then_code | band4 | 32 | 11 | 0.344 | {"no_objective": 7, "objective_mismatch": 6, "runtime_error": 8, "unknown": 11} |
