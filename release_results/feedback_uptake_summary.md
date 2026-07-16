# Offline Feedback Uptake Summary

| Method | Items | Implementation rate | Resolution rate | New error rate | Gap improvement rate | Implemented+solved |
|---|---:|---:|---:|---:|---:|---:|
| adaptive_compressed | 301 | 0.967 | 0.525 | 0.352 | 0.183 | 52 |
| original_advisory | 283 | 0.986 | 0.572 | 0.431 | 0.219 | 40 |

## Uptake By Diagnosed Error Type

| Method | Error type | Items | Implementation rate | Resolution rate |
|---|---|---:|---:|---:|
| adaptive_compressed | api_issue | 19 | 0.895 | 0.526 |
| adaptive_compressed | compile_risk | 4 | 0.5 | 0.5 |
| adaptive_compressed | domain_issue | 19 | 1 | 0.526 |
| adaptive_compressed | missing_constraint | 33 | 0.97 | 0.576 |
| adaptive_compressed | other | 21 | 0.952 | 0.429 |
| adaptive_compressed | output_issue | 17 | 1 | 0.471 |
| adaptive_compressed | repair_instruction | 140 | 0.979 | 0.536 |
| adaptive_compressed | runtime_risk | 20 | 0.95 | 0.55 |
| adaptive_compressed | variable_issue | 11 | 1 | 0.455 |
| adaptive_compressed | wrong_objective | 17 | 1 | 0.529 |
| original_advisory | api_issue | 18 | 1 | 0.556 |
| original_advisory | compile_risk | 6 | 0.833 | 0.667 |
| original_advisory | domain_issue | 19 | 1 | 0.526 |
| original_advisory | missing_constraint | 24 | 1 | 0.542 |
| original_advisory | other | 21 | 1 | 0.714 |
| original_advisory | output_issue | 12 | 1 | 0.5 |
| original_advisory | repair_instruction | 139 | 0.986 | 0.576 |
| original_advisory | runtime_risk | 16 | 1 | 0.562 |
| original_advisory | variable_issue | 13 | 1 | 0.462 |
| original_advisory | wrong_objective | 15 | 0.933 | 0.6 |

Note: this is heuristic offline uptake. Treat it as directional evidence, not a substitute for human artifact review.
