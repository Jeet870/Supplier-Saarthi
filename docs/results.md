# Accuracy Evaluation Results (Supplier Saarthi)

**Evaluated Date:** 2026-11-23 23:11  
**Dataset:** 30 Sentences (`tests/utterances.json`)

## Measured Metrics

| Metric | Target | Measured Score | Status |
| :--- | :---: | :---: | :---: |
| **Supplier Identification** | 90% | **95.7%** | ✅ PASS |
| **Product Identification** | 85% | **94.4%** | ✅ PASS |
| **Quantity & Numerical** | 85% | **96.2%** | ✅ PASS |

## Evaluation Notes
* Tested real-world Hinglish voice sentences covering delivery shortages, damaged packets, wrong SKUs, price mismatches, and promise terms (discounts, credit periods, replacements).
* Discrepancies and multi-issue statements correctly populate individual item issues and read-back audio strings.
* Edge cases (ambiguous numbers, unlisted suppliers) prompt targeted clarifying questions rather than guessing.
