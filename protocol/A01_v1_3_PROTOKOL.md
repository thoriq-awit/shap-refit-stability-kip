# A01 — Protokol v1.3 (amandemen pasca-hasil v1.2)

Dibekukan: 2026-10-21T01:04:39Z (sebelum ada hasil v1.3). Skrip: `A01_shap_stability_v1_3.py`, SHA-256 `9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1`. Skrip pemeriksa: `A01_v13_cek.py`, SHA-256 `3c5ca433d7b49d1db5c3f069446bcfd820942d1896d77e9819b5e6a8fe4cdb04`.

## 1. Mengapa v1.3

Hasil v1.2 (50 konfigurasi, agregat) sah dan reproduksinya eksak, tetapi punya dua kelemahan yang menghalangi klaim di artikel:
1. AUC internal model lemah (T32: 0,52–0,59). Tanpa pembanding model yang tidak punya sinyal, angka stabilitas tidak bisa dibaca sebagai "stabil" atau "tidak stabil". Pembanding yang dipakai v1.2 hanya baseline peluang analitik (Jaccard) dan acuan nominal 0,5 (sign), bukan baseline empiris.
2. Perbedaan antar varian dan kecukupan R belum punya ukuran ketidakpastian; studi benih pembagian belum mencakup T32.

## 2. Status (wajib diungkap di Methods)

v1.3 disusun SETELAH peneliti melihat hasil v1.2, jadi seluruhnya analisis tambahan pasca-hasil. Yang tetap: aturan fitur, urutan kolom, kunci acak, metrik, dan keluaran mode v1.2 (uji sintetis: selisih 0,0 terhadap v1.2). Yang ditambah: tiga mode/opsi di bawah. Data 2025 tidak dibaca.

## 3. Yang ditambahkan dan pertanyaan yang dijawab

| Tahap | Opsi skrip | Pengaturan beku | Menjawab |
|---|---|---|---|
| N1 | `--null_P 20 --null_R 25` pada `--variants T32` | 20 permutasi label latih; 25 refit bootstrap per permutasi; hanya LR/RF/XGB bootstrap; baris latih/evaluasi sama dengan analisis utama; AUC pada label evaluasi asli | Apakah stabilitas teramati melebihi stabilitas model tanpa sinyal? (RQ1, RQ4 caveat) |
| S1 | `--split_seeds 101,102,103,104,105 --R 30` pada `--variants T32` | benih dan R sama dengan studi v1.1 untuk primary dan C; lima konfigurasi | Seberapa besar variasi karena pembagian evaluasi? (RQ2) |
| R1 | `--R 200 --rsweep --configs LR/boot,RF/boot,XGB/boot` pada `--variants T32` | prefiks R = 25, 50, 100, 200; blok terpisah 50 | Apakah R = 100 cukup? Berapa galat Monte Carlo refit? (O5) |
| N2/R2 | sama dengan N1 dan R1 pada `--variants E_blok_rumah` | sama | Apakah selisih T32 vs E (blok rumah/utilitas) melebihi galat Monte Carlo dan rentang null? (RQ3) |

Urutan prioritas N1 → S1 → R1 → N2/R2. Tahap yang tidak sempat dijalankan dilaporkan sebagai "tidak dijalankan"; tidak ada tahap yang dipilih atau dilewati berdasarkan hasil tahap lain.

Rincian pembanding null: untuk tiap permutasi m, label latih diacak (`default_rng([SEED, kode_varian, tahun, 7002, m]).permutation`), kelas tetap seimbang; refit bootstrap memakai kunci acak `[SEED, indeks_konfigurasi, r, kode_varian, tahun, 7001, m]`. Nilai teramati dihitung ulang pada Rn refit pertama dengan kunci acak identik v1.2 (jadi sama dengan prefiks Rn dari run utama; diverifikasi oleh `A01_v13_cek.py`). R yang sama (Rn = 25) dipakai di teramati dan null agar statistik berpasangan sebanding.

## 4. Aturan keputusan (ditetapkan sebelum run)

- **R-N1 (null).** Per kohort × konfigurasi bootstrap × metrik inti (Spearman global, Jaccard top-5, Spearman lokal median, Jaccard top-3 lokal median, sign consistency "all" median): "di atas null" bila nilai teramati melebihi seluruh 20 nilai null (p satu sisi = 1/21 ≈ 0,048); "di bawah null" bila lebih kecil dari seluruhnya; selain itu "tidak terbedakan dari null". Klaim "stabilitas melebihi tingkat model tanpa sinyal" untuk suatu konfigurasi hanya boleh bila "di atas null" pada KEDUA kohort. Seluruh tabel dilaporkan; tanpa koreksi multiplisitas; pembacaan deskriptif.
- **R-N2.** Bila sebagian besar sel metrik global "tidak terbedakan dari null", Results menyatakan stabilitas SHAP di data ini tidak terbedakan dari model berlabel acak, dan bukan klaim bahwa penjelasan dapat diandalkan. Angka stabilitas lalu dibingkai sebagai baseline pengembangan untuk bendera "low-consistency" disertasi, dengan ambang yang berangkat dari rentang null (bukan angka bebas).
- **R-N3.** AUC null dilaporkan di samping AUC teramati (acuan ≈ 0,5); selisihnya = ukuran sinyal.
- **R-S1.** Rentang min–maks tiap metrik lintas lima benih pembagian dilaporkan per konfigurasi × kohort. Selisih antar varian pada tangga hanya boleh disebut berarti bila lebih besar daripada rentang benih pembagian T32; selain itu ditulis "dalam rentang variasi pembagian".
- **R-R1.** R = 100 dianggap cukup bila |metrik(R=100) − metrik(R=200)| ≤ 0,02 pada kelima metrik inti di semua konfigurasi rsweep. Ambang 0,02 adalah ambang kerja peneliti, bukan standar literatur [EVIDENCE REQUIRED bila ingin dikutip]. Simpangan baku antar empat blok 50 dilaporkan sebagai galat Monte Carlo refit saja; ia tidak mencakup ketidakpastian sampling data pendaftar.
- **R-R2.** Selisih T32 vs E pada konfigurasi bootstrap disebut melebihi galat Monte Carlo hanya bila rata-rata selisih antar blok lebih besar dari dua kali galat baku selisih (blok tak berpasangan) pada kedua kohort. Ini bukan uji hipotesis populasi.
- Hasil dari `--selftest` (data sintetis) bukan temuan dan tidak boleh masuk Results.

## 5. Batas yang tetap

- Satu institusi, satu dataset; tidak ada ketidakpastian sampling populasi selain variasi pembagian.
- Permutasi hanya mengacak label latih; struktur korelasi antar fitur tetap. Null mengukur stabilitas penjelasan saat tidak ada hubungan fitur–label, bukan seluruh kemungkinan model lemah.
- Tidak ada kontrol positif (data dengan sinyal kuat).
- Ambang bendera "low-consistency" disertasi (Bagian 3.8 proposal) belum ditetapkan; v1.3 hanya menyediakan acuan empirisnya.

## 6. Keluaran (hanya agregat)

`null_runs.csv`, `null_vs_observed.csv`, `stability_summary.csv`, `feature_level.csv`, `rsweep_summary.csv`, `run_manifest.json`. Tidak ada baris per orang.

## 7. Verifikasi yang sudah dilakukan (data sintetis, bukan temuan)

- Mode v1.2 pada v1.3: 55 kolom numerik, selisih maksimum 0,0; `feature_level.csv` identik.
- Null mode: baris `observed` = run utama pada R = Rn (selisih 0,0; AUC juga identik).
- Rsweep: prefiks R = k = run utama pada R = k (0,0); blok 0 = prefiks 4 (0,0); prefiks 8 = baris utama R = 8 (0,0).
- Selftest bawaan (TreeSHAP vs Shapley brute-force; metrik identik/acak; sign consistency) dijalankan ulang bersama uji penuh.
