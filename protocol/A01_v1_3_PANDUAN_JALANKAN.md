# A01 protokol v1.3 — panduan menjalankan di komputer peneliti

Dibuat 2026-10-21. Protokol dan aturan keputusan: `A01_v1_3_PROTOKOL.md`. Semua perintah dijalankan di PowerShell di komputer Anda (data mentah tidak boleh keluar dari komputer). Jangan ubah skrip setelah hash dicek.

## 0. Persiapan (sekali, di satu jendela)

```powershell
cd "<folder kerja>"
certutil -hashfile A01_shap_stability_v1_3.py SHA256
certutil -hashfile A01_v13_cek.py SHA256
```
Hash yang diharapkan:
- skrip: `9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1`
- pemeriksa: `3c5ca433d7b49d1db5c3f069446bcfd820942d1896d77e9819b5e6a8fe4cdb04`

Bila berbeda, jangan jalankan. Lalu siapkan jalur data dan matikan peringatan sklearn (lakukan ini di SETIAP jendela baru):

```powershell
$D   = "<folder data>"
$f23 = (Get-ChildItem -LiteralPath $D -Filter "*20231204*.xlsx" | Where-Object { $_.Name -notlike '~$*' } | Select-Object -First 1).FullName
$f24 = (Get-ChildItem -LiteralPath $D -Filter "*20241022*.xlsx" | Where-Object { $_.Name -notlike '~$*' } | Select-Object -First 1).FullName
$env:PYTHONWARNINGS = "ignore"
$f23; $f24
```
Kedua jalur harus tercetak. Bila kosong, periksa nama berkas.

## 1. Uji pilot waktu (beberapa menit; bukan hasil)

```powershell
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants T32 --null_P 2 --null_R 5 --out pilot_waktu_null
```
Baris terakhir tiap model mencetak `(NNs)` = detik untuk 3 himpunan × 5 refit = 15 refit. Perkiraan waktu penuh tahap N1 per model = detik pilot × 35. Kirim ke saya angka detik LR, RF, XGB; saya hitung jadwal totalnya. Folder `pilot_waktu_null` hanya untuk menghitung waktu dan tidak masuk Results.

## 2. Jalankan tahapan (dua jendela PowerShell paralel)

Jendela A mengerjakan 2023 dan jendela B mengerjakan 2024, masing-masing berurutan dari N1 ke R1. Setiap tahap menyimpan keluarannya sendiri begitu selesai, jadi bila dihentikan di tengah, tahap yang sudah selesai tetap aman. Jangan shutdown selama berjalan.

**Jendela A (2023)**
```powershell
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants T32 --null_P 20 --null_R 25 --out hasil_A01_v13_null_T32_2023
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants T32 --split_seeds 101,102,103,104,105 --R 30 --out hasil_A01_v13_split_T32_2023
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants T32 --R 200 --rsweep --configs LR/boot,RF/boot,XGB/boot --out hasil_A01_v13_rsweep_T32_2023
```

**Jendela B (2024)**
```powershell
python A01_shap_stability_v1_3.py --data2024 $f24 --cohorts 2024 --variants T32 --null_P 20 --null_R 25 --out hasil_A01_v13_null_T32_2024
python A01_shap_stability_v1_3.py --data2024 $f24 --cohorts 2024 --variants T32 --split_seeds 101,102,103,104,105 --R 30 --out hasil_A01_v13_split_T32_2024
python A01_shap_stability_v1_3.py --data2024 $f24 --cohorts 2024 --variants T32 --R 200 --rsweep --configs LR/boot,RF/boot,XGB/boot --out hasil_A01_v13_rsweep_T32_2024
```

## 3. Tahap lanjutan (setelah tahap 2 selesai, bila waktu cukup; dijalankan apa pun hasil T32)

Varian E_blok_rumah, untuk menjawab apakah selisih T32 vs E melebihi galat.

Jendela A: ganti `T32` dengan `E_blok_rumah` dan akhiran folder menjadi `_E_2023` pada perintah N1 dan R1 (tanpa tahap benih pembagian). Jendela B sama dengan `$f24`, `--cohorts 2024`, akhiran `_E_2024`.
```powershell
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants E_blok_rumah --null_P 20 --null_R 25 --out hasil_A01_v13_null_E_2023
python A01_shap_stability_v1_3.py --data2023 $f23 --cohorts 2023 --variants E_blok_rumah --R 200 --rsweep --configs LR/boot,RF/boot,XGB/boot --out hasil_A01_v13_rsweep_E_2023
```
(Untuk 2024: `--data2024 $f24 --cohorts 2024` dan `_E_2024`.)

## 4. Cek konsistensi (satu jendela, setelah tahap 2 selesai)

```powershell
python A01_v13_cek.py --v12 hasil_A01_v12_2023_A\stability_summary.csv hasil_A01_v12_2023_B\stability_summary.csv hasil_A01_v12_2024_A\stability_summary.csv hasil_A01_v12_2024_B\stability_summary.csv --rsweep hasil_A01_v13_rsweep_T32_2023\rsweep_summary.csv hasil_A01_v13_rsweep_T32_2024\rsweep_summary.csv
python A01_v13_cek.py --null hasil_A01_v13_null_T32_2023\null_runs.csv hasil_A01_v13_null_T32_2024\null_runs.csv --rsweep hasil_A01_v13_rsweep_T32_2023\rsweep_summary.csv hasil_A01_v13_rsweep_T32_2024\rsweep_summary.csv
```
Kedua cek harus menunjukkan selisih 0,0 (versi paket sama dengan run v1.2). Itu membuktikan 100 refit pertama dari R = 200 sama dengan v1.2 dan nilai "teramati" pada null sama dengan prefiks run utama.

## 5. Setelah selesai

Beri tahu saya di chat. Saya hanya mengambil berkas agregat (`null_runs.csv`, `null_vs_observed.csv`, `stability_summary.csv`, `feature_level.csv`, `rsweep_summary.csv`, `run_manifest.json`) dari folder `hasil_A01_v13_*`, bukan data mentah.

## Yang tidak boleh dilakukan

- Jangan ubah skrip setelah hash dicek; perubahan berarti v1.4 dengan hash baru.
- Jangan membuka atau menjalankan data 2025.
- Jangan memilih atau melewatkan tahap berdasarkan hasil tahap lain; tahap yang tidak sempat dijalankan dilaporkan sebagai tidak dijalankan.
- Jangan membuka berkas xlsx data mentah di Excel selama skrip berjalan (menghasilkan berkas `~$` sementara; perintah di atas sudah mengabaikannya, tetapi berkas yang terkunci bisa gagal dibaca).
