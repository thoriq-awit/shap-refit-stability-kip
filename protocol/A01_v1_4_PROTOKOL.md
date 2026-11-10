# A01 — Protokol v1.4 (amandemen pasca-hasil v1.3)

Dibekukan: 2026-10-31T01:43:06Z (sebelum ada hasil v1.4), lihat `A01_v1_4_FREEZE.json`. Skrip: `A01_posctl_v1_4.py` (SHA-256 `dbe5561818fee01cc7fc3804e0d02bef534a09837e690ebdaef08aa6c4c800ee`); penerap aturan: `A01_v14_aturan.py` (`4435dccf336b284fbc22588bfdb6e7807d975febe260c997e8c270ab92078c98`); skrip uji: `uji_v14.py` (`8cf3a8d3c9af88e30c5c1e577393b6e29d52c362f022c262631462cbdaaf3b38`). Skrip dasar v1.3 tidak diubah (`9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1`) dan diverifikasi hash-nya oleh skrip v1.4 setiap kali dijalankan.

## 1. Mengapa v1.4

Hasil v1.3 tahap T32 menunjukkan stabilitas global SHAP tidak terbedakan dari model berlabel acak, dan AUC model hampir tidak terbedakan dari model acak. Ada dua penjelasan yang tidak dapat dipisahkan oleh data nyata saja:
1. Data seleksi ini memang hampir tanpa sinyal yang dapat dipelajari model (sehingga penjelasannya setara dengan penjelasan model acak).
2. Protokol (metrik + pembanding null) tidak cukup peka: bahkan bila sinyal ada, stabilitas yang dihasilkannya tidak dapat dibedakan dari null.

Tanpa kontrol positif (data dengan sinyal yang ditanam dan diketahui), artikel tidak dapat menyatakan mana yang benar. v1.4 menambah kontrol itu. v1.4 juga (a) memperbesar null dari 20 menjadi 100 permutasi pada data nyata (p terkecil 0,048 menjadi 0,0099) dan (b) mencantumkan tahap N2/R2 (E_blok_rumah) yang belum dijalankan pada v1.3.

## 2. Status (wajib diungkap di Methods)

v1.4 disusun SETELAH peneliti melihat hasil v1.3 tahap T32, jadi seluruhnya analisis tambahan pasca-hasil. Skrip v1.3 tidak diubah. Data 2025 tidak dibaca. Label pada kontrol positif adalah SINTETIK dan bukan temuan tentang pendaftar.

## 3. Tahapan

| Tahap | Perintah | Pengaturan beku | Menjawab |
|---|---|---|---|
| PC | `A01_posctl_v1_4.py --mode posctl --variants T32 --levels 0.58,0.70,0.85 --null_P 20 --null_R 25` | Fitur NYATA kohort (aturan fitur v1.3), label SINTETIK: model logistik jarang dengan K = 3 grup fitur "benar" (dipilih dengan kunci acak beku `[SEED, kode_varian, tahun, 7003]`, bukan dari hasil), koefisien acak normal baku per kolom, prevalensi disamakan dengan kohort, kekuatan sinyal diatur sehingga AUC oracle (peluang benar vs label tersampel) sama dengan target 0,58 / 0,70 / 0,85. Per level: 25 refit bootstrap pada label sintetik ("teramati") dan 20 permutasi label latih × 25 refit (null), LR/RF/XGB bootstrap, pembagian 70/30 stratifikasi pada label sintetik. Tambahan: pemulihan kebenaran (top-3 grup SHAP vs 3 grup benar; Spearman SHAP global vs kepentingan benar). | Apakah protokol mampu mendeteksi stabilitas ketika sinyal ada (PC-1), apakah stabilitas naik bersama sinyal (PC-2), apakah SHAP memulihkan grup benar (PC-3), dan di titik mana pada sumbu sinyal data nyata berada (PC-4) |
| N2/R2 | Perintah v1.3 bagian 3 (`--variants E_blok_rumah`), aturan v1.3 | Tidak berubah dari v1.3 | RQ3: selisih T32 vs E melebihi galat Monte Carlo? |
| NX | `A01_posctl_v1_4.py --mode nullx --variants T32 --nullx_from 20 --nullx_to 100 --null_R 25` | Permutasi 20..99 dengan kunci acak identik v1.3; digabung dengan permutasi 0..19 dari v1.3 menjadi null berukuran 100; nilai teramati tetap dari v1.3 | Apakah "di atas null" bertahan pada null yang lebih besar (NX-1) |

Urutan prioritas: PC → N2/R2 → NX. Tahap yang tidak sempat dijalankan dilaporkan "tidak dijalankan"; tidak ada tahap yang dipilih atau dilewati berdasarkan hasil tahap lain. Seluruh level PC (0,58 / 0,70 / 0,85) dijalankan; level 0,58 dipilih karena kira-kira sebanding dengan AUC model nyata T32 (0,52–0,59), bukan dari hasil.

Prevalensi label sintetik mengikuti prevalensi kohort (29,8% pada 2023; 23,5% pada 2024) dengan simpangan acak sampling beberapa persen poin; nilai tercapai dicatat di `posctl_design.csv`.

## 4. Aturan keputusan (ditetapkan sebelum run; diterapkan mekanis oleh `A01_v14_aturan.py`)

Sel = kohort × model (2 × 3 = 6 sel bila kedua kohort dijalankan). "Di atas null" = nilai teramati melebihi seluruh 20 nilai null (aturan yang sama dengan R-N1 v1.3). Ambang berikut adalah ambang kerja peneliti, bukan standar literatur [EVIDENCE REQUIRED bila ingin dikutip].

- **PC-1 (kepekaan protokol).** Pada level tertinggi (0,85), untuk Spearman global dan Spearman lokal median: "di atas null" pada setidaknya 80% sel (5 dari 6). Bila keduanya terpenuhi, protokol dinyatakan "peka pada sinyal kuat". Bila tidak, Results menyatakan protokol tidak terbukti peka dan pembacaan "tidak terbedakan dari null" pada data nyata tidak dapat ditafsirkan sebagai tidak adanya sinyal.
- **PC-2 (dosis–respons).** Untuk tiap sel dan tiap dari dua metrik di atas, selisih (teramati − rata-rata null) disebut monoton bila tidak turun lebih dari 0,02 antar level berurutan. Dosis–respons dinyatakan ada bila setidaknya 2/3 sel monoton pada kedua metrik.
- **PC-3 (pemulihan kebenaran).** Pada level 0,85: pemulihan top-3 teramati "di atas null" pada setidaknya 80% sel DAN rata-rata pemulihan top-3 teramati ≥ 2/3. Bila tidak, Results menyatakan SHAP pada n dan struktur fitur ini tidak memulihkan grup benar secara andal. Pemulihan pada semua level dilaporkan.
- **PC-4 (posisi data nyata; deskriptif, tanpa lulus/gagal).** Untuk tiap sel dan metrik inti, level kontrol positif yang nilai teramatinya paling dekat dengan nilai nyata T32 (v1.3) dilaporkan. Ini menunjukkan "setara dengan sinyal sekitar berapa" dan bergantung pada rancangan sintetik; tidak dipakai untuk inferensi.
- **PC-5 (deteksi per level; deskriptif).** Jumlah sel "di atas null" untuk tiap metrik inti pada tiap level, termasuk level 0,58, dilaporkan sebagai batas bawah kepekaan.
- **NX-1 (null diperluas).** Bila NX dijalankan, null berukuran 100 (permutasi 0–19 v1.3 + 20–99 v1.4), p satu sisi = (1 + #{null ≥ teramati}) / 101. "Di atas null (diperluas)" bila p ≤ 0,05. Klaim "stabilitas melebihi model tanpa sinyal" tetap hanya bila di atas null pada KEDUA kohort. Pembacaan sekunder: Benjamini–Hochberg q ≤ 0,10 atas 30 sel inti. Aturan R-N1 v1.3 (melebihi seluruh 20 nilai) tetap dilaporkan di lampiran; bila NX dijalankan, NX-1 adalah aturan utama; bila tidak, R-N1 yang berlaku. Pilihan ini ditetapkan sekarang, bukan dari hasil.
- **N2/R2.** Aturan R-N1, R-N2, R-N3, R-S1, R-R1, R-R2 v1.3 berlaku tanpa perubahan (lihat `A01_v1_3_PROTOKOL.md` bagian 4).
- Hasil `--selftest` bukan temuan.

### Konsekuensi yang disepakati sebelum run (untuk pembingkaian artikel)

| Hasil PC | Pembacaan yang diizinkan di artikel |
|---|---|
| PC-1 terpenuhi | Protokol peka pada sinyal kuat; stabilitas yang tidak terbedakan dari null pada data nyata dibaca sebagai: sinyal data ini terlalu lemah, bukan protokol yang tumpul. |
| PC-1 tidak terpenuhi | Protokol tidak terbukti peka pada rancangan ini; hasil data nyata "tidak terbedakan dari null" tidak boleh ditafsirkan sebagai tidak adanya sinyal; keterbatasan protokol dilaporkan sebagai temuan. |
| PC-2 terpenuhi | Boleh menyatakan stabilitas penjelasan naik bersama kekuatan sinyal pada kontrol semi-sintetik. |
| PC-3 tidak terpenuhi | Boleh menyatakan SHAP tidak memulihkan grup benar secara andal pada n ini; tidak boleh membaca SHAP data nyata sebagai bukti faktor penentu. |

## 5. Batas yang tetap

- Label sintetik berbentuk logistik linear pada 3 grup benar; ini rancangan yang menguntungkan LR dan bukan representasi proses seleksi sungguhan. Kontrol positif tidak membuktikan bahwa data nyata memuat sinyal dan tidak membuktikan penjelasan nyata benar.
- Fitur nyata dipakai sehingga struktur korelasi dan dispersi kolom nyata terbawa, tetapi hanya satu rancangan benar per kohort (K = 3, satu set koefisien); ketergantungan pada pilihan grup benar tidak diuji.
- Null (nyata maupun kontrol) hanya pada pembagian utama; hanya T32; 100 permutasi pada NX; tanpa koreksi multiplisitas kecuali pembacaan sekunder BH.
- Satu institusi, satu dataset.

## 6. Keluaran (hanya agregat)

`posctl_runs.csv`, `posctl_vs_null.csv`, `posctl_design.csv` (memuat nama grup benar dan AUC oracle tercapai; tanpa label sintetik), `nullx_runs.csv`, `run_manifest.json`; dari penerap aturan: `aturan_posctl.json`, `pc5_deteksi_per_level.csv`, `nx1_sel.csv`, `nx1_klaim_dua_kohort.csv`, `aturan_nx.json`.

## 7. Verifikasi yang sudah dilakukan (data sintetis, bukan temuan)

- Mode `nullx` untuk permutasi 0–1 identik dengan `run_null` v1.3 (selisih maksimum 0,0).
- Mode `posctl` deterministik (dua run identik, selisih 0,0).
- Kalibrasi: AUC oracle tercapai 0,551 / 0,651 / 0,752 / 0,850 / 0,951 untuk target 0,55 / 0,65 / 0,75 / 0,85 / 0,95; 0,579 untuk target 0,58 pada ukuran kohort 2024; toleransi 0,011.
- Pemulihan: atribusi sempurna pada grup benar menghasilkan top-3 = 1,0.
- Penerap aturan berjalan pada keluaran uji untuk kedua mode (nilai tidak bermakna: R dan P kecil).
- Pada uji sintetis kecil (R = 4, P = 4), stabilitas teramati melampaui null jelas pada level 0,85 untuk LR; ini hanya memeriksa bahwa kode bekerja, bukan hasil.
