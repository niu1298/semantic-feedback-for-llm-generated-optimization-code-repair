# Full92 Candidate Comparison

| Method | Solved | Pass rate | Solver calls | LLM calls | Parse | Max prompt | Max feedback | Leaks | Containers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 25/92 | 0.272 | 165 | 165 | n/a | 12277 | 3687 | 0 | 0 |
| original_advisory | 46/92 | 0.5 | 164 | 328 | 0.988 | 17952 | 9915 | 0 | 0 |
| adaptive_compressed | 37/92 | 0.402 | 165 | 330 | 0.988 | 10667 | 3000 | 0 | 0 |
| spec_then_code | 44/92 | 0.478 | 154 | 308 | 0.981 | 15791 | 3803 | 0 | 0 |
