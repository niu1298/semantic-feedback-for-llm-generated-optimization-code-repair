# Final Results

These tables are retained from the final report and the small release summaries in this directory. The protocols differ, so the sections should not be compared as a single pooled leaderboard. Semantic advisory is repair context, not formal verification.

## Experiment 1: Cross-Difficulty Semantic Advisory Study

Protocol: LogiOR, 92 problems, four difficulty bands, five-round repair horizon. This experiment asks when semantic advisory helps across generator capability, advisor capability, and problem difficulty.

| Setting | Solved |
| --- | ---: |
| `gpt-4o-mini` execution-only | 31/92 |
| `gpt-4o-mini` + `gpt-5-mini` advisory | 56/92 |
| `gpt-5-mini` execution-only | 53/92 |
| `gpt-5-mini` + `gpt-5-mini` advisory | 53/92 |
| `gpt-5-mini` + `kimi-k2.6` advisory | 54/92 |

Interpretation: advisory helped most when the advisor added capability beyond the generator. The clearest gain was for `gpt-4o-mini`, where advisory improved solved count from 31/92 to 56/92.

## Experiment 2: Final Four-Method Repair-System Comparison

Protocol: LogiOR, 92 problems, two-round repair horizon. This experiment compares ways to package semantic information under a tighter repair budget. The canonical configs are in `configs/final/`.

| Method | Solved | Pass rate |
| --- | ---: | ---: |
| Execution-only baseline | 25/92 | 0.272 |
| Direct semantic advisory | 46/92 | 0.500 |
| Adaptive compressed advisory | 37/92 | 0.402 |
| `spec_then_code` | 44/92 | 0.478 |

Interpretation: direct semantic advisory produced the strongest final comparison result. `spec_then_code` was close and solved a complementary subset. Adaptive compression shortened feedback but lost some repair signal.

## Traceability

- Final comparison details: `full92_candidate_comparison.md`.
- Band breakdown: `full92_candidate_band_breakdown.md`.
- Solve overlap: `full92_candidate_solve_overlap.md`.
- Cost tradeoff: `full92_candidate_cost_tradeoff.md`.
- Full writeup: `docs/final-report.pdf`.