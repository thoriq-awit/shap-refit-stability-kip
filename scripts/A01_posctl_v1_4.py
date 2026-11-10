#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Artikel 01 - Stabilitas penjelasan SHAP, KIP Kuliah Seleksi Mandiri PTS Universitas Adzkia
PROTOKOL v1.4 (disusun 2026-10-31, SETELAH peneliti melihat hasil v1.3 tahap T32; seluruhnya analisis tambahan pasca-hasil).

Skrip ini TIDAK mengubah skrip v1.3. Ia memuat A01_shap_stability_v1_3.py (harus ada di folder yang sama dan hash SHA-256-nya
harus sama dengan hash beku v1.3) dan memakai ulang aturan fitur, model, penjelasan SHAP, metrik, dan kunci acak.

Dua mode:
  --mode posctl  KONTROL POSITIF SEMI-SINTETIK. Matriks fitur = fitur NYATA kohort (aturan fitur v1.3); label = SINTETIK, dibangkitkan dari
                 model logistik jarang dengan K = 3 grup fitur "benar" (dipilih acak dari kunci acak beku, bukan dari hasil), koefisien
                 acak, prevalensi disamakan dengan kohort, dan kekuatan sinyal (AUC oracle) diatur ke tiap level --levels.
                 Untuk tiap level: (a) Rn refit bootstrap pada label sintetik ("observed") dan (b) P permutasi label latih (null),
                 persis seperti N1 v1.3. Tambahan: pemulihan kebenaran (top-3 grup SHAP vs 3 grup benar; Spearman SHAP vs kebenaran).
                 Tujuan: menguji apakah protokol (metrik + pembanding null) MAMPU mendeteksi stabilitas ketika sinyal memang ada.
  --mode nullx   PERLUASAN NULL pada data nyata: permutasi m = nullx_from .. nullx_to-1 (kunci acak identik dengan v1.3, sehingga
                 permutasi 0..19 v1.3 dan 20..99 di sini membentuk satu null berukuran 100). Tidak ada baris "observed".

PENTING
- Jalankan di komputer peneliti. Data mentah mengandung identitas langsung; JANGAN diunggah. Keluaran hanya agregat.
- Label sintetik TIDAK dikeluarkan dari skrip. Data 2025 tidak dibaca.
- Hasil posctl BUKAN temuan tentang pendaftar. Ia hanya kontrol metodologis (sinyal sengaja ditanam).
- Hasil --selftest (data sintetis penuh) bukan temuan penelitian.

Contoh:
  python A01_posctl_v1_4.py --mode posctl --data2023 "...20231204.xlsx" --cohorts 2023 --variants T32 --levels 0.58,0.70,0.85 --out hasil_A01_v14_posctl_T32_2023
  python A01_posctl_v1_4.py --mode nullx --data2023 "...20231204.xlsx" --cohorts 2023 --variants T32 --nullx_from 20 --nullx_to 100 --out hasil_A01_v14_nullx_T32_2023
Uji logika:  python A01_posctl_v1_4.py --selftest --mode posctl --out selftest_v14 --levels 0.7,0.85 --null_P 3 --null_R 4
"""
import argparse, hashlib, importlib.util, json, os, platform, sys, time, warnings
import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ----------------------------- KONFIGURASI BEKU (v1.4) -----------------------------
BASE_NAME = "A01_shap_stability_v1_3.py"
BASE_SHA256 = "9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1"   # hash beku v1.3
K_TRUE = 3               # jumlah grup fitur yang sungguh membawa sinyal pada kontrol positif
POS_TAG = 7003           # penanda kunci acak: pemilihan grup benar dan koefisien
POSU_TAG = 7004          # penanda kunci acak: bilangan seragam untuk pembangkitan label
POSRUN_TAG = 7005        # penanda kunci acak: refit dan permutasi pada kontrol positif (dipisah per level)
AUC_TOL = 0.01           # toleransi |AUC oracle tercapai - target|
DEFAULT_LEVELS = (0.58, 0.70, 0.85)


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
KEEP = base.KEEP


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ----------------------------- KONTROL POSITIF: PEMBANGKIT LABEL -----------------------------
def make_truth(Xv, grp, feat_names, year, variant):
    """Pilih K_TRUE grup benar dan koefisien (kunci acak beku). Mengembalikan beta (per kolom), indeks grup benar, Xstd, kepentingan benar."""
    mu, sd = Xv.mean(0), Xv.std(0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Xstd = (Xv - mu) / sd
    rng = np.random.default_rng([SEED, base.VARIANT_CODE[variant], year, POS_TAG])
    true_idx = sorted(int(i) for i in rng.choice(len(feat_names), size=K_TRUE, replace=False))
    beta = np.zeros(Xv.shape[1])
    gi = np.array([feat_names.index(g) for g in grp])
    for j in range(Xv.shape[1]):          # urutan kolom tetap -> reprodusibel
        if gi[j] in true_idx:
            beta[j] = rng.normal()
    imp = np.zeros(len(feat_names))
    for g in true_idx:
        cols = np.where(gi == g)[0]
        imp[g] = np.abs(Xstd[:, cols] @ beta[cols]).mean()
    return beta, true_idx, Xstd, imp


def calibrate(Xstd, beta, prevalence, year, variant, target_auc):
    """Cari (a, s) sehingga rata-rata peluang = prevalensi dan AUC oracle (peluang benar vs label tersampel) ~ target.
    Bilangan seragam u tetap (kunci beku), jadi label deterministik untuk setiap level."""
    n = Xstd.shape[0]
    z = Xstd @ beta
    z = (z - z.mean()) / (z.std() + 1e-12)
    u = np.random.default_rng([SEED, base.VARIANT_CODE[variant], year, POSU_TAG]).random(n)

    def p_of(s):
        lo, hi = -25.0, 25.0
        for _ in range(60):
            a = (lo + hi) / 2
            if expit(a + s * z).mean() > prevalence:
                hi = a
            else:
                lo = a
        return expit(a + s * z), a

    lo, hi = 0.0, 15.0
    for _ in range(45):
        s = (lo + hi) / 2
        p, _a = p_of(s)
        y = (u < p).astype(int)
        auc = roc_auc_score(y, p) if 0 < y.sum() < n else 0.5
        if auc < target_auc:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    p, a = p_of(s)
    y = (u < p).astype(int)
    return y, float(roc_auc_score(y, p)), float(s), float(a)


# ----------------------------- PELARI GENERIK -----------------------------
def recovery(PHIok, true_idx, imp):
    """Rata-rata per-refit: (a) proporsi 3 grup benar di top-3 |SHAP| rata-rata; (b) Spearman |SHAP| global vs kepentingan benar."""
    G = np.abs(PHIok).mean(1)                       # (R, F)
    rec, sps = [], []
    for g in G:
        top = set(np.argsort(-g)[:K_TRUE].tolist())
        rec.append(len(top & set(true_idx)) / K_TRUE)
        if np.ptp(g) > 0:
            sps.append(spearmanr(g, imp).correlation)
    return float(np.mean(rec)), float(np.nanmean(sps)) if sps else np.nan


def run_block(Xtr, ytr, Xev, yev, Gmat, feat_names, vcode, year, extra, mrange, Rn, n_jobs, selftest, configs_sel,
              truth, rows, meta, tag):
    """Untuk tiap konfigurasi bootstrap terpilih dan tiap m dalam mrange (m = -1: label asli/sintetik; m >= 0: label latih diacak):
    Rn refit bootstrap, metrik stabilitas, AUC (pada yev), pemulihan kebenaran (bila truth ada).
    Kunci acak: dengan extra = [] identik dengan base.run_null (v1.3)."""
    use_fb = substitute_xgb = False
    if selftest:
        try: import shap  # noqa
        except Exception: use_fb = True
        try: import xgboost  # noqa
        except Exception: substitute_xgb = True
    for mi, (mname, source) in enumerate(base.CONFIGS):
        if source != "boot" or ("%s/%s" % (mname, source)) not in configs_sel:
            continue
        t0 = time.time()
        for m in mrange:
            if m < 0:
                yfit = ytr
            else:
                yfit = np.random.default_rng([SEED, vcode, year, base.PERM_TAG, m] + extra).permutation(ytr)
            PHI = np.full((Rn, len(yev), len(feat_names)), np.nan)
            auc = []
            for r in range(Rn):
                key = [SEED, mi, r, vcode, year] + extra
                if m >= 0:
                    key += [base.NULL_TAG, m]
                rng = np.random.default_rng(key)
                seed = int(rng.integers(0, 2**31 - 1))
                bi = rng.integers(0, len(yfit), len(yfit))
                Xb, yb = Xtr[bi], yfit[bi]
                if yb.min() == yb.max():
                    continue
                mdl = base.make_model(mname, seed, n_jobs, substitute_xgb, small=use_fb).fit(Xb, yb)
                p = mdl.predict_proba(Xev)[:, 1]
                auc.append(roc_auc_score(yev, p))
                PHI[r] = base.explain(mname, mdl, Xb, Xev, use_fb and mname != "LR") @ Gmat
            ok = ~np.isnan(PHI).all((1, 2))
            mt, _ = base.stability_metrics(PHI[ok], feat_names)
            row = dict(meta)
            row.update(model=mname, source=source, perm=m, kind="observed" if m < 0 else "permuted",
                       R_effective=int(ok.sum()), auc_mean=float(np.mean(auc)) if auc else np.nan)
            row.update({k_: mt[k_] for k_ in KEEP})
            if truth is not None:
                row["rec_top3"], row["rec_spearman"] = recovery(PHI[ok], truth[0], truth[1])
            rows.append(row)
        sub = [r_ for r_ in rows if r_.get("model") == mname and r_.get("source") == source and r_.get("tag") == tag and r_.get("cohort") == meta["cohort"]]
        nul = [r_ for r_ in sub if r_["kind"] == "permuted"]
        obs = [r_ for r_ in sub if r_["kind"] == "observed"]
        msg = "    %s/%s [%s]: " % (mname, source, tag)
        if obs:
            msg += "teramati Spearman global %.3f, lokal %.3f, AUC %.3f" % (obs[0]["global_spearman_mean"], obs[0]["local_spearman_median"], obs[0]["auc_mean"])
            if truth is not None:
                msg += ", pemulihan top-3 %.2f" % obs[0]["rec_top3"]
        if nul:
            msg += " | null (n=%d) Spearman global %.3f, lokal %.3f" % (len(nul), np.mean([r_["global_spearman_mean"] for r_ in nul]),
                                                                          np.mean([r_["local_spearman_median"] for r_ in nul]))
        print(msg + " (%.0fs)" % (time.time() - t0), flush=True)


def prep_cohort(raw, cohort, variant):
    X, y, grp = base.build_features(raw, variant)
    feat_names = list(dict.fromkeys(grp))
    Gmat = np.zeros((X.shape[1], len(feat_names)))
    for j, g in enumerate(grp):
        Gmat[j, feat_names.index(g)] = 1.0
    return X.values.astype(float), y, grp, feat_names, Gmat


def split(y, selftest, split_seed=SEED):
    tr, ev = train_test_split(np.arange(len(y)), test_size=base.TEST_FRAC, stratify=y, random_state=split_seed)
    if selftest:
        ev = ev[:40]
    return tr, ev


def run_posctl(raw, cohort, variant, levels, P, Rn, rows, truthlog, n_jobs, selftest, configs_sel):
    year = 2023 if cohort == "2023" else 2024
    vcode = base.VARIANT_CODE[variant]
    Xv, y_real, grp, feat_names, Gmat = prep_cohort(raw, cohort, variant)
    prevalence = float(y_real.mean())
    beta, true_idx, Xstd, imp = make_truth(Xv, grp, feat_names, year, variant)
    print("  [POSCTL %s | %s] n=%d kolom=%d grup=%d prevalensi=%.3f grup benar=%s" % (
        cohort, variant, len(y_real), Xv.shape[1], len(feat_names), prevalence, [feat_names[i] for i in true_idx]), flush=True)
    for li, target in enumerate(levels):
        ysyn, auc_or, s, a = calibrate(Xstd, beta, prevalence, year, variant, target)
        if abs(auc_or - target) > AUC_TOL:
            print("    PERINGATAN: AUC oracle %.3f menyimpang dari target %.3f" % (auc_or, target), flush=True)
        tr, ev = split(ysyn, selftest)
        Xtr, ytr, Xev, yev = Xv[tr], ysyn[tr], Xv[ev], ysyn[ev]
        meta = dict(cohort=cohort, variant=variant, level_target=target, level_oracle_auc=auc_or, tag="L%.2f" % target,
                    split_seed=SEED, n_train=len(tr), n_eval=len(ev), n_eval_pos=int(yev.sum()))
        truthlog.append(dict(cohort=cohort, variant=variant, level_target=target, level_oracle_auc=auc_or, scale=s, intercept=a,
                             prevalence_real=prevalence, prevalence_syn=float(ysyn.mean()), true_groups="|".join(feat_names[i] for i in true_idx)))
        print("  -- level %.2f: AUC oracle %.3f; prevalensi sintetik %.3f; n_latih=%d n_eval=%d" % (target, auc_or, ysyn.mean(), len(tr), len(ev)), flush=True)
        run_block(Xtr, ytr, Xev, yev, Gmat, feat_names, vcode, year, [POSRUN_TAG, li], range(-1, P), Rn, n_jobs, selftest,
                  configs_sel, (true_idx, imp), rows, meta, meta["tag"])


def run_nullx(raw, cohort, variant, m_from, m_to, Rn, rows, n_jobs, selftest, configs_sel):
    year = 2023 if cohort == "2023" else 2024
    vcode = base.VARIANT_CODE[variant]
    Xv, y, grp, feat_names, Gmat = prep_cohort(raw, cohort, variant)
    tr, ev = split(y, selftest)
    Xtr, ytr, Xev, yev = Xv[tr], y[tr], Xv[ev], y[ev]
    meta = dict(cohort=cohort, variant=variant, level_target=np.nan, level_oracle_auc=np.nan, tag="NX", split_seed=SEED,
                n_train=len(tr), n_eval=len(ev), n_eval_pos=int(yev.sum()))
    print("  [NULLX %s | %s] permutasi %d..%d Rn=%d n_train=%d n_eval=%d" % (cohort, variant, m_from, m_to - 1, Rn, len(tr), len(ev)), flush=True)
    run_block(Xtr, ytr, Xev, yev, Gmat, feat_names, vcode, year, [], range(m_from, m_to), Rn, n_jobs, selftest, configs_sel,
              None, rows, meta, "NX")


# ----------------------------- RINGKASAN -----------------------------
def summarize(rows):
    d = pd.DataFrame(rows)
    mets = KEEP + ["auc_mean"] + [c for c in ("rec_top3", "rec_spearman") if c in d.columns]
    out = []
    for key, g in d.groupby(["cohort", "variant", "tag", "model", "source"], dropna=False):
        obs = g[g.kind == "observed"]
        nul = g[g.kind == "permuted"]
        if obs.empty or nul.empty:
            continue
        o = obs.iloc[0]
        P = len(nul)
        for mt in mets:
            v = nul[mt].to_numpy(float)
            out.append(dict(cohort=key[0], variant=key[1], tag=key[2], level_target=o["level_target"], level_oracle_auc=o["level_oracle_auc"],
                            model=key[3], source=key[4], metric=mt, P=P, R_null=int(o["R_effective"]), observed=o[mt],
                            null_mean=v.mean(), null_sd=v.std(ddof=1) if P > 1 else np.nan, null_min=v.min(), null_max=v.max(),
                            above_null=bool(o[mt] > v.max()), below_null=bool(o[mt] < v.min()),
                            p_upper=(1 + (v >= o[mt]).sum()) / (P + 1)))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["posctl", "nullx"], required=True)
    ap.add_argument("--data2023"); ap.add_argument("--data2024")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cohorts", default="2023,2024")
    ap.add_argument("--variants", default="T32")
    ap.add_argument("--levels", default=",".join(str(x) for x in DEFAULT_LEVELS), help="target AUC oracle, dipisah koma (posctl)")
    ap.add_argument("--null_P", type=int, default=20, help="posctl: jumlah permutasi per level")
    ap.add_argument("--null_R", type=int, default=25, help="jumlah refit bootstrap per permutasi")
    ap.add_argument("--nullx_from", type=int, default=20)
    ap.add_argument("--nullx_to", type=int, default=100)
    ap.add_argument("--configs", default="LR/boot,RF/boot,XGB/boot")
    ap.add_argument("--n_jobs", type=int, default=-1)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    configs_sel = [c.strip() for c in a.configs.split(",") if c.strip()]
    levels = [float(x) for x in a.levels.split(",") if x.strip()]
    os.makedirs(a.out, exist_ok=True)
    data, files = {}, {}
    if a.selftest:
        print("MODE UJI: data SINTETIS. Keluaran bukan temuan penelitian.")
        data = {"2023": base.make_synthetic_raw(708, 1), "2024": base.make_synthetic_raw(829, 2)}
    else:
        for c, p in (("2023", a.data2023), ("2024", a.data2024)):
            if c in a.cohorts.split(","):
                if not p: sys.exit("Path data %s belum diberikan" % c)
                data[c] = base.read_raw(p); files[c] = sha256(p)
    rows, truthlog = [], []
    for c in a.cohorts.split(","):
        for v in a.variants.split(","):
            if a.mode == "posctl":
                run_posctl(data[c], c, v, levels, a.null_P, a.null_R, rows, truthlog, a.n_jobs, a.selftest, configs_sel)
            else:
                run_nullx(data[c], c, v, a.nullx_from, a.nullx_to, a.null_R, rows, a.n_jobs, a.selftest, configs_sel)
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(a.out, "posctl_runs.csv" if a.mode == "posctl" else "nullx_runs.csv"), index=False)
    if a.mode == "posctl":
        summarize(rows).to_csv(os.path.join(a.out, "posctl_vs_null.csv"), index=False)
        pd.DataFrame(truthlog).to_csv(os.path.join(a.out, "posctl_design.csv"), index=False)
    manifest = dict(protocol="A01 v1.4", mode=a.mode, script_sha256=sha256(os.path.abspath(__file__)), base_script=BASE_NAME, base_sha256=BASE_SHA256,
                    levels=levels, null_P=a.null_P, null_R=a.null_R, nullx_from=a.nullx_from, nullx_to=a.nullx_to, configs=configs_sel,
                    k_true=K_TRUE, pos_tags=[POS_TAG, POSU_TAG, POSRUN_TAG], auc_tol=AUC_TOL, variants=a.variants, cohorts=a.cohorts,
                    selftest=a.selftest, seed=SEED, test_frac=base.TEST_FRAC, python=platform.python_version(), input_sha256=files,
                    packages={m: getattr(__import__(m), "__version__", "?") for m in ["numpy", "pandas", "scipy", "sklearn"]})
    for m in ("shap", "xgboost"):
        try: manifest["packages"][m] = __import__(m).__version__
        except Exception: manifest["packages"][m] = "tidak terpasang"
    json.dump(manifest, open(os.path.join(a.out, "run_manifest.json"), "w"), indent=2, default=str)
    print("Selesai. Keluaran di", a.out)


if __name__ == "__main__":
    main()
