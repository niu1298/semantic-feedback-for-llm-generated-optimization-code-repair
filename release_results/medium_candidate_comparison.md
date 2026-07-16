# Medium Candidate Comparison

| Method | Solved | Pass rate | Solver calls | LLM calls | Parse | Max prompt | Max feedback | Leaks | Containers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 6/24 | 0.25 | 43 | 43 | n/a | 10459 | 3185 | 0 | 0 |
| original_advisory | 8/24 | 0.333 | 43 | 86 | 1 | 16172 | 9243 | 0 | 0 |
| adaptive_compressed | 7/24 | 0.292 | 45 | 90 | 1 | 10985 | 3000 | 0 | 0 |
| spec_then_code | 8/24 | 0.333 | 40 | 80 | 0.975 | 15942 | 3780 | 0 | 0 |
| multi_advisor_disagreement | 6/24 | 0.25 | 45 | 135 | 1 | 10488 | 3000 | 0 | 0 |
