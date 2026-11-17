#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Artikel 01 - Stabilitas penjelasan SHAP terhadap pembanding null berlabel-teracak
PROTOKOL v1.5 (disusun 2026-11-17): DATASET PEMBANDING PUBLIK (UCI "Predict Students' Dropout and Academic Success").

Status: analisis tambahan PASCA-HASIL. Disusun setelah seluruh hasil KIP v1.2-v1.4 diketahui, tetapi SEBELUM model apa pun
dilatih pada data UCI. Sebelum pembekuan, pada data UCI hanya dilihat: ukuran data, kolom, distribusi label, dan satu tabel
silang deskriptif "Scholarship holder" x "Target" (lihat A01_v1_5_PROTOKOL.md bagian 1).

Tujuan: menjalankan protokol yang SAMA (skrip v1.3 tanpa perubahan) pada data pendidikan nyata dengan sinyal yang diduga lebih
kuat, untuk melihat apakah protokol membedakan penjelasan yang stabil di atas null dari yang tidak.

Skrip ini TIDAK mengubah skrip v1.3. Ia memuat A01_shap_stability_v1_3.py (harus di folder yang sama, hash SHA-256 harus sama
dengan hash beku v1.3) dan hanya mengganti PEMBANGUN FITUR untuk kolom UCI. Model, penjelasan SHAP, metrik, ambang dekat-batas,
dan pembanding null dipakai ulang dari v1.3.

Desain beku:
  Label    : Target = "Dropout" -> 1, "Graduate" -> 0; "Enrolled" (luaran belum diketahui) dikeluarkan. N = 3630.
  Fitur    : hanya yang diketahui saat pendaftaran (17 grup, lihat FEAT_CAT dan FEAT_NUM). Dikeluarkan: 12 kolom unit kurikuler
             semester 1-2 (setelah kuliah berjalan), 3 indikator makroekonomi (nilai per tahun masuk), Debtor, Tuition fees up to
             date, Scholarship holder (waktu pengukuran tidak didokumentasikan), International (berulang dengan Nacionality).
  Sampel   : UCI_s1..UCI_s5 = lima subsampel berstrata label, masing-masing N = 800 (sebanding dengan kohort KIP), diambil tanpa
             pengembalian dengan kunci acak beku; UCI_full = seluruh 3630 baris (acuan ukuran sampel).

Mode:
  --mode main   analisis stabilitas v1.3 (R refit; konfigurasi LR/boot, RF/seed, RF/boot, XGB/seed, XGB/boot)
  --mode null   pembanding label-teracak v1.3 (P permutasi x Rn refit bootstrap; konfigurasi bootstrap)

Contoh:
  python A01_uci_v1_5.py --mode main --data data.csv --samples UCI_s1,UCI_s2,UCI_s3,UCI_s4,UCI_s5 --R 100 --out hasil_A01_v15_main_sub
  python A01_uci_v1_5.py --mode null --data data.csv --samples UCI_s1 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s1
Uji logika (data sintetis, bukan temuan):
  python A01_uci_v1_5.py --selftest --mode main --samples UCI_s1 --R 4 --out selftest_v15
"""
import argparse, hashlib, importlib.util, json, os, platform, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ----------------------------- KONFIGURASI BEKU (v1.5) -----------------------------
BASE_NAME = "A01_shap_stability_v1_3.py"
BASE_SHA256 = "9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1"   # hash beku v1.3
DATA_SHA256 = "3ef126de5cefff26eb11fbb4237f1a1401cb64b488e2f1d598c23cedeb4c45ae"   # data.csv dari arsip UCI yang diunduh peneliti (diisi saat pembekuan)
COHORT = "UCI"
LABEL_SRC = "Target"
POS, NEG, DROP = "Dropout", "Graduate", "Enrolled"
SUB_N = 800
SUB_TAG = 1505                    # penanda kunci acak pengambilan subsampel
SAMPLE_CODES = {"UCI_full": 30, "UCI_s1": 31, "UCI_s2": 32, "UCI_s3": 33, "UCI_s4": 34, "UCI_s5": 35}

FEAT_CAT = {   # kolom kategorik (kode bilangan di UCI diperlakukan sebagai label kategori)
    "Marital status": "Marital_status",
    "Application mode": "Application_mode",
    "Course": "Course",
    "Daytime/evening attendance": "Attendance",
    "Previous qualification": "Prev_qualification",
    "Nacionality": "Nationality",
    "Mother's qualification": "Mother_qualification",
    "Father's qualification": "Father_qualification",
    "Mother's occupation": "Mother_occupation",
    "Father's occupation": "Father_occupation",
    "Displaced": "Displaced",
    "Educational special needs": "Special_needs",
    "Gender": "Gender",
}
FEAT_NUM = {
    "Application order": "Application_order",
    "Previous qualification (grade)": "Prev_qualification_grade",
    "Admission grade": "Admission_grade",
    "Age at enrollment": "Age_at_enrollment",
}
EXCLUDED = ["Debtor", "Tuition fees up to date", "Scholarship holder", "International",
            "Unemployment rate", "Inflation rate", "GDP"]   # + 12 kolom "Curricular units ..."


def load_base():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, BASE_NAME)
    if not os.path.exists(path):
        sys.exit("Skrip v1.3 (%s) harus berada di folder yang sama dengan skrip ini." % BASE_NAME)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != BASE_SHA256:
        sys.exit("Hash skrip v1.3 tidak sama dengan hash beku (%s). Hentikan; jangan jalankan." % h)
    spec = importlib.util.spec_from_file_location("a01v13", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["a01v13"] = mod
    spec.loader.exec_module(mod)
    return mod


base = load_base()
SEED = base.SEED


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ----------------------------- DATA -----------------------------
def read_uci(path):
    d = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
    d.columns = [c.strip() for c in d.columns]
    need = list(FEAT_CAT) + list(FEAT_NUM) + [LABEL_SRC]
    miss = [c for c in need if c not in d.columns]
    if miss:
        sys.exit("Kolom tidak ditemukan di data UCI: %s" % miss)
    d[LABEL_SRC] = d[LABEL_SRC].str.strip()
    d = d[d[LABEL_SRC].isin([POS, NEG])].reset_index(drop=True)
    d[base.LABEL_COL] = np.where(d[LABEL_SRC] == POS, "diterima", "tidak")   # 1 = Dropout (format label v1.3)
    return d


def draw_sample(d, name):
    if name == "UCI_full":
        return d.copy()
    s = int(name.split("_s")[1])
    rng = np.random.default_rng([SEED, SUB_TAG, s])
    y = (d[LABEL_SRC] == POS).values
    pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
    n_pos = int(round(SUB_N * len(pos) / len(y)))
    idx = np.sort(np.concatenate([rng.choice(pos, n_pos, replace=False), rng.choice(neg, SUB_N - n_pos, replace=False)]))
    return d.iloc[idx].reset_index(drop=True)


def build_features_uci(raw, variant):
    """Pengganti build_features v1.3 untuk kolom UCI (aturan sama: one-hot + kategori langka -> 'Lainnya';
    numerik distandarkan pada sampel yang dianalisis; transformasi bebas-label; kolom konstan dibuang)."""
    y = (raw[base.LABEL_COL].astype(str).str.strip().str.lower() == "diterima").astype(int).values
    feats, groups = {}, {}
    for col, name in FEAT_CAT.items():
        s = raw[col].astype("string").str.strip()
        s = s.mask(base.is_missing(s), base.MISSING_LABEL)
        vc = s.value_counts()
        small = vc[vc < base.RARE_MIN].index
        s = s.mask(s.isin(small) & (s != base.MISSING_LABEL), "Lainnya")
        dm = pd.get_dummies(s, prefix=name, prefix_sep="=", dtype=float)
        for c in dm.columns:
            feats[c] = dm[c].values
            groups[c] = name
    for col, name in FEAT_NUM.items():
        v = pd.to_numeric(raw[col], errors="coerce")
        v = v.fillna(v.median())
        feats[name] = ((v - v.mean()) / (v.std() + 1e-12)).values.astype(float)
        groups[name] = name
    X = pd.DataFrame(feats)
    keep = [c for c in X.columns if X[c].nunique() > 1]
    X = X[keep]
    return X, y, [groups[c] for c in X.columns]


def make_synthetic_uci(seed, n=3630):
    """HANYA untuk --selftest: kolom sama dengan UCI, nilai acak. Bukan temuan."""
    rng = np.random.default_rng(seed)
    d = {}
    for col in FEAT_CAT:
        d[col] = rng.integers(1, 8, n).astype(str)
    for col in FEAT_NUM:
        d[col] = np.round(rng.normal(130, 14, n), 1).astype(str)
    z = (d["Mother's qualification"].astype(int) - 4) * 0.4 + rng.normal(0, 1, n)
    d[LABEL_SRC] = np.where(z > 0.4, POS, np.where(rng.random(n) < 0.15, DROP, NEG))
    return pd.DataFrame(d)


# ----------------------------- UTAMA -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["main", "null"], required=True)
    ap.add_argument("--data")
    ap.add_argument("--samples", required=True, help="mis. UCI_s1,UCI_s2 atau UCI_full")
    ap.add_argument("--out", required=True)
    ap.add_argument("--R", type=int, default=base.R_DEFAULT)
    ap.add_argument("--null_P", type=int, default=100)
    ap.add_argument("--null_R", type=int, default=25)
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    samples = [s.strip() for s in a.samples.split(",") if s.strip()]
    bad = [s for s in samples if s not in SAMPLE_CODES]
    if bad:
        sys.exit("Nama sampel tidak dikenal: %s" % bad)
    os.makedirs(a.out, exist_ok=True)

    # sambungkan aturan fitur UCI ke modul v1.3 (tanpa mengubah berkasnya)
    base.build_features = build_features_uci
    base.VARIANT_CODE.update(SAMPLE_CODES)

    if a.selftest:
        print("MODE UJI: data SINTETIS. Keluaran bukan temuan penelitian.")
        d = make_synthetic_uci(1)
        d.columns = [c.strip() for c in d.columns]
        d = d[d[LABEL_SRC].isin([POS, NEG])].reset_index(drop=True)
        d[base.LABEL_COL] = np.where(d[LABEL_SRC] == POS, "diterima", "tidak")
        in_sha = None
    else:
        if not a.data:
            sys.exit("Path data UCI (--data) belum diberikan.")
        in_sha = sha256(a.data)
        if DATA_SHA256 != "__DATA_SHA256__" and in_sha != DATA_SHA256:
            sys.exit("Hash data.csv (%s) tidak sama dengan hash beku. Pastikan berkas dari arsip UCI yang sama." % in_sha)
        d = read_uci(a.data)
    print("Data UCI (setelah Enrolled dikeluarkan): N=%d, Dropout=%d" % (len(d), int((d[LABEL_SRC] == POS).sum())), flush=True)

    rows, feats, perfs, nul, sample_info = [], [], [], [], []
    for s in samples:
        raw = draw_sample(d, s)
        X, y, grp = build_features_uci(raw, s)
        sample_info.append(dict(sample=s, n=len(raw), n_pos=int(y.sum()), n_columns=X.shape[1],
                                n_groups=len(dict.fromkeys(grp))))
        if a.mode == "main":
            base.run_cohort(raw, COHORT, s, a.R, rows, feats, perfs, a.n_jobs, a.selftest)
        else:
            sel = ["%s/%s" % (m_, s_) for m_, s_ in base.CONFIGS if s_ == "boot"]
            base.run_null(raw, COHORT, s, a.null_P, a.null_R, nul, a.n_jobs, a.selftest, sel)

    if a.mode == "main":
        pd.DataFrame(rows).to_csv(os.path.join(a.out, "stability_summary.csv"), index=False)
        pd.concat(feats).to_csv(os.path.join(a.out, "feature_level.csv"), index=False)
    else:
        pd.DataFrame(nul).to_csv(os.path.join(a.out, "null_runs.csv"), index=False)
        base.null_vs_observed(nul).to_csv(os.path.join(a.out, "null_vs_observed.csv"), index=False)
    pd.DataFrame(sample_info).to_csv(os.path.join(a.out, "samples.csv"), index=False)

    manifest = dict(protocol="A01 v1.5 (UCI pembanding)", mode=a.mode, samples=samples, R=a.R, null_P=a.null_P,
                    null_R=a.null_R, selftest=a.selftest, script_sha256=sha256(os.path.abspath(__file__)),
                    base_sha256=BASE_SHA256, input_sha256=in_sha, seed=SEED, sub_n=SUB_N, sub_tag=SUB_TAG,
                    feat_cat=list(FEAT_CAT), feat_num=list(FEAT_NUM), excluded=EXCLUDED + ["Curricular units (12 kolom)"],
                    python=platform.python_version(),
                    packages={m: getattr(__import__(m), "__version__", "?") for m in ["numpy", "pandas", "scipy", "sklearn"]})
    for m in ("shap", "xgboost"):
        try:
            manifest["packages"][m] = __import__(m).__version__
        except Exception:
            manifest["packages"][m] = "tidak terpasang"
    json.dump(manifest, open(os.path.join(a.out, "run_manifest.json"), "w"), indent=2, default=str)
    print("Selesai. Keluaran di", a.out)


if __name__ == "__main__":
    main()
