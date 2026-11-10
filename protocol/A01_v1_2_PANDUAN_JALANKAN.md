# A01 protokol v1.2: panduan menjalankan di komputer peneliti

Dibuat 2026-10-19. Skrip dibekukan sebelum ada hasil (lihat `A01_v1_2_FREEZE.json`). Analisis penuh tidak bisa dijalankan di lingkungan Claude karena paket `shap` dan `xgboost` tidak dapat dipasang di sana (pypi.org diblokir), dan data mentah memang sebaiknya tidak keluar dari komputer Anda. Uji logika dengan data sintetis sudah lolos di lingkungan Claude (bukan temuan penelitian).

## Yang dijalankan (urutan)

1. Buka PowerShell di folder `search`:
   `cd "<folder kerja>"`
2. Cek hash skrip (harus sama dengan `script_sha256` di `A01_v1_2_FREEZE.json`):
   `certutil -hashfile A01_shap_stability_v1_2.py SHA256`
   Hash yang diharapkan: `2f273800c2ec0eb36c4174aa062655dc2df87e644e7e7db890cb401fa1bd4d27`
   Bila berbeda, jangan jalankan; berarti berkas berubah setelah dibekukan.
3. Pastikan paket ada: `pip install numpy pandas scipy scikit-learn openpyxl shap xgboost`
4. Uji logika (sintetis, beberapa menit): `python A01_shap_stability_v1_2.py --selftest --out selftest_A01_v12 --R 8`
5. Analisis penuh, dua jendela PowerShell paralel (ganti path data sesuai lokasi berkas Anda):
   - Jendela 1: `python A01_shap_stability_v1_2.py --data2023 "<path>\...20231204.xlsx" --cohorts 2023 --out hasil_A01_v12_2023 --R 100`
   - Jendela 2: `python A01_shap_stability_v1_2.py --data2024 "<path>\...20241022.xlsx" --cohorts 2024 --out hasil_A01_v12_2024 --R 100`
   Lima varian (T32, E_blok_rumah, C_tanpa_kabkota, primary, B_tanpa_blok), lima konfigurasi model, R = 100. Perkiraan waktu sekitar 5/3 dari run utama v1.1 di komputer Anda.
6. Cek reproduksi terhadap keluaran v1.1 (varian lama harus mengulang angka lama):
   `python A01_v12_cek_reproduksi.py --lama hasil_A01\stability_summary.csv --baru hasil_A01_v12_2023\stability_summary.csv hasil_A01_v12_2024\stability_summary.csv`
   Selisih mendekati nol berarti reproduksi benar. Selisih kecil bukan nol biasanya karena versi `shap`/`xgboost` berbeda; catat versinya di `run_manifest.json`.

## Setelah selesai

Beri tahu saya di chat. Saya akan mengambil hanya berkas agregat (`stability_summary.csv`, `feature_level.csv`, `run_manifest.json`) dari kedua folder hasil, bukan data mentah, lalu menyusun ringkasan: tangga varian, efek tiap langkah, sign consistency, strata dekat batas, dan pembanding baseline peluang.

## Yang tidak boleh dilakukan

- Jangan ubah skrip setelah hash dicek. Bila perlu perubahan, buat v1.3 dengan hash baru.
- Jangan membuka atau menjalankan data 2025.
- Jangan memilih varian "terbaik" setelah melihat hasil; semua varian dilaporkan.
