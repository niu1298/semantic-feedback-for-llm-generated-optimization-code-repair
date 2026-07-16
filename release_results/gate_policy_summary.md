# Gate Policy Summary

| Policy | Total rounds | Would skip | Saving rate | Rejection accuracy | False rejection rate | False rejected solved code |
|---|---:|---:|---:|---:|---:|---:|
| no_gate | 88 | 0 | 0 | n/a | 0 | 0 |
| single_should_execute | 88 | 57 | 0.648 | 0.965 | 0.133 | 2 |
| confidence_threshold | 88 | 72 | 0.818 | 0.944 | 0.267 | 4 |
| reject_only_high_confidence | 88 | 45 | 0.511 | 0.956 | 0.133 | 2 |
| static_error_threshold | 88 | 7 | 0.08 | 1 | 0 | 0 |
| pessimistic_panel | 88 | 57 | 0.648 | 0.965 | 0.133 | 2 |
| optimistic_panel | 88 | 57 | 0.648 | 0.965 | 0.133 | 2 |

Interpretation:
- Hard gating remains unsafe unless false rejection is low and solved-code false rejections are acceptable.
- Prefer retrospective analysis until the gate policy is calibrated on a larger held-out set.
