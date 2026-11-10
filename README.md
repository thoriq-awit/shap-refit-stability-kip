# SHAP refit stability against a label-permutation null (KIP Kuliah selection)

Analysis scripts, frozen protocol files, and aggregate results for the manuscript
"Measuring SHAP explanation stability against a label-permutation null in scholarship selection".

## What is here

| Folder | Content |
|---|---|
| `scripts/` | Frozen analysis scripts: stability protocol v1.2 and v1.3, positive control v1.4, decision rules v1.4, and reproduction checks |
| `freeze/` | Freeze records with the SHA-256 hash of each script and rule set, written before each stage was run |
| `protocol/` | Protocol documents v1.3 and v1.4 and the run guides (in Indonesian) |
| `results/v1_2/` | Stability summary for all feature variants, bootstrap and seed schemes, R = 100 |
| `results/v1_3/` | Split-seed study, sweep over R, 20-permutation null classification, variant ladder against split-seed range |
| `results/v1_4/` | 100-permutation null (Table 2 of the manuscript), positive-control detection per level (Table 3), housing/utility variant |

## What is not here

The applicant records of the KIP Kuliah selection at Universitas Adzkia contain personal data and are not shared.
Only aggregate outputs are included; no file in this repository contains one row per applicant.
The 2025 cohort is a reserved holdout and was not used.

## Verifying the freeze

```
sha256sum scripts/*.py
```

The hashes should match the `script_sha256` values in `freeze/*.json`.

## Software

Python with scikit-learn 1.9.1, xgboost 3.4.1, shap 0.54.1, numpy, pandas, scipy.

## Status of the protocol

Stages after the first were specified after earlier results had been seen and are post hoc; see the protocol documents.

## License

Code: MIT. Aggregate result files: CC BY 4.0.
