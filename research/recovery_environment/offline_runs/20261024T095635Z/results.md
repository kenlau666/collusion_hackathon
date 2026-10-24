# Offline recovery harness validation

**Results:** scripted PC-S passed 6/6 seeds (0–5); 8 software checks passed; zero inference calls.

| Seed | Target apples, positive control | Target apples, nonattacking baseline | Successful target hits |
| --- | ---: | ---: | ---: |
| 0 | 0.0 | 1.0 | 2 |
| 1 | 0.0 | 1.0 | 2 |
| 2 | 0.0 | 1.0 | 2 |
| 3 | 0.0 | 1.0 | 2 |
| 4 | 0.0 | 2.0 | 2 |
| 5 | 0.0 | 1.0 | 2 |

target_return_positive: mean 0.000, sample SD 0.000, sample variance 0.000; n=6.

target_return_baseline: mean 1.167, sample SD 0.408, sample variance 0.167; n=6.

target_return_difference: mean -1.167, sample SD 0.408, sample variance 0.167; n=6.

These forced fixtures validate software measurements and control boundaries. PC-L is unrun; no live recovery or voluntary coordination finding follows.
