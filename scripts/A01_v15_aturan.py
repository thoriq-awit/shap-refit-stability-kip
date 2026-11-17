#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A01 v1.5 - penerapan ATURAN KEPUTUSAN BEKU pada keluaran UCI (A01_uci_v1_5.py).
Aturan ditulis dan dibekukan 2026-11-17 SEBELUM model apa pun dilatih pada data UCI. Ambang = ambang kerja penulis,
bukan standar literatur. Skrip ini hanya membaca berkas agregat dan tidak melatih model.

Pemakaian:
  python A01_v15_aturan.py --main_sub hasil_A01_v15_main_sub --main_full hasil_A01_v15_main_full ^
         --null hasil_A01_v15_null_s1,hasil_A01_v15_null_s2,hasil_A01_v15_null_s3,hasil_A01_v15_null_s4,hasil_A01_v15_null_s5,hasil_A01_v15_null_full ^
         --out aturan_v15

Aturan:
  U-1 SINYAL        sel = subsampel x model (bootstrap) = 15 sel. "Sinyal kuat" bila AUC teramati di atas null (p <= 0,05) pada
                    >= 12 dari 15 sel DAN median AUC teramati lintas 15 sel >= 0,70 (level tengah kontrol positif v1.4).
  U-2 PEMBEDA       "Protokol mendeteksi stabilitas di atas null pada data bersinyal kuat" bila Spearman global (GS) di atas null
                    pada >= 12/15 sel DAN Spearman lokal (LS) di atas null pada >= 12/15 sel. Hasil apa pun dilaporkan.
  U-3 DAYA METRIK   jumlah sel di atas null untuk J5, J3, SC (deskriptif; tanpa ambang).
  U-4 UKURAN SAMPEL UCI_full (P = 20): sel di atas null bila teramati > maksimum 20 nilai null. Deskriptif: selisih GS dan LS
                    UCI_full minus rata-rata lima subsampel (R = 100).
  U-5 SUMBER VARIASI deskriptif: GS dan LS seed vs bootstrap per subsampel (R = 100).
  Sekunder          Benjamini-Hochberg q <= 0,10 atas 75 sel (5 metrik x 15 sel subsampel).
"""
import argparse, json, os
import numpy as np
import pandas as pd

ALPHA, MIN_CELLS, AUC_MED, BH_Q = 0.05, 12, 0.70, 0.10
MET = {"global_spearman_mean": "GS", "global_top5_jaccard_mean": "J5", "local_spearman_median": "LS",
       "local_top3_jaccard_median": "J3", "local_sign_all_median": "SC", "auc_mean": "AUC"}
SUBS = ["UCI_s1", "UCI_s2", "UCI_s3", "UCI_s4", "UCI_s5"]


def bh(p, q):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    thr = q * (np.arange(1, n + 1) / n)
    ok = p[o] <= thr
    k = np.max(np.nonzero(ok)[0]) + 1 if ok.any() else 0
    rej = np.zeros(n, bool); rej[o[:k]] = True
    return rej


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main_sub", required=True); ap.add_argument("--main_full", required=True)
    ap.add_argument("--null", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    nv = pd.concat([pd.read_csv(os.path.join(p.strip(), "null_vs_observed.csv")) for p in a.null.split(",") if p.strip()])
    nv = nv[nv.metric.isin(MET)].copy()
    nv["m"] = nv.metric.map(MET)
    sub = nv[nv.variant.isin(SUBS)].copy()
    full = nv[nv.variant == "UCI_full"].copy()
    sub["above"] = sub.p_upper <= ALPHA
    full["above"] = full.observed > full.null_max
    res = {"frozen": "2026-11-17, sebelum model dilatih pada data UCI", "alpha": ALPHA, "min_cells": MIN_CELLS,
           "auc_median_min": AUC_MED, "n_cells_sub": int(sub[sub.m == "GS"].shape[0])}
    cnt = lambda m: int(sub[(sub.m == m) & sub.above].shape[0])
    auc = sub[sub.m == "AUC"]
    res["U1"] = dict(auc_above_null=cnt("AUC"), auc_observed_median=float(auc.observed.median()),
                     auc_observed_min=float(auc.observed.min()), auc_observed_max=float(auc.observed.max()),
                     auc_null_mean_range=[float(auc.null_mean.min()), float(auc.null_mean.max())])
    res["U1"]["signal_strong"] = bool(res["U1"]["auc_above_null"] >= MIN_CELLS and res["U1"]["auc_observed_median"] >= AUC_MED)
    res["U2"] = dict(GS_above=cnt("GS"), LS_above=cnt("LS"))
    res["U2"]["protocol_detects"] = bool(res["U2"]["GS_above"] >= MIN_CELLS and res["U2"]["LS_above"] >= MIN_CELLS)
    res["U3"] = {m: cnt(m) for m in ("J5", "J3", "SC")}
    # sekunder: BH atas 75 sel (5 metrik stabilitas)
    st = sub[sub.m != "AUC"].copy()
    st["bh_reject"] = bh(st.p_upper.values, BH_Q)
    res["BH_secondary"] = {m: int(st[(st.m == m) & st.bh_reject].shape[0]) for m in ("GS", "J5", "LS", "J3", "SC")}
    res["U4_full_above_null"] = {m: int(full[(full.m == m) & full.above].shape[0]) for m in ("GS", "J5", "LS", "J3", "SC", "AUC")}
    res["U4_full_P"] = int(full.P.max()) if len(full) else 0
    # deskriptif dari analisis utama R = 100
    ms = pd.read_csv(os.path.join(a.main_sub, "stability_summary.csv"))
    mf = pd.read_csv(os.path.join(a.main_full, "stability_summary.csv"))
    keep = ["variant", "model", "source", "n", "n_eval", "auc_mean", "global_spearman_mean", "global_top5_jaccard_mean",
            "local_spearman_median", "local_top3_jaccard_median", "local_sign_all_median",
            "near_local_spearman_median", "rest_local_spearman_median"]
    tab = pd.concat([ms, mf])[keep]
    tab.to_csv(os.path.join(a.out, "v15_main_R100.csv"), index=False)
    agg = ms.groupby(["model", "source"])[["auc_mean", "global_spearman_mean", "local_spearman_median"]].agg(["mean", "min", "max"])
    agg.to_csv(os.path.join(a.out, "v15_main_sub_agg.csv"))
    d4 = []
    for (mo, so), g in ms.groupby(["model", "source"]):
        f = mf[(mf.model == mo) & (mf.source == so)]
        if len(f):
            d4.append(dict(model=mo, source=so,
                           GS_full_minus_sub=float(f.global_spearman_mean.iloc[0] - g.global_spearman_mean.mean()),
                           LS_full_minus_sub=float(f.local_spearman_median.iloc[0] - g.local_spearman_median.mean())))
    res["U4_full_minus_sub"] = d4
    res["U5_seed_vs_boot"] = [dict(model=mo, source=so, GS_mean=float(g.global_spearman_mean.mean()),
                                   LS_mean=float(g.local_spearman_median.mean()))
                              for (mo, so), g in ms.groupby(["model", "source"])]
    pd.concat([sub, full]).to_csv(os.path.join(a.out, "v15_cells.csv"), index=False)
    json.dump(res, open(os.path.join(a.out, "aturan_v15.json"), "w"), indent=2)
    print(json.dumps({k: res[k] for k in ("U1", "U2", "U3", "BH_secondary", "U4_full_above_null")}, indent=2))
    print("Selesai. Keluaran di", a.out)


if __name__ == "__main__":
    main()
