# Full92 Cost Tradeoff

| method | solved_count | total_llm_calls | solver_calls_per_solved | semantic_or_spec_calls_per_solved | max_prompt_chars | mean_prompt_chars | max_feedback_chars | mean_feedback_chars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 25 | 165 | 6.6 | 0 | 12277 | 4511.43 | 3687 | 1255.606 |
| original_advisory | 46 | 328 | 3.565 | 3.565 | 17952 | 6472.439 | 9915 | 3222.433 |
| adaptive_compressed | 37 | 330 | 4.459 | 4.459 | 10667 | 4452.97 | 3000 | 1266.594 |
| spec_then_code | 44 | 308 | 3.5 | 3.5 | 15791 | 6310.221 | 3803 | 1146.273 |
| adaptive_compressed_vs_original_delta | -9 | 2 | n/a | n/a | -7285 | -2019.469 | -6915 | -1955.839 |
| spec_then_code_vs_original_delta | -2 | -20 | n/a | n/a | -2161 | -162.218 | -6112 | -2076.16 |
