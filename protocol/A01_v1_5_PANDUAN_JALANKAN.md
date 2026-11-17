# A01 protokol v1.5 — panduan menjalankan (data UCI)

Semua perintah dijalankan di PowerShell, di folder kerja `search`. Data UCI bersifat publik, jadi semua keluaran boleh dikirim utuh.

## 0. Persiapan (sekali)

Pastikan berkas ini ada di folder `search`:
- `A01_shap_stability_v1_3.py` (sudah ada dari tahap sebelumnya)
- `A01_uci_v1_5.py` dan `A01_v15_aturan.py` (baru)
- `data_uci\data.csv` (dari arsip UCI)

Cek hash:

```powershell
cd "D:\UNIVERSITAS ADZKIA\PENELITIAN dan PKM\Pelatihan artikel internasional\search"
certutil -hashfile A01_uci_v1_5.py SHA256
certutil -hashfile A01_v15_aturan.py SHA256
certutil -hashfile A01_shap_stability_v1_3.py SHA256
certutil -hashfile data_uci\data.csv SHA256
```

Hasil harus sama dengan:
- `A01_uci_v1_5.py`: lihat `A01_v1_5_FREEZE.json`
- `A01_v15_aturan.py`: lihat `A01_v1_5_FREEZE.json`
- `A01_shap_stability_v1_3.py`: `9ecab5bdd24f710d81dfdffa5cb79bf7ed4a5946dac2a840361b644279cbd5e1`
- `data.csv`: `3ef126de5cefff26eb11fbb4237f1a1401cb64b488e2f1d598c23cedeb4c45ae`

Bila berbeda, jangan jalankan. Di setiap jendela PowerShell baru:

```powershell
cd "D:\UNIVERSITAS ADZKIA\PENELITIAN dan PKM\Pelatihan artikel internasional\search"
$u = "data_uci\data.csv"
$env:PYTHONWARNINGS = "ignore"
```

## 1. Uji pilot (beberapa menit; bukan hasil)

```powershell
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s1 --null_P 1 --null_R 5 --out pilot_v15
```

Kirim angka detik yang muncul di layar. Dari situ saya hitung perkiraan waktu tahap berikutnya. Folder `pilot_v15` tidak dipakai di naskah.

## 2. Tahap utama (R = 100)

```powershell
python A01_uci_v1_5.py --mode main --data $u --samples UCI_s1,UCI_s2,UCI_s3,UCI_s4,UCI_s5 --R 100 --out hasil_A01_v15_main_sub
python A01_uci_v1_5.py --mode main --data $u --samples UCI_full --R 100 --out hasil_A01_v15_main_full
```

## 3. Tahap null

Satu perintah per subsampel; boleh dijalankan bergantian atau di beberapa jendela sekaligus bila komputer kuat.

```powershell
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s1 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s1
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s2 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s2
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s3 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s3
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s4 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s4
python A01_uci_v1_5.py --mode null --data $u --samples UCI_s5 --null_P 100 --null_R 25 --out hasil_A01_v15_null_s5
python A01_uci_v1_5.py --mode null --data $u --samples UCI_full --null_P 20 --null_R 25 --out hasil_A01_v15_null_full
```

Keluaran baru tersimpan setelah perintah selesai penuh. Jangan matikan komputer selama berjalan.

## 4. Terapkan aturan beku

```powershell
python A01_v15_aturan.py --main_sub hasil_A01_v15_main_sub --main_full hasil_A01_v15_main_full --null hasil_A01_v15_null_s1,hasil_A01_v15_null_s2,hasil_A01_v15_null_s3,hasil_A01_v15_null_s4,hasil_A01_v15_null_s5,hasil_A01_v15_null_full --out aturan_v15
```

## 5. Yang dikirim

Isi folder `aturan_v15`, ditambah `stability_summary.csv` dan `run_manifest.json` dari setiap folder `hasil_A01_v15_*`.
