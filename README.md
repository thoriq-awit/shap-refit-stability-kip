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
| `results/v1_5/` | (filled after the run) Comparator analysis on the public UCI dataset "Predict Students' Dropout and Academic Success"; protocol v1.5 was frozen before any model was fitted on it |
| `results/v1_4/` | 100-permutation null (Table 2 of the manuscript), positive-control detection per level (Table 3), housing/utility variant |

## Public comparator data (v1.5)

The v1.5 comparator uses the UCI dataset "Predict Students' Dropout and Academic Success" (CC BY 4.0). Please cite M. V. Martins, D. Tolledo, J. Machado, L. M. T. Baptista, and V. Realinho (2021), doi: 10.1007/978-3-030-72657-7_16, and V. Realinho, J. Machado, L. Baptista, and M. V. Martins (2022), *Data* 7(11), 146. The file is not redistributed here; its SHA-256 is recorded in `freeze/A01_v1_5_FREEZE.json`.

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

## Results v1.5 (public UCI comparator)

`results/v1_5/` holds the aggregate outputs of the frozen v1.5 protocol on the public UCI dataset:
`hasil_A01_v15_main_sub` and `hasil_A01_v15_main_full` (R = 100), `hasil_A01_v15_null_s1`–`s5` (P = 100), and
`aturan_v15_sub` (frozen decision rules applied to the five subsamples). The 20-permutation null for the full dataset
(`hasil_A01_v15_null_full`) has not been run yet; the U-4 "above null" counts in `aturan_v15_sub` are therefore zero by
construction and mean "not run", not "not above null".
