# Accuracy results

## Run on 2026-11-23 (15:12)

Model: openai/gpt-oss-120b. Sentences scored: 26. The test sentences pretend today is 2026-11-19.

| Measure | Correct | Target |
|---|---|---|
| Supplier | 96% (23/24) | 90% |
| Product | 96% (23/24) | 85% |
| Quantity | 71% (17/24) | 85% |
| Type | 88% (21/24) | - |
| When | 91% (10/11) | - |
| Edge questions | 2/3 | - |

Sentences with a problem: #2 (quantity), #7 (type), #8 (quantity), #9 (quantity), #12 (supplier, product, quantity, type), #13 (type), #14 (when), #19 (quantity), #27 (edge), #29 (quantity)

Skipped (query sentences, not built yet): #23, #24, #25, #26

