#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cek konsistensi v1.3 (hanya agregat).
 (1) rsweep prefiks R=100 harus sama dengan baris v1.2 (R=100) untuk varian/kohort/konfigurasi yang sama.
 (2) null mode 'observed' (Rn refit pertama) harus sama dengan rsweep prefiks R=Rn.
Pemakaian:
 python A01_v13_cek.py --v12 hasil_A01_v12_2023_A\\stability_summary.csv hasil_A01_v12_2023_B\\stability_summary.csv hasil_A01_v12_2024_A\\stability_summary.csv hasil_A01_v12_2024_B\\stability_summary.csv --rsweep hasil_A01_v13_rsweep_2023\\rsweep_summary.csv hasil_A01_v13_rsweep_2024\\rsweep_summary.csv
 python A01_v13_cek.py --null hasil_A01_v13_null_T32_2023\\null_runs.csv hasil_A01_v13_null_T32_2024\\null_runs.csv --rsweep ...
Selisih harus 0,0 (paket sama). Selisih kecil tetapi bukan nol biasanya karena versi paket berbeda."""
import argparse
import numpy as np
import pandas as pd

KEEP = ["global_spearman_mean", "global_top5_jaccard_mean", "local_spearman_median", "local_top3_jaccard_median", "local_sign_all_median"]
KEY = ["cohort", "variant", "model", "source"]
SEED0 = 20261018
ap = argparse.ArgumentParser()
ap.add_argument("--v12", nargs="*", default=[])
ap.add_argument("--null", nargs="*", default=[])
ap.add_argument("--rsweep", nargs="*", default=[])
a = ap.parse_args()
rsw = pd.concat([pd.read_csv(p) for p in a.rsweep]) if a.rsweep else pd.DataFrame()
if not rsw.empty:
    rsw = rsw[(rsw.kind == "prefix") & (rsw.split_seed == SEED0)]


def compare(x, y, tag):
    m = x.merge(y, on=KEY, suffixes=("_a", "_b"))
    print("%s: baris cocok = %d" % (tag, len(m)))
    if len(m) == 0:
        return
    d = pd.DataFrame({c: (m[c + "_a"] - m[c + "_b"]).abs() for c in KEEP})
    print(pd.DataFrame({"selisih_maks": d.max(), "selisih_rata": d.mean()}).round(10).to_string())


if a.v12 and not rsw.empty:
    old = pd.concat([pd.read_csv(p) for p in a.v12]); old = old[old.split_seed == SEED0]
    compare(old[KEY + KEEP], rsw[rsw.R_used == 100][KEY + KEEP], "rsweep prefiks 100 vs v1.2")
if a.null and not rsw.empty:
    nl = pd.concat([pd.read_csv(p) for p in a.null]); nl = nl[nl.kind == "observed"]
    for rn in sorted(nl.R_effective.unique()):
        compare(nl[nl.R_effective == rn][KEY + KEEP], rsw[rsw.R_used == rn][KEY + KEEP], "null observed (Rn=%d) vs rsweep prefiks %d" % (rn, rn))
