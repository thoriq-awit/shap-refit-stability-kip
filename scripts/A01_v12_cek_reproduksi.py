#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cek reproduksi v1.2 terhadap keluaran v1.0/v1.1: untuk varian lama (primary, B_tanpa_blok, C_tanpa_kabkota) pada benih
pembagian v1.0, metrik lama harus sama (selisih ~0 bila versi paket sama; selisih kecil bila versi shap/xgboost berbeda).
Pemakaian: python A01_v12_cek_reproduksi.py --lama hasil_A01\\stability_summary.csv --baru hasil_A01_v12_2023\\stability_summary.csv hasil_A01_v12_2024\\stability_summary.csv
Keluaran hanya agregat."""
import argparse
import pandas as pd

KEY = ["cohort", "variant", "model", "source"]
COLS = ["global_spearman_mean", "global_top5_jaccard_mean", "local_spearman_median", "local_top3_jaccard_median", "auc_mean", "prauc_mean"]

ap = argparse.ArgumentParser()
ap.add_argument("--lama", required=True)
ap.add_argument("--baru", nargs="+", required=True)
a = ap.parse_args()
old = pd.read_csv(a.lama)
new = pd.concat([pd.read_csv(p) for p in a.baru])
# v1.0 (hasil_A01) belum punya kolom split_seed: semua barisnya memakai benih pembagian utama (20261018).
SEED0 = 20261018
if "split_seed" in old.columns:
    old = old[old["split_seed"] == SEED0]
new = new[new["split_seed"] == SEED0]
m = old.merge(new, on=KEY, suffixes=("_lama", "_baru"))
print("baris yang cocok:", len(m), "dari", len(old), "baris lama; varian:", sorted(m["variant"].unique()), "kohort:", sorted(m["cohort"].unique()))
rows = []
for c in COLS:
    if c + "_lama" in m and c + "_baru" in m:
        d = (m[c + "_lama"] - m[c + "_baru"]).abs()
        rows.append((c, d.max(), d.mean()))
print(pd.DataFrame(rows, columns=["metrik", "selisih_maks", "selisih_rata"]).to_string(index=False))
print("Catatan: selisih ~0 = reproduksi persis. Selisih kecil tetapi tidak nol biasanya karena versi paket (shap/xgboost) berbeda.")
