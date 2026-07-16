# Convergence Summary

This analysis treats convergence as bounded-horizon repair progress, not asymptotic convergence.

| Method | Solved | Pass rate | Avg first valid | Median first valid | Solver calls/solved | LLM calls/solved | Repair productivity | Repeated failure rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 25/92 | 0.272 | 0.24 | 0 | 6.6 | 6.6 | 0.082 | 0.589 |
| original_advisory | 46/92 | 0.5 | 0.565 | 1 | 3.565 | 7.13 | 0.361 | 0.292 |
| adaptive_compressed | 37/92 | 0.402 | 0.486 | 0 | 4.459 | 8.919 | 0.247 | 0.315 |
| spec_then_code | 44/92 | 0.478 | 0.318 | 0 | 3.5 | 7 | 0.226 | 0.645 |

## Cumulative Solved By Round

| method | round | cumulative_solved | selected_problem_count | cumulative_pass_rate |
| --- | --- | --- | --- | --- |
| baseline | 0 | 19 | 92 | 0.207 |
| baseline | 1 | 25 | 92 | 0.272 |
| original_advisory | 0 | 20 | 92 | 0.217 |
| original_advisory | 1 | 46 | 92 | 0.5 |
| adaptive_compressed | 0 | 19 | 92 | 0.207 |
| adaptive_compressed | 1 | 37 | 92 | 0.402 |
| spec_then_code | 0 | 30 | 92 | 0.326 |
| spec_then_code | 1 | 44 | 92 | 0.478 |

## Error Transitions Toward Solved

| method | solved_from_compile_failed | solved_from_runtime_error | solved_from_objective_mismatch | solved_from_no_objective | repeated_failure_count |
| --- | --- | --- | --- | --- | --- |
| adaptive_compressed | n/a | 8 | 10 | n/a | 23 |
| baseline | n/a | 3 | 2 | 1 | 43 |
| original_advisory | n/a | 17 | 8 | 1 | 21 |
| spec_then_code | n/a | 12 | 2 | n/a | 40 |

## Objective Gap Movement

| method | objective_gap_pairs_count | objective_gap_improved_count | objective_gap_worsened_count | objective_gap_unchanged_count | mean_initial_objective_gap | mean_final_objective_gap |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 22 | 5 | 3 | 14 | 136074.446 | 83258.587 |
| original_advisory | 16 | 12 | 3 | 1 | 5517641.257 | 5522239.286 |
| adaptive_compressed | 18 | 15 | 2 | 1 | 264017.922 | 197724.388 |
| spec_then_code | 18 | 2 | 2 | 14 | 10295.722 | 10291.369 |

## Figure Specs

### Figure A: Cumulative Solved By Round

- x-axis: repair round.
- y-axis: cumulative solved count.
- Data: baseline r0=19; baseline r1=25; original_advisory r0=20; original_advisory r1=46; adaptive_compressed r0=19; adaptive_compressed r1=37; spec_then_code r0=30; spec_then_code r1=44.
- Caption: Bounded-horizon cumulative solved count by repair round. Higher curves indicate earlier valid solutions within the fixed repair budget.

### Figure B: Calls To First Valid

- Bar chart of mean solver calls and mean total LLM calls to first valid among solved problems.
- Data: baseline: solver 1.24, LLM 1.24, original_advisory: solver 1.565, LLM 3.13, adaptive_compressed: solver 1.486, LLM 2.973, spec_then_code: solver 1.318, LLM 2.636.
- Caption: Calls needed to reach the first valid solution among solved problems. This measures repair speed conditional on eventual success.

### Figure C: Error Transition To Solved

- Stacked bars for compile_failed->solved, runtime_error->solved, objective_mismatch->solved, no_objective->solved, and repeated failures.
- Data: adaptive_compressed: compile 0, runtime 8, objective 10, no_objective 0, repeated 23; baseline: compile 0, runtime 3, objective 2, no_objective 1, repeated 43; original_advisory: compile 0, runtime 17, objective 8, no_objective 1, repeated 21; spec_then_code: compile 0, runtime 12, objective 2, no_objective 0, repeated 40.
- Caption: Error transitions within the bounded repair horizon. Semantic methods are useful when they turn concrete failure modes into solved states rather than repeated failures.

### Figure D: Convergence Efficiency

- Grouped bars for solved / LLM calls and solved / solver calls.
- Data: baseline: solved/LLM 0.152, solved/solver 0.152, original_advisory: solved/LLM 0.14, solved/solver 0.28, adaptive_compressed: solved/LLM 0.112, solved/solver 0.224, spec_then_code: solved/LLM 0.143, solved/solver 0.286.
- Caption: Repair productivity normalized by LLM and solver calls. This distinguishes higher final coverage from faster or cheaper convergence.

## Report-Ready Convergence Interpretation

- Original semantic advisory improves final bounded-horizon coverage over execution-only repair. Because average first-valid rounds are close on this sample, the safer claim is better repair coverage, not decisively faster convergence.
- Adaptive compression preserves a similar convergence profile while substantially improving prompt/feedback hygiene. Frame this as a prompt-efficiency tradeoff rather than a strict speedup.
- Spec_then_code changes the convergence profile by solving many cases at round 0 through structured planning. It is complementary to original advisory rather than strictly dominant.
- Safe final-report wording: the bounded-horizon data supports a solve-rate and repair-productivity improvement from semantic structure, but only weak evidence of universally faster convergence. Stronger convergence-speed claims require full92 or additional repeated seeds.
