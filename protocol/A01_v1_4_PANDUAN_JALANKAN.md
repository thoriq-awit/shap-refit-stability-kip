# A01 protokol v1.4 — panduan menjalankan di komputer peneliti

Dibuat 2026-10-31. Protokol dan aturan: `A01_v1_4_PROTOKOL.md`. Semua perintah dijalankan di PowerShell di komputer Anda (data mentah tidak boleh keluar dari komputer). Jangan ubah skrip setelah hash dicek.

## 0. Persiapan (sekali)

Salin tiga berkas baru ke folder `search`, di samping skrip v1.3: `A01_posctl_v1_4.py`, `A01_v14_aturan.py`, `uji_v14.py`. Skrip v1.3 (`A01_shap_stability_v1_3.py`) harus tetap ada di folder yang sama.

```powershell
cd "<folder kerja>"
certutil -hashfile A01_posctl_v1_4.py SHA256
certutil -hashfile A01_v14_aturan.py SHA256
certutil -hashfile A01_shap_stability_v1_3.py SHA256
```
Hash yang diharapkan:
- `A01_posctl_v1_4.py`: `dbe5561818fee01cc7fc3804e0d02bef534a09837e690ebdaef08aa6c4c800ee`
- `A01_v14_aturan.py`: `4435dccf336b284fbc22588bfdb6e7807d975febe260c997e8c270ab92078c98`
- `A01_shap_stability_v1_3.py`: `9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1`

Bila berbeda, jangan jalankan. Di SETIAP jendela PowerShell baru:

```powershell
$D   = "<folder data>"
$f23 = (Get-ChildItem -LiteralPath $D -Filter "*20231204*.xlsx" | Where-Object { $_.Name -notlike '~$*' } | Select-Object -First 1).FullName
$f24 = (Get-ChildItem -LiteralPath $D -Filter "*20241022*.xlsx" | Where-Object { $_.Name -notlike '~$*' } | Select-Object -First 1).FullName
$env:PYTHONWARNINGS = "ignore"
$f23; $f24
```

## 1. Uji pilot (beberapa menit; bukan hasil)

```powershell
python A01_posctl_v1_4.py --mode posctl --data2023 $f23 --cohorts 2023 --variants T32 --levels 0.70 --null_P 1 --null_R 3 --out pilot_v14
```
Kirim ke saya seluruh keluaran layar (termasuk baris `grup benar=...` dan angka detik). Folder `pilot_v14` tidak masuk Results. Estimasi saya dari laju v1.3: sekitar 35 menit per level per kohort, jadi sekitar 1 jam 45 menit untuk tiga level per kohort.

## 2. Tahap PC — kontrol positif (prioritas 1; dua jendela paralel)

**Jendela A (2023)**
```powershell
python A01_posctl_v1_4.py --mode posctl --data2023 $f23 --cohorts 2023 --variants T32 --levels 0.58,0.70,0.85 --null_P 20 --null_R 25 --out hasil_A01_v14_posctl_T32_2023
```
**Jendela B (2024)**
```powershell
python A01_posctl_v1_4.py --mode posctl --data2024 $f24 --cohorts 2024 --variants T32 --levels 0.58,0.70,0.85 --null_P 20 --null_R 25 --out hasil_A01_v14_posctl_T32_2024
```
Keluaran tersimpan hanya setelah perintah selesai penuh. Jangan shutdown selama berjalan.

## 3. Tahap N2/R2 — E_blok_rumah (prioritas 2)

Pakai perintah di `A01_v1_3_PANDUAN_JALANKAN.md` bagian 3 (skrip v1.3, tidak berubah).

## 4. Tahap NX — null diperluas (prioritas 3; boleh dijalankan semalam)

Perkiraan sekitar 2 jam 15 menit per kohort.

**Jendela A (2023)**
```powershell
python A01_posctl_v1_4.py --mode nullx --data2023 $f23 --cohorts 2023 --variants T32 --nullx_from 20 --nullx_to 100 --null_R 25 --out hasil_A01_v14_nullx_T32_2023
```
**Jendela B (2024)**
```powershell
python A01_posctl_v1_4.py --mode nullx --data2024 $f24 --cohorts 2024 --variants T32 --nullx_from 20 --nullx_to 100 --null_R 25 --out hasil_A01_v14_nullx_T32_2024
```

## 5. Penerapan aturan (setelah tahap terkait selesai)

```powershell
python A01_v14_aturan.py --posctl hasil_A01_v14_posctl_T32_2023\posctl_vs_null.csv hasil_A01_v14_posctl_T32_2024\posctl_vs_null.csv --out aturan_v14_posctl
python A01_v14_aturan.py --null13 hasil_A01_v13_null_T32_2023\null_runs.csv hasil_A01_v13_null_T32_2024\null_runs.csv --nullx hasil_A01_v14_nullx_T32_2023\nullx_runs.csv hasil_A01_v14_nullx_T32_2024\nullx_runs.csv --out aturan_v14_nullx
```

## 6. Setelah selesai

Beri tahu saya di chat. Saya hanya mengambil berkas agregat dari folder `hasil_A01_v14_*` dan `aturan_v14_*`, bukan data mentah.

## Yang tidak boleh dilakukan

- Jangan ubah skrip setelah hash dicek; perubahan berarti v1.5 dengan hash baru.
- Jangan membuka atau menjalankan data 2025.
- Jangan memilih atau melewatkan tahap berdasarkan hasil tahap lain; tahap yang tidak sempat dijalankan dilaporkan sebagai tidak dijalankan.
- Jangan mengubah `--levels`, `--null_P`, `--null_R` dari nilai di atas pada run yang akan dilaporkan.
- Jangan membuka berkas xlsx data mentah di Excel selama skrip berjalan.
