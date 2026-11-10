#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Artikel 01 - Stabilitas penjelasan SHAP pada keputusan beasiswa KIP Kuliah (Universitas Adzkia)
PROTOKOL v1.3 = v1.2 + AMANDEMEN pasca-hasil v1.2 (disusun 2026-10-21, SETELAH peneliti melihat hasil v1.2).
Amandemen v1.3 (tidak mengubah aturan fitur, kunci acak, metrik, atau keluaran mode v1.2; hanya MENAMBAH mode dan opsi):
  1. --null_P P [--null_R Rn]: pembanding label-teracak (permutation null). Label data LATIH diacak (kelas tetap seimbang),
     baris latih/evaluasi sama dengan analisis utama; Rn refit bootstrap per permutasi. Bandingkan dengan nilai teramati
     pada Rn refit pertama (kunci acak identik dengan v1.2). Keluaran: null_runs.csv, null_vs_observed.csv.
  2. --rsweep: metrik pada prefiks R (25, 50, 100, 200) dan blok terpisah (50) dalam satu run R=200; keluaran rsweep_summary.csv.
     Refit ke-1..100 identik dengan v1.2 (kunci acak tidak bergantung pada R), sehingga bisa diverifikasi.
  3. --configs "LR/boot,RF/boot,..." membatasi konfigurasi model (indeks konfigurasi asli tetap dipakai pada kunci acak).
  4. Kolom 'seconds' (waktu per konfigurasi) ditambahkan pada keluaran.
PROTOKOL v1.2 = v1.1 + AMANDEMEN pasca-hasil (disusun 2026-10-19, SETELAH peneliti melihat hasil v1.0).
v1.1 = v1.0 (doc 15) + varian C (tanpa Kab/Kota Sekolah) dan studi benih pembagian evaluasi (pasca-hasil).
Amandemen v1.2 (semuanya pasca-hasil; laporkan sebagai analisis tambahan, bukan analisis awal):
  1. Tangga varian bersarang yang diselaraskan dengan Tabel 3.2 proposal disertasi:
       T32 (9 grup, utama)  <  E_blok_rumah (18)  <  C_tanpa_kabkota (22)  <  primary (23, = S1 pada canvas);
     B_tanpa_blok (12) dipertahankan sebagai varian warisan v1.0. Varian lama TIDAK diubah (aturan fitur dan urutan kolom identik).
  2. Local sign consistency (Tabel 3.5 proposal): SC_i = proporsi fitur (grup) dengan arah kontribusi sama antar pasangan refit.
     Dua perlakuan nol: "all" (kedua nol dihitung sepakat) dan "nz" (hanya fitur yang bukan nol pada keduanya).
  3. Strata dekat batas keputusan: 20% instans evaluasi dengan |rata-rata probabilitas refit - ambang| terkecil.
     Ambang = nilai yang memaksimalkan F1 pada rata-rata probabilitas refit di himpunan evaluasi kohort itu (proksi pengembangan
     bagi ambang terkunci disertasi; dipakai hanya untuk menentukan strata, bukan untuk klaim kinerja).
  4. Baseline peluang analitik untuk Jaccard top-k (hipergeometrik) per jumlah fitur.

PENTING
- Jalankan di komputer peneliti. Data mentah mengandung identitas langsung; JANGAN diunggah.
- Kode memakai DAFTAR PUTIH kolom (fitur dipilih eksplisit). Kolom identitas tidak pernah dibawa ke
  matriks fitur. Keluaran hanya agregat (tanpa baris per orang).
- Data 2025 (holdout) tidak dibaca oleh skrip ini.
- Hasil dari --selftest (data sintetis) BUKAN temuan penelitian dan tidak boleh masuk Results.

Pemasangan:  pip install numpy pandas scipy scikit-learn openpyxl shap xgboost
Contoh:      python A01_shap_stability_v1_3.py --data2023 "...20231204.xlsx" --data2024 "...20241022.xlsx" --out hasil_A01
Uji logika:  python A01_shap_stability_v1_3.py --selftest --out selftest_A01 --R 8
"""
import argparse, hashlib, json, os, platform, sys, time, warnings
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from math import comb
from sklearn.metrics import average_precision_score, balanced_accuracy_score, precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ----------------------------- KONFIGURASI BEKU (protokol v1.0) -----------------------------
SEED = 20261018          # benih utama
TEST_FRAC = 0.30         # porsi himpunan evaluasi-penjelasan (tetap untuk semua refit)
R_DEFAULT = 100          # jumlah refit per konfigurasi
TOPK_GLOBAL = 5          # top-k untuk Jaccard global
TOPK_LOCAL = 3           # top-k untuk Jaccard lokal
RARE_MIN = 15            # kategori dengan < RARE_MIN pendaftar (dalam kohort) -> "Lainnya" (tanpa label)
MISSING_LABEL = "Tidak diisi"
NEAR_FRAC = 0.20         # [v1.2] porsi instans terdekat ke ambang = strata "dekat batas keputusan"
SIGN_EPS = 1e-10         # [v1.2] |phi| < SIGN_EPS dianggap nol pada local sign consistency
RSWEEP_PREFIX = (25, 50, 100, 200)   # [v1.3] prefiks R untuk --rsweep
RSWEEP_BLOCK = 50                    # [v1.3] ukuran blok terpisah untuk --rsweep
NULL_TAG = 7001                      # [v1.3] penanda kunci acak untuk refit pembanding null
PERM_TAG = 7002                      # [v1.3] penanda kunci acak untuk permutasi label
KEEP = ["global_spearman_mean", "global_top5_jaccard_mean", "local_spearman_median", "local_top3_jaccard_median",
        "local_sign_all_median"]     # [v1.3] metrik inti untuk null dan rsweep

LABEL_COL = "Diterima"
# Fitur kategorikal (kolom mentah -> nama fitur)
CAT_PLAIN = {
    "Status DTKS": "DTKS", "Status P3KE": "P3KE",
    "Pekerjaan Ayah": "PekerjaanAyah", "Pekerjaan Ibu": "PekerjaanIbu",
    "Status Ayah": "StatusAyah", "Status Ibu": "StatusIbu",
}
CAT_RARE = {"Pilihan Prodi 1": "Prodi1", "Kab/Kota Sekolah": "KabKotaSekolah"}
FLAG_FROM = {"No. KIP": "KIP_terisi", "No. KKS": "KKS_terisi", "Prestasi Siswa": "Prestasi_terisi"}
BLOCK_CAT = {  # blok struktural (hanya terisi sebagian pendaftar)
    "Penghasilan Ayah": "PenghasilanAyah", "Penghasilan Ibu": "PenghasilanIbu",
    "Kepemilikan Rumah": "KepemilikanRumah", "Sumber Listrik": "SumberListrik",
    "Luas Tanah": "LuasTanah", "Luas Bangunan": "LuasBangunan",
    "Sumber Air": "SumberAir", "MCK": "MCK",
}
NUM_COLS = {"Jumlah Tanggungan": "JumlahTanggungan"}
BLOCK_NUM = {"Jarak Pusat Kota (KM)": "JarakPusatKota"}
BLOCK_FLAGS = {"Penghasilan Ayah": "Blok_penghasilan_terisi", "Kepemilikan Rumah": "Blok_rumah_terisi"}
# Sengaja TIDAK dipakai: semua identitas, KAP (arti belum jelas), Jenis Kelamin (atribut sensitif; ranah artikel
# fairness), Tanggal Daftar (risiko proses seleksi bergulir), Provinsi Sekolah, Tahun Perolehan, Pilihan Prodi 2,
# Asal Sekolah (kuasi-identitas, kardinalitas tinggi).
VARIANTS = ["T32", "E_blok_rumah", "C_tanpa_kabkota", "primary", "B_tanpa_blok"]
VARIANT_CODE = {"primary": 7, "B_tanpa_blok": 8, "C_tanpa_kabkota": 9, "T32": 10, "E_blok_rumah": 11}
# Spesifikasi fitur per varian. Urutan kolom mengikuti urutan kode v1.1 (agar varian lama identik dengan v1.0/v1.1).
INCOME_BLOCK = ("Penghasilan Ayah", "Penghasilan Ibu")  # tercantum di Tabel 3.2 (blok struktural)
VSPEC = {
    "primary":         dict(rare=("Prodi1", "KabKotaSekolah"), flags=True,  block_cat="all",    block_num=True,  block_flags=True),
    "B_tanpa_blok":    dict(rare=("Prodi1", "KabKotaSekolah"), flags=True,  block_cat="none",   block_num=False, block_flags=False),
    "C_tanpa_kabkota": dict(rare=("Prodi1",),                  flags=True,  block_cat="all",    block_num=True,  block_flags=True),
    "E_blok_rumah":    dict(rare=(),                           flags=False, block_cat="all",    block_num=True,  block_flags=True),
    "T32":             dict(rare=(),                           flags=False, block_cat="income", block_num=False, block_flags=False),
}


def is_missing(s):
    s = s.astype("string").str.strip()
    return s.isna() | s.isin(["-", "", "nan", "<NA>"])


# ----------------------------- DATA -----------------------------
def read_raw(path):
    d = pd.read_excel(path, header=None, dtype=str)
    h = [i for i in range(min(6, len(d))) if d.iloc[i].astype(str).str.contains("No. Pendaftaran", regex=False).any()]
    if not h:
        raise ValueError("Baris header ('No. Pendaftaran') tidak ditemukan di " + path)
    h = h[0]
    cols = d.iloc[h].astype(str).str.strip().tolist()
    d = d.iloc[h + 1:].copy()
    d.columns = cols
    d = d.loc[:, [c for c in d.columns if c not in ("#", "", "nan")]].reset_index(drop=True)
    d = d.rename(columns={c: LABEL_COL for c in d.columns if c.lower().startswith("diterima")})
    return d


def build_features(raw, variant):
    """Matriks fitur dari DAFTAR PUTIH kolom. Mengembalikan (X DataFrame, y array, group list)."""
    y = (raw[LABEL_COL].astype(str).str.strip().str.lower() == "diterima").astype(int).values
    feats, groups = {}, {}
    sp = VSPEC[variant]

    def cat(col, name, rare=False, block=False):
        s = raw[col].astype("string").str.strip()
        s = s.mask(is_missing(s), MISSING_LABEL)
        if rare:
            vc = s.value_counts()
            small = vc[vc < RARE_MIN].index
            s = s.mask(s.isin(small) & (s != MISSING_LABEL), "Lainnya")
        dm = pd.get_dummies(s, prefix=name, prefix_sep="=", dtype=float)
        for c in dm.columns:
            feats[c] = dm[c].values
            groups[c] = name

    for col, name in CAT_PLAIN.items():
        cat(col, name)
    for col, name in CAT_RARE.items():
        if name not in sp["rare"]:
            continue
        cat(col, name, rare=True)
    if sp["flags"]:
        for col, name in FLAG_FROM.items():
            feats[name] = (~is_missing(raw[col])).astype(float).values
            groups[name] = name
    for col, name in NUM_COLS.items():
        v = pd.to_numeric(raw[col].astype("string").str.extract(r"(\d+)")[0], errors="coerce")
        v = v.fillna(v.median())
        feats[name] = ((v - v.mean()) / (v.std() + 1e-12)).values.astype(float)
        groups[name] = name
    if sp["block_cat"] != "none":
        for col, name in BLOCK_CAT.items():
            if sp["block_cat"] == "income" and col not in INCOME_BLOCK:
                continue
            cat(col, name, block=True)
    if sp["block_num"]:
        for col, name in BLOCK_NUM.items():
            v = pd.to_numeric(raw[col].astype("string").str.replace(",", ".", regex=False), errors="coerce")
            v = v.fillna(0.0)
            feats[name] = ((v - v.mean()) / (v.std() + 1e-12)).values.astype(float)
            groups[name] = name
    if sp["block_flags"]:
        for col, name in BLOCK_FLAGS.items():
            feats[name] = (~is_missing(raw[col])).astype(float).values
            groups[name] = name
    X = pd.DataFrame(feats)
    # buang kolom konstan (tanpa informasi)
    keep = [c for c in X.columns if X[c].nunique() > 1]
    X = X[keep]
    grp = [groups[c] for c in X.columns]
    return X, y, grp


# ----------------------------- MODEL & SHAP -----------------------------
def make_model(name, seed, n_jobs, substitute_xgb=False, small=False):
    if name == "LR":
        return LogisticRegression(C=1.0, max_iter=2000)
    if name == "RF":
        return RandomForestClassifier(n_estimators=20 if small else 300, min_samples_leaf=3, max_features="sqrt",
                                      n_jobs=n_jobs, random_state=seed)
    if name == "XGB":
        if substitute_xgb:  # HANYA untuk --selftest tanpa xgboost
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(n_estimators=60, max_depth=3, learning_rate=0.1,
                                              subsample=0.8, max_features=0.8, random_state=seed)
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.1, subsample=0.8,
                             colsample_bytree=0.8, eval_metric="logloss", random_state=seed,
                             n_jobs=n_jobs, verbosity=0)
    raise ValueError(name)


# --- TreeSHAP path-dependent (Lundberg dkk. 2020, Alg. 2); HANYA fallback uji bila paket shap tidak ada ---
def _extend(path, pz, po, pi):
    l = len(path)
    path = [p[:] for p in path]
    path.append([pi, pz, po, 1.0 if l == 0 else 0.0])
    for i in range(l - 1, -1, -1):
        path[i + 1][3] += po * path[i][3] * (i + 1) / (l + 1)
        path[i][3] = pz * path[i][3] * (l - i) / (l + 1)
    return path


def _unwind(path, idx):
    ud = len(path) - 1
    po, pz = path[idx][2], path[idx][1]
    nxt = path[ud][3]
    path = [p[:] for p in path]
    for i in range(ud - 1, -1, -1):
        if po != 0:
            tmp = path[i][3]
            path[i][3] = nxt * (ud + 1) / ((i + 1) * po)
            nxt = tmp - path[i][3] * pz * (ud - i) / (ud + 1)
        else:
            path[i][3] = path[i][3] * (ud + 1) / (pz * (ud - i))
    for i in range(idx, ud):
        path[i][0], path[i][1], path[i][2] = path[i + 1][0], path[i + 1][1], path[i + 1][2]
    return path[:-1]


def _unwound_sum(path, idx):
    ud = len(path) - 1
    po, pz = path[idx][2], path[idx][1]
    nxt = path[ud][3]
    total = 0.0
    for i in range(ud - 1, -1, -1):
        if po != 0:
            tmp = nxt * (ud + 1) / ((i + 1) * po)
            total += tmp
            nxt = path[i][3] - tmp * pz * ((ud - i) / (ud + 1))
        elif pz != 0:
            total += (path[i][3] / pz) / ((ud - i) / (ud + 1))
    return total


def tree_shap_one(tree, leaf_value, x, phi):
    """Menambah kontribusi satu pohon sklearn (tree_) untuk satu baris x ke vektor phi."""
    L, R_, F, T, W = tree.children_left, tree.children_right, tree.feature, tree.threshold, tree.weighted_n_node_samples

    def rec(node, path, pz, po, pi):
        path = _extend(path, pz, po, pi)
        if L[node] < 0:
            for i in range(1, len(path)):
                w = _unwound_sum(path, i)
                phi[path[i][0]] += w * (path[i][2] - path[i][1]) * leaf_value[node]
            return
        f = F[node]
        hot, cold = (L[node], R_[node]) if x[f] <= T[node] else (R_[node], L[node])
        iz, io = 1.0, 1.0
        k = next((j for j in range(len(path)) if path[j][0] == f), None)
        if k is not None:
            iz, io = path[k][1], path[k][2]
            path = _unwind(path, k)
        rec(hot, path, W[hot] / W[node] * iz, io, f)
        rec(cold, path, W[cold] / W[node] * iz, 0.0, f)

    rec(0, [], 1.0, 1.0, -1)


def fallback_tree_shap(model, X):
    """Fallback (uji) untuk RandomForestClassifier / GradientBoostingClassifier sklearn."""
    n, m = X.shape
    out = np.zeros((n, m))
    if hasattr(model, "estimators_") and isinstance(model, RandomForestClassifier):
        trees = [(e.tree_, (lambda v: v[:, 0, 1] / v[:, 0, :].sum(1))(e.tree_.value), 1.0 / len(model.estimators_))
                 for e in model.estimators_]
    else:  # GradientBoostingClassifier: jumlah pohon * learning_rate, ruang log-odds
        trees = [(e[0].tree_, e[0].tree_.value[:, 0, 0], model.learning_rate) for e in model.estimators_]
    for i in range(n):
        phi = np.zeros(m + 1)
        for tr, lv, sc in trees:
            p = np.zeros(m + 1)
            tree_shap_one(tr, lv * sc, X[i], p)
            phi += p
        out[i] = phi[:m]
    return out


def explain(model_name, model, X_train, X_eval, use_fallback):
    if model_name == "LR":  # = shap.LinearExplainer (interventional, latar belakang = data latih refit), log-odds
        return model.coef_[0][None, :] * (X_eval - X_train.mean(0)[None, :])
    if use_fallback:
        return fallback_tree_shap(model, X_eval)
    import shap
    sv = shap.TreeExplainer(model).shap_values(X_eval, check_additivity=False)
    if isinstance(sv, list):
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, 1]
    return sv


# ----------------------------- METRIK STABILITAS -----------------------------
def _rank_rows(a):
    return np.apply_along_axis(rankdata, 1, a)


def pairwise_spearman(V):
    """V: (R, F). Mengembalikan korelasi Spearman semua pasangan refit (segitiga atas)."""
    rk = _rank_rows(V)
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.corrcoef(rk)
    iu = np.triu_indices(V.shape[0], 1)
    return C[iu]


def topk_membership(V, k):
    idx = np.argsort(-V, axis=1, kind="stable")[:, :k]
    M = np.zeros_like(V, dtype=float)
    np.put_along_axis(M, idx, 1.0, axis=1)
    return M


def pairwise_jaccard(V, k):
    M = topk_membership(V, k)
    inter = M @ M.T
    union = 2 * k - inter
    J = inter / union
    return J[np.triu_indices(V.shape[0], 1)]


def summarize(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return dict(mean=np.nan, p025=np.nan, median=np.nan, p975=np.nan)
    return dict(mean=x.mean(), p025=np.percentile(x, 2.5), median=np.median(x), p975=np.percentile(x, 97.5))


def chance_jaccard(F, k):
    """[v1.2] Harapan Jaccard dua himpunan top-k acak dari F fitur (hipergeometrik)."""
    k = min(k, F)
    tot = comb(F, k)
    return sum(comb(k, i) * comb(F - k, k - i) / tot * (i / (2 * k - i)) for i in range(max(0, 2 * k - F), k + 1))


def local_sign_consistency(PHI, eps=SIGN_EPS):
    """[v1.2] Tabel 3.5 proposal: SC_i = proporsi fitur dengan arah kontribusi sama antar pasangan refit.
    'all': nol pada kedua refit dihitung sepakat; 'nz': hanya fitur yang bukan nol pada kedua refit (pasangan tanpa fitur
    bukan-nol dilewati). Mengembalikan (sc_all, sc_nz) per instans, dirata-ratakan atas semua pasangan refit."""
    R, n, F = PHI.shape
    S = np.where(np.abs(PHI) < eps, 0.0, np.sign(PHI))
    iu = np.triu_indices(R, 1)
    sc_all, sc_nz = np.empty(n), np.empty(n)
    for i in range(n):
        s = S[:, i, :]
        a, b = s[iu[0]], s[iu[1]]
        eq = a == b
        sc_all[i] = eq.mean()
        nzm = (a != 0) & (b != 0)
        den = nzm.sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            r_ = np.where(den > 0, (eq & nzm).sum(1) / den, np.nan)
        sc_nz[i] = np.nanmean(r_) if np.isfinite(r_).any() else np.nan
    return sc_all, sc_nz


def stability_metrics(PHI, feat_names, near=None):
    """PHI: (R, n_eval, F) atribusi SHAP per refit, sudah diagregasi ke tingkat fitur asal.
    near: [v1.2] mask boolean (n_eval,) untuk strata dekat batas keputusan (opsional)."""
    R, n, F = PHI.shape
    G = np.abs(PHI).mean(1)                       # (R, F) pentingnya global per refit
    sp, jc = pairwise_spearman(G), pairwise_jaccard(G, min(TOPK_GLOBAL, F))
    top1 = np.argmax(G, axis=1)
    top1_share = np.bincount(top1, minlength=F) / R
    rk = _rank_rows(-G)                           # peringkat 1 = terpenting
    feat_tab = pd.DataFrame({
        "feature": feat_names,
        "mean_abs_shap": G.mean(0),
        "cv_abs_shap": G.std(0) / (G.mean(0) + 1e-12),
        "mean_rank": rk.mean(0),
        "sd_rank": rk.std(0),
        "share_top1": top1_share,
        "share_in_top%d" % TOPK_GLOBAL: (rk <= TOPK_GLOBAL).mean(0),
    }).sort_values("mean_rank")
    # lokal: per instans, kestabilan peringkat |SHAP| antar refit
    loc_sp, loc_jc = np.empty(n), np.empty(n)
    kl = min(TOPK_LOCAL, F)
    for i in range(n):
        A = np.abs(PHI[:, i, :])
        loc_sp[i] = np.nanmean(pairwise_spearman(A))
        loc_jc[i] = pairwise_jaccard(A, kl).mean()
    out = {}
    for k, v in summarize(sp).items(): out["global_spearman_" + k] = v
    for k, v in summarize(jc).items(): out["global_top%d_jaccard_%s" % (TOPK_GLOBAL, k)] = v
    out["local_spearman_median"] = np.nanmedian(loc_sp)
    out["local_spearman_q25"], out["local_spearman_q75"] = np.nanpercentile(loc_sp, [25, 75])
    out["local_spearman_p05"] = np.nanpercentile(loc_sp, 5)
    out["local_top%d_jaccard_median" % TOPK_LOCAL] = np.median(loc_jc)
    out["local_top%d_jaccard_q25" % TOPK_LOCAL], out["local_top%d_jaccard_q75" % TOPK_LOCAL] = np.percentile(loc_jc, [25, 75])
    out["local_top%d_jaccard_p05" % TOPK_LOCAL] = np.percentile(loc_jc, 5)
    # --- [v1.2] sign consistency, baseline peluang, strata dekat batas ---
    sc_all, sc_nz = local_sign_consistency(PHI)
    for nm, v in (("all", sc_all), ("nz", sc_nz)):
        out["local_sign_%s_median" % nm] = np.nanmedian(v)
        out["local_sign_%s_q25" % nm], out["local_sign_%s_q75" % nm] = np.nanpercentile(v, [25, 75])
        out["local_sign_%s_p05" % nm] = np.nanpercentile(v, 5)
    out["chance_top%d_jaccard" % TOPK_GLOBAL] = chance_jaccard(F, TOPK_GLOBAL)
    out["chance_top%d_jaccard" % TOPK_LOCAL] = chance_jaccard(F, TOPK_LOCAL)
    out["chance_sign_nominal"] = 0.5   # acuan nominal bila arah acak dan simetris; bukan baseline empiris
    if near is not None:
        out["near_n"] = int(near.sum())
        for nm, v in (("local_spearman", loc_sp), ("local_top%d_jaccard" % TOPK_LOCAL, loc_jc),
                      ("local_sign_all", sc_all), ("local_sign_nz", sc_nz)):
            out["near_%s_median" % nm] = np.nanmedian(v[near])
            out["rest_%s_median" % nm] = np.nanmedian(v[~near])
    return out, feat_tab


# ----------------------------- PIPELINE -----------------------------
CONFIGS = [("LR", "boot"), ("RF", "seed"), ("RF", "boot"), ("XGB", "seed"), ("XGB", "boot")]


def run_cohort(raw, cohort, variant, R, out_rows, out_feat, out_perf, n_jobs, selftest, split_seed=SEED, configs_sel=None,
               out_rsw=None):
    X, y, grp = build_features(raw, variant)
    feat_names = list(dict.fromkeys(grp))
    Gmat = np.zeros((X.shape[1], len(feat_names)))
    for j, g in enumerate(grp):
        Gmat[j, feat_names.index(g)] = 1.0
    Xv = X.values.astype(float)
    tr_idx, ev_idx = train_test_split(np.arange(len(y)), test_size=TEST_FRAC, stratify=y, random_state=split_seed)
    if selftest:  # uji cepat: himpunan evaluasi kecil (fallback TreeSHAP Python murni lambat)
        ev_idx = ev_idx[:40]
    Xtr, ytr, Xev, yev = Xv[tr_idx], y[tr_idx], Xv[ev_idx], y[ev_idx]
    info = dict(cohort=cohort, variant=variant, split_seed=split_seed, n=len(y), n_pos=int(y.sum()), n_train=len(tr_idx),
                n_eval=len(ev_idx), n_eval_pos=int(yev.sum()), n_columns=Xv.shape[1], n_features=len(feat_names))
    print("  [%s | %s | split %s] %s" % (cohort, variant, split_seed, info), flush=True)
    use_fb = False
    substitute_xgb = False
    if selftest:
        try:
            import shap  # noqa
        except Exception:
            use_fb = True
        try:
            import xgboost  # noqa
        except Exception:
            substitute_xgb = True
    for mi, (mname, source) in enumerate(CONFIGS):
        if configs_sel and ("%s/%s" % (mname, source)) not in configs_sel:
            continue
        t0 = time.time()
        PHI = np.full((R, len(ev_idx), len(feat_names)), np.nan)
        PR = np.full((R, len(ev_idx)), np.nan)   # [v1.2] probabilitas evaluasi per refit
        perf = []
        for r in range(R):
            key = [SEED, mi, r, VARIANT_CODE[variant], 2023 if cohort == "2023" else 2024]
            if split_seed != SEED:  # v1.0 (split_seed = SEED) tetap reprodusibel
                key.append(int(split_seed))
            rng = np.random.default_rng(key)
            seed = int(rng.integers(0, 2**31 - 1))
            if source == "boot":
                bi = rng.integers(0, len(ytr), len(ytr))
                Xb, yb = Xtr[bi], ytr[bi]
                if yb.min() == yb.max():
                    continue
            else:
                Xb, yb = Xtr, ytr
            mdl = make_model(mname, seed, n_jobs, substitute_xgb, small=use_fb).fit(Xb, yb)
            p = mdl.predict_proba(Xev)[:, 1]
            PR[r] = p
            perf.append((roc_auc_score(yev, p), average_precision_score(yev, p), balanced_accuracy_score(yev, p >= 0.5)))
            PHI[r] = explain(mname, mdl, Xb, Xev, use_fb and mname != "LR") @ Gmat
        ok = ~np.isnan(PR).all(1)               # refit yang benar-benar dijalankan (bootstrap satu-kelas dilewati)
        PHI, PR = PHI[ok], PR[ok]
        mp = PR.mean(0)
        prc, rcl, thr = precision_recall_curve(yev, mp)
        f1 = 2 * prc[:-1] * rcl[:-1] / np.maximum(prc[:-1] + rcl[:-1], 1e-12)
        t_star = float(thr[int(np.argmax(f1))])
        n_near = max(1, int(np.ceil(NEAR_FRAC * len(mp))))
        near = np.zeros(len(mp), bool); near[np.argsort(np.abs(mp - t_star), kind="stable")[:n_near]] = True
        metrics, ftab = stability_metrics(PHI, feat_names, near=near)
        metrics["strata_threshold_f1"] = t_star
        metrics["R_effective"] = int(ok.sum())
        pf = np.array(perf)
        row = dict(info, model=mname, source=source, R=R, auc_mean=pf[:, 0].mean(), auc_sd=pf[:, 0].std(),
                   prauc_mean=pf[:, 1].mean(), prauc_sd=pf[:, 1].std(), balacc_mean=pf[:, 2].mean(),
                   balacc_sd=pf[:, 2].std(), base_rate_eval=yev.mean(), **metrics)
        row["seconds"] = round(time.time() - t0, 1)
        out_rows.append(row)
        if out_rsw is not None:   # [v1.3] prefiks R dan blok terpisah
            nR = PHI.shape[0]
            plan = [("prefix", n_, 0, 0, n_) for n_ in RSWEEP_PREFIX if n_ <= nR]
            plan += [("block", RSWEEP_BLOCK, b, b * RSWEEP_BLOCK, (b + 1) * RSWEEP_BLOCK) for b in range(nR // RSWEEP_BLOCK)]
            for kind, size, b, lo, hi in plan:
                mt, _ = stability_metrics(PHI[lo:hi] if kind == "block" else PHI[:hi], feat_names)
                rsw = dict(split_seed=split_seed, cohort=cohort, variant=variant, model=mname, source=source, kind=kind,
                           R_used=hi - lo, block=b)
                rsw.update({k_: mt[k_] for k_ in KEEP})
                out_rsw.append(rsw)
        ftab.insert(0, "model", mname); ftab.insert(1, "source", source)
        ftab.insert(0, "variant", variant); ftab.insert(0, "cohort", cohort); ftab.insert(0, "split_seed", split_seed)
        out_feat.append(ftab)
        print("    %s/%s: global Spearman=%.3f, top%d Jaccard=%.3f, local Spearman(median)=%.3f, AUC=%.3f (%.0fs)" % (
            mname, source, row["global_spearman_mean"], TOPK_GLOBAL, row["global_top%d_jaccard_mean" % TOPK_GLOBAL],
            row["local_spearman_median"], row["auc_mean"], time.time() - t0), flush=True)
        print("      sign(all)=%.3f sign(nz)=%.3f | dekat-batas n=%d: spearman %.3f vs sisa %.3f" % (
            row["local_sign_all_median"], row["local_sign_nz_median"], row["near_n"],
            row["near_local_spearman_median"], row["rest_local_spearman_median"]), flush=True)



def run_null(raw, cohort, variant, P, Rn, out_null, n_jobs, selftest, configs_sel, split_seed=SEED):
    """[v1.3] Pembanding label-teracak. Untuk tiap konfigurasi bootstrap: (a) m = -1: Rn refit pertama pada label asli
    (kunci acak identik dengan run_cohort, sehingga sama dengan Rn refit pertama v1.2); (b) m = 0..P-1: label LATIH diacak
    (permutasi tetap seimbang kelas), baris latih/evaluasi sama, Rn refit bootstrap, kunci acak berbeda. AUC dihitung pada
    label evaluasi ASLI. Keluaran hanya agregat per permutasi."""
    X, y, grp = build_features(raw, variant)
    feat_names = list(dict.fromkeys(grp))
    Gmat = np.zeros((X.shape[1], len(feat_names)))
    for j, g in enumerate(grp):
        Gmat[j, feat_names.index(g)] = 1.0
    Xv = X.values.astype(float)
    tr_idx, ev_idx = train_test_split(np.arange(len(y)), test_size=TEST_FRAC, stratify=y, random_state=split_seed)
    if selftest:
        ev_idx = ev_idx[:40]
    Xtr, ytr, Xev, yev = Xv[tr_idx], y[tr_idx], Xv[ev_idx], y[ev_idx]
    year = 2023 if cohort == "2023" else 2024
    use_fb = substitute_xgb = False
    if selftest:
        try: import shap  # noqa
        except Exception: use_fb = True
        try: import xgboost  # noqa
        except Exception: substitute_xgb = True
    print("  [NULL %s | %s] n_train=%d n_eval=%d P=%d Rn=%d" % (cohort, variant, len(ytr), len(ev_idx), P, Rn), flush=True)
    for mi, (mname, source) in enumerate(CONFIGS):
        if source != "boot" or ("%s/%s" % (mname, source)) not in configs_sel:
            continue
        t0 = time.time()
        for m in range(-1, P):
            if m < 0:
                yfit = ytr
            else:
                yfit = np.random.default_rng([SEED, VARIANT_CODE[variant], year, PERM_TAG, m]).permutation(ytr)
            PHI = np.full((Rn, len(ev_idx), len(feat_names)), np.nan)
            auc = []
            for r in range(Rn):
                key = [SEED, mi, r, VARIANT_CODE[variant], year]
                if m >= 0:
                    key += [NULL_TAG, m]
                rng = np.random.default_rng(key)
                seed = int(rng.integers(0, 2**31 - 1))
                bi = rng.integers(0, len(yfit), len(yfit))
                Xb, yb = Xtr[bi], yfit[bi]
                if yb.min() == yb.max():
                    continue
                mdl = make_model(mname, seed, n_jobs, substitute_xgb, small=use_fb).fit(Xb, yb)
                p = mdl.predict_proba(Xev)[:, 1]
                auc.append(roc_auc_score(yev, p))
                PHI[r] = explain(mname, mdl, Xb, Xev, use_fb and mname != "LR") @ Gmat
            ok = ~np.isnan(PHI).all((1, 2))
            mt, _ = stability_metrics(PHI[ok], feat_names)
            row = dict(cohort=cohort, variant=variant, model=mname, source=source, split_seed=split_seed, perm=m,
                       kind="observed" if m < 0 else "permuted", R_effective=int(ok.sum()), auc_mean=float(np.mean(auc)))
            row.update({k_: mt[k_] for k_ in KEEP})
            out_null.append(row)
        sub = [r_ for r_ in out_null if (r_["cohort"], r_["variant"], r_["model"], r_["source"]) == (cohort, variant, mname, source)]
        obs = [r_ for r_ in sub if r_["kind"] == "observed"][0]
        nul = [r_ for r_ in sub if r_["kind"] == "permuted"]
        print("    %s/%s: teramati Spearman global %.3f vs null rata-rata %.3f (AUC teramati %.3f, null %.3f) (%.0fs)" % (
            mname, source, obs["global_spearman_mean"], np.mean([r_["global_spearman_mean"] for r_ in nul]), obs["auc_mean"],
            np.mean([r_["auc_mean"] for r_ in nul]), time.time() - t0), flush=True)


def null_vs_observed(null_rows):
    """[v1.3] Ringkas: nilai teramati vs distribusi null; p satu sisi = (1 + #{null >= atau <= teramati}) / (P + 1)."""
    d = pd.DataFrame(null_rows)
    out = []
    for key, g in d.groupby(["cohort", "variant", "model", "source", "split_seed"]):
        obs = g[g.kind == "observed"].iloc[0]
        nul = g[g.kind == "permuted"]
        P = len(nul)
        for mt in KEEP + ["auc_mean"]:
            v = nul[mt].to_numpy(float)
            out.append(dict(cohort=key[0], variant=key[1], model=key[2], source=key[3], split_seed=key[4], metric=mt, P=P,
                            R_null=int(obs["R_effective"]), observed=obs[mt], null_mean=v.mean(), null_sd=v.std(ddof=1) if P > 1 else np.nan,
                            null_p05=np.percentile(v, 5), null_p95=np.percentile(v, 95), null_min=v.min(), null_max=v.max(),
                            p_upper=(1 + (v >= obs[mt]).sum()) / (P + 1), p_lower=(1 + (v <= obs[mt]).sum()) / (P + 1)))
    return pd.DataFrame(out)


# ----------------------------- UJI & DATA SINTETIS -----------------------------
def make_synthetic_raw(n, seed):
    rng = np.random.default_rng(seed)
    pick = lambda opts, p=None: rng.choice(opts, n, p=p)
    d = pd.DataFrame({
        "Status DTKS": pick(["Terdata", "Belum Terdata"], [.7, .3]),
        "Status P3KE": pick(["Belum Terdata"] + ["Terdata: Desil %d" % k for k in range(1, 8)]),
        "No. KIP": pick(["-", "123"], [.8, .2]), "No. KKS": pick(["-", "1"], [.9, .1]),
        "Prestasi Siswa": pick(["-", "Juara 1"], [.65, .35]),
        "Pekerjaan Ayah": pick(["Petani", "Lainnya", "TIDAK BEKERJA", "Nelayan", "Wirausaha"]),
        "Pekerjaan Ibu": pick(["TIDAK BEKERJA", "Lainnya", "Petani"]),
        "Status Ayah": pick(["Hidup", "Wafat", "Bercerai"], [.8, .12, .08]),
        "Status Ibu": pick(["Hidup", "Wafat"], [.95, .05]),
        "Jumlah Tanggungan": pick(["%d Orang" % k for k in range(1, 8)]),
        "Pilihan Prodi 1": pick(["S1 A", "S1 B", "S1 C", "S1 D"], [.5, .2, .2, .1]),
        "Kab/Kota Sekolah": pick(["Kab X", "Kab Y", "Kota Z"]),
    })
    blk = rng.random(n) < 0.19
    for col, opts in {"Penghasilan Ayah": ["Rp. 1", "Rp. 2", "Tidak Berpenghasilan"], "Penghasilan Ibu": ["Rp. 1", "Tidak Berpenghasilan"],
                      "Kepemilikan Rumah": ["Sendiri", "Menumpang"], "Sumber Listrik": ["PLN", "Genset"],
                      "Luas Tanah": ["< 25 M2", "25-50 M2"], "Luas Bangunan": ["< 25 M2", "25-50 M2"],
                      "Sumber Air": ["Sumur", "PDAM"], "MCK": ["Sendiri", "Bersama"]}.items():
        d[col] = np.where(blk, rng.choice(opts, n), "-")
    d["Jarak Pusat Kota (KM)"] = np.where(blk, rng.integers(1, 40, n).astype(str), "-")
    z = (-1.2 + 0.9 * d["Status P3KE"].isin(["Terdata: Desil 1", "Terdata: Desil 2"]) + 0.6 * (d["No. KIP"] != "-")
         + 0.5 * (d["Pekerjaan Ayah"] == "TIDAK BEKERJA") + 0.4 * (d["Prestasi Siswa"] != "-"))
    d["Diterima"] = np.where(rng.random(n) < 1 / (1 + np.exp(-z)), "Diterima", "Tidak Diterima")
    return d


def selftest_checks():
    """Uji logika (bukan temuan): (1) TreeSHAP fallback vs Shapley brute-force; (2) metrik pada kasus yang diketahui."""
    from itertools import combinations
    from math import factorial
    from sklearn.tree import DecisionTreeClassifier
    rng = np.random.default_rng(0)
    Xs = rng.integers(0, 2, (300, 5)).astype(float) + rng.normal(0, .01, (300, 5))
    ys = ((Xs[:, 0] > .5) ^ (Xs[:, 2] > .5) | (Xs[:, 4] > .5)).astype(int)
    ys[rng.random(300) < .1] ^= 1
    dt = DecisionTreeClassifier(max_depth=4, min_samples_leaf=5, random_state=0).fit(Xs, ys)
    t = dt.tree_
    val = t.value[:, 0, 1] / t.value[:, 0, :].sum(1)

    def ev(node, x, S):
        if t.children_left[node] < 0:
            return val[node]
        f = t.feature[node]
        l, r = t.children_left[node], t.children_right[node]
        if f in S:
            return ev(l if x[f] <= t.threshold[node] else r, x, S)
        wl, wr = t.weighted_n_node_samples[l], t.weighted_n_node_samples[r]
        return (wl * ev(l, x, S) + wr * ev(r, x, S)) / (wl + wr)

    M, maxerr = 5, 0.0
    for x in Xs[:25]:
        phi = np.zeros(M + 1)
        tree_shap_one(t, val, x, phi)
        brute = np.zeros(M)
        for i in range(M):
            others = [j for j in range(M) if j != i]
            for k in range(M):
                for S in combinations(others, k):
                    w = factorial(k) * factorial(M - k - 1) / factorial(M)
                    brute[i] += w * (ev(0, x, set(S) | {i}) - ev(0, x, set(S)))
        maxerr = max(maxerr, np.abs(phi[:M] - brute).max())
    print("  [uji 1] TreeSHAP fallback vs Shapley brute-force: galat maks = %.2e" % maxerr, flush=True)
    assert maxerr < 1e-9
    # metrik: refit identik -> 1; acak -> sekitar 0
    base = np.abs(rng.normal(size=(30, 8)))
    P_same = np.repeat(base[None], 12, axis=0)
    m_same, _ = stability_metrics(P_same, ["f%d" % i for i in range(8)])
    assert abs(m_same["global_spearman_mean"] - 1) < 1e-9 and abs(m_same["local_top3_jaccard_median"] - 1) < 1e-9
    P_rand = rng.normal(size=(60, 30, 8))
    m_rand, _ = stability_metrics(P_rand, ["f%d" % i for i in range(8)])
    print("  [uji 2] identik -> Spearman %.3f; acak -> Spearman %.3f, Jaccard top3 %.3f (acuan acak ~0.2)" % (
        m_same["global_spearman_mean"], m_rand["global_spearman_mean"], m_rand["local_top3_jaccard_median"]))
    assert abs(m_rand["global_spearman_mean"]) < 0.25
    # [v1.2] sign consistency: refit identik -> 1; tanda acak -> sekitar 0.5; baseline peluang Jaccard
    assert abs(m_same["local_sign_all_median"] - 1) < 1e-9 and abs(m_same["local_sign_nz_median"] - 1) < 1e-9
    assert 0.4 < m_rand["local_sign_all_median"] < 0.6 and 0.4 < m_rand["local_sign_nz_median"] < 0.6
    assert abs(chance_jaccard(4, 2) - (1 / 6 * 1 + 4 / 6 * (1 / 3) + 1 / 6 * 0)) < 1e-12   # F=4,k=2: P(I=0,1,2)=1/6,4/6,1/6
    near_t = np.zeros(30, bool); near_t[:6] = True
    m_n, _ = stability_metrics(P_rand, ["f%d" % i for i in range(8)], near=near_t)
    assert m_n["near_n"] == 6
    print("  [uji 3] sign consistency: identik -> %.3f; acak -> %.3f (acuan 0.5); Jaccard peluang F=8,k=5 -> %.3f" % (
        m_same["local_sign_all_median"], m_rand["local_sign_all_median"], chance_jaccard(8, 5)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data2023"); ap.add_argument("--data2024")
    ap.add_argument("--out", required=True)
    ap.add_argument("--R", type=int, default=R_DEFAULT)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--split_seeds", default="", help="daftar benih pembagian evaluasi, dipisah koma; kosong = benih v1.0")
    ap.add_argument("--cohorts", default="2023,2024")
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--null_P", type=int, default=0, help="[v1.3] jumlah permutasi label; >0 = jalankan mode pembanding null")
    ap.add_argument("--null_R", type=int, default=25, help="[v1.3] jumlah refit bootstrap per permutasi")
    ap.add_argument("--rsweep", action="store_true", help="[v1.3] simpan metrik prefiks R dan blok terpisah")
    ap.add_argument("--configs", default="", help='[v1.3] mis. "LR/boot,RF/boot,XGB/boot"; kosong = semua (null: semua bootstrap)')
    a = ap.parse_args()
    configs_sel = [c.strip() for c in a.configs.split(",") if c.strip()]
    global RSWEEP_PREFIX, RSWEEP_BLOCK
    if a.selftest and a.rsweep:
        RSWEEP_PREFIX, RSWEEP_BLOCK = (2, 4, 8), 4
    os.makedirs(a.out, exist_ok=True)
    data, manifest_files = {}, {}
    if a.selftest:
        print("MODE UJI: data SINTETIS. Keluaran bukan temuan penelitian.")
        selftest_checks()
        data = {"2023": make_synthetic_raw(708, 1), "2024": make_synthetic_raw(829, 2)}
    else:
        for c, p in (("2023", a.data2023), ("2024", a.data2024)):
            if c in a.cohorts.split(","):
                if not p: sys.exit("Path data %s belum diberikan" % c)
                data[c] = read_raw(p); manifest_files[c] = sha256(p)
    rows, feats, perfs, rsw, nul = [], [], [], [], []
    seeds = [int(x) for x in a.split_seeds.split(",") if x.strip()] or [SEED]
    if a.null_P > 0:     # [v1.3] mode pembanding null (tidak menjalankan analisis utama)
        sel = configs_sel or ["%s/%s" % (m_, s_) for m_, s_ in CONFIGS if s_ == "boot"]
        for c in a.cohorts.split(","):
            for v in a.variants.split(","):
                run_null(data[c], c, v, a.null_P, a.null_R, nul, a.n_jobs, a.selftest, sel)
        pd.DataFrame(nul).to_csv(os.path.join(a.out, "null_runs.csv"), index=False)
        null_vs_observed(nul).to_csv(os.path.join(a.out, "null_vs_observed.csv"), index=False)
    else:
        for c in a.cohorts.split(","):
            for v in a.variants.split(","):
                for ss in seeds:
                    run_cohort(data[c], c, v, a.R, rows, feats, perfs, a.n_jobs, a.selftest, ss, configs_sel or None,
                               rsw if a.rsweep else None)
        pd.DataFrame(rows).to_csv(os.path.join(a.out, "stability_summary.csv"), index=False)
        pd.concat(feats).to_csv(os.path.join(a.out, "feature_level.csv"), index=False)
        if a.rsweep:
            pd.DataFrame(rsw).to_csv(os.path.join(a.out, "rsweep_summary.csv"), index=False)
    manifest = dict(protocol="A01 v1.3", null_P=a.null_P, null_R=a.null_R, rsweep=a.rsweep, configs=configs_sel, script_sha256=sha256(os.path.abspath(__file__)), near_frac=NEAR_FRAC, sign_eps=SIGN_EPS,
                    vspec={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in VSPEC.items()},
                    split_seeds=seeds, selftest=a.selftest, seed=SEED, test_frac=TEST_FRAC, R=a.R,
                    topk_global=TOPK_GLOBAL, topk_local=TOPK_LOCAL, rare_min=RARE_MIN, all_configs=CONFIGS,
                    variants=a.variants, python=platform.python_version(), input_sha256=manifest_files,
                    packages={m: getattr(__import__(m), "__version__", "?") for m in ["numpy", "pandas", "scipy", "sklearn"]})
    for m in ("shap", "xgboost"):
        try: manifest["packages"][m] = __import__(m).__version__
        except Exception: manifest["packages"][m] = "tidak terpasang"
    json.dump(manifest, open(os.path.join(a.out, "run_manifest.json"), "w"), indent=2, default=str)
    print("Selesai. Keluaran di", a.out)


if __name__ == "__main__":
    main()
