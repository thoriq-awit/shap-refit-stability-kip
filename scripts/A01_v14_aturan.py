#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
A01 protokol v1.4 - penerapan MEKANIS aturan keputusan PC-1..PC-5 dan NX-1 (aturan ada di A01_v1_4_PROTOKOL.md bagian 4).
Tidak ada pilihan manual: keluaran skrip ini adalah klasifikasi yang dilaporkan apa adanya.
Pemakaian:
  python A01_v14_aturan.py --posctl hasil_A01_v14_posctl_T32_2023\posctl_vs_null.csv hasil_A01_v14_posctl_T32_2024\posctl_vs_null.csv --out aturan_v14_posctl
  python A01_v14_aturan.py --null13 hasil_A01_v13_null_T32_2023\null_runs.csv hasil_A01_v13_null_T32_2024\null_runs.csv --nullx hasil_A01_v14_nullx_T32_2023\nullx_runs.csv hasil_A01_v14_nullx_T32_2024\nullx_runs.csv --out aturan_v14_nullx
"""
import argparse, json, math, os
import numpy as np
import pandas as pd

KEEP = ["global_spearman_mean", "global_top5_jaccard_mean", "local_spearman_median", "local_top3_jaccard_median", "local_sign_all_median"]
PC_METRICS = ["global_spearman_mean", "local_spearman_median"]   # metrik utama untuk PC-1 dan PC-2
FRAC_SENS = 0.80          # PC-1, PC-3: bagian sel yang harus "di atas null"
FRAC_MONO = 2 / 3         # PC-2: bagian sel yang harus monoton
MONO_TOL = 0.02           # PC-2: toleransi penurunan antar level
REC_MIN = 2 / 3           # PC-3: rata-rata pemulihan top-3 minimum (2 dari 3 grup benar)
NX_ALPHA = 0.05           # NX-1: p satu sisi
BH_Q = 0.10               # NX-1: ambang sekunder


def posctl_rules(paths, out):
    d = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    d["cell"] = d["cohort"].astype(str) + "|" + d["model"]
    levels = sorted(d["level_target"].unique())
    lmax, lmin = levels[-1], levels[0]
    res = {"levels": levels, "cells": sorted(d["cell"].unique())}
    ncell = d["cell"].nunique()
    # PC-1
    need1 = math.ceil(FRAC_SENS * ncell)
    pc1 = {}
    for m in PC_METRICS:
        g = d[(d.level_target == lmax) & (d.metric == m)]
        pc1[m] = dict(above=int(g.above_null.sum()), cells=int(len(g)))
    res["PC-1"] = dict(level=lmax, need=need1, detail=pc1, sensitive=bool(all(v["above"] >= need1 and v["cells"] == ncell for v in pc1.values())))
    # PC-2
    need2 = math.ceil(FRAC_MONO * ncell)
    pc2 = {}
    for m in PC_METRICS:
        ok = 0
        for c in d.cell.unique():
            g = d[(d.cell == c) & (d.metric == m)].sort_values("level_target")
            gap = (g.observed - g.null_mean).to_numpy()
            ok += int(len(gap) >= 2 and np.all(np.diff(gap) >= -MONO_TOL))
        pc2[m] = dict(monotone=ok, cells=int(ncell))
    res["PC-2"] = dict(need=need2, detail=pc2, dose_response=bool(all(v["monotone"] >= need2 for v in pc2.values())))
    # PC-3
    g = d[(d.level_target == lmax) & (d.metric == "rec_top3")]
    res["PC-3"] = dict(level=lmax, above=int(g.above_null.sum()), cells=int(len(g)), need=need1, mean_observed=float(g.observed.mean()),
                       recovers=bool(g.above_null.sum() >= need1 and g.observed.mean() >= REC_MIN))
    # PC-5 (deskriptif, tanpa lulus/gagal): deteksi per level x metrik
    rows = []
    for L in levels:
        for m in KEEP + ["auc_mean", "rec_top3"]:
            g = d[(d.level_target == L) & (d.metric == m)]
            rows.append(dict(level_target=L, metric=m, above_null=int(g.above_null.sum()), cells=int(len(g)),
                             observed_mean=float(g.observed.mean()), null_mean=float(g.null_mean.mean())))
    os.makedirs(out, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "pc5_deteksi_per_level.csv"), index=False)
    json.dump(res, open(os.path.join(out, "aturan_posctl.json"), "w"), indent=2, default=str)
    print(json.dumps(res, indent=2, default=str))


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.empty(n); prev = 1.0
    for i, k in enumerate(o[::-1]):
        rank = n - i
        prev = min(prev, p[k] * n / rank); q[k] = prev
    return q


def nullx_rules(null13, nullx, out):
    a = pd.concat([pd.read_csv(p) for p in null13], ignore_index=True)
    b = pd.concat([pd.read_csv(p) for p in nullx], ignore_index=True)
    obs = a[a.kind == "observed"]
    nul = pd.concat([a[a.kind == "permuted"], b[b.kind == "permuted"]], ignore_index=True)
    dup = nul.duplicated(["cohort", "variant", "model", "source", "perm"]).sum()
    assert dup == 0, "permutasi ganda antara v1.3 dan nullx: %d" % dup
    rows = []
    for (c, v, mo, so), g in nul.groupby(["cohort", "variant", "model", "source"]):
        o = obs[(obs.cohort == c) & (obs.variant == v) & (obs.model == mo) & (obs.source == so)].iloc[0]
        for m in KEEP + ["auc_mean"]:
            x = g[m].to_numpy(float); P = len(x)
            rows.append(dict(cohort=c, variant=v, model=mo, source=so, metric=m, P=P, observed=o[m], null_mean=x.mean(), null_p95=np.percentile(x, 95),
                             null_max=x.max(), p_upper=(1 + (x >= o[m]).sum()) / (P + 1), p_lower=(1 + (x <= o[m]).sum()) / (P + 1)))
    r = pd.DataFrame(rows)
    r["above_null_nx"] = r.p_upper <= NX_ALPHA
    r["below_null_nx"] = r.p_lower <= NX_ALPHA
    r["q_bh"] = np.nan
    core = r.metric.isin(KEEP)
    r.loc[core, "q_bh"] = bh(r.loc[core, "p_upper"].to_numpy())
    r["above_null_bh"] = r.q_bh <= BH_Q
    claim = (r[core].groupby(["variant", "model", "metric"]).agg(cohorts=("cohort", "nunique"), n_above=("above_null_nx", "sum")).reset_index())
    claim["claim_both_cohorts"] = (claim.cohorts == 2) & (claim.n_above == 2)
    os.makedirs(out, exist_ok=True)
    r.to_csv(os.path.join(out, "nx1_sel.csv"), index=False)
    claim.to_csv(os.path.join(out, "nx1_klaim_dua_kohort.csv"), index=False)
    summ = dict(P_total=int(r.P.min()), cells_core=int(core.sum()), above_nx=int(r[core].above_null_nx.sum()), above_bh=int(r[core].above_null_bh.sum()),
                claims_both_cohorts=int(claim.claim_both_cohorts.sum()))
    json.dump(summ, open(os.path.join(out, "aturan_nx.json"), "w"), indent=2)
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--posctl", nargs="*"); ap.add_argument("--null13", nargs="*"); ap.add_argument("--nullx", nargs="*")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.posctl: posctl_rules(a.posctl, a.out)
    if a.null13 and a.nullx: nullx_rules(a.null13, a.nullx, a.out)
