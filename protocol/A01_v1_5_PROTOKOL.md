# A01 protokol v1.5 — pembanding pada data publik (UCI)

Dibekukan 2026-11-17, sebelum model apa pun dilatih pada data UCI. Skrip: `A01_uci_v1_5.py` dan `A01_v15_aturan.py`. Skrip dasar: `A01_shap_stability_v1_3.py` (tidak diubah; hash diperiksa oleh skrip v1.5).

## 1. Status

- Analisis tambahan pasca-hasil. Disusun setelah seluruh hasil KIP v1.2–v1.4 diketahui.
- Yang sudah dilihat pada data UCI sebelum pembekuan: ukuran data (4.424 × 37), nama kolom, distribusi label (Dropout 1.421, Graduate 2.209, Enrolled 794), jumlah kategori beberapa kolom, statistik ringkas usia dan nilai masuk, dan satu tabel silang deskriptif "Scholarship holder" × "Target". Tidak ada model yang dilatih, tidak ada metrik stabilitas atau AUC yang dihitung pada data UCI.
- Uji logika skrip dilakukan hanya pada data sintetis (`--selftest`), dan pada data UCI hanya sebatas pembacaan kolom dan pembentukan fitur (jumlah baris, kolom, dan grup).

## 2. Alasan

Pada data KIP, model hampir tidak berdaya prediksi (AUC 0,51–0,58) dan stabilitas global SHAP tidak terbedakan dari null. Kontrol positif v1.4 memakai label semi-sintetik. Analisis ini menguji protokol yang sama pada data pendidikan nyata yang sinyalnya diduga lebih kuat, untuk melihat apakah protokol membedakan penjelasan yang stabil di atas null dari yang tidak.

## 3. Data

- Sumber: UCI Machine Learning Repository, "Predict Students' Dropout and Academic Success" (Instituto Politécnico de Portalegre, Portugal). Lisensi CC BY 4.0.
- Rujukan yang diminta pembuat dataset: M. V. Martins, D. Tolledo, J. Machado, L. M. T. Baptista, V. Realinho (2021), "Early prediction of student's performance in higher education: a case study," *Trends and Applications in Information Systems and Technologies*, vol. 1, Advances in Intelligent Systems and Computing, Springer, doi: 10.1007/978-3-030-72657-7_16. Deskripsi data: V. Realinho, J. Machado, L. Baptista, M. V. Martins (2022), "Predicting Student Dropout and Academic Success," *Data* 7(11), 146.
- Berkas: `data.csv` dari arsip UCI, SHA-256 `3ef126de5cefff26eb11fbb4237f1a1401cb64b488e2f1d598c23cedeb4c45ae`. Skrip berhenti bila hash berbeda.

## 4. Label dan fitur

- Label: Dropout = 1, Graduate = 0. Enrolled dikeluarkan karena luarannya belum diketahui. N = 3.630, Dropout 1.421 (39,1%).
- Fitur (17 grup, semuanya diketahui saat pendaftaran):
  - Kategorik (13): Marital status, Application mode, Course, Daytime/evening attendance, Previous qualification, Nacionality, Mother's qualification, Father's qualification, Mother's occupation, Father's occupation, Displaced, Educational special needs, Gender.
  - Numerik (4): Application order, Previous qualification (grade), Admission grade, Age at enrollment.
- Dikeluarkan: 12 kolom unit kurikuler semester 1 dan 2 (terjadi setelah kuliah berjalan); Unemployment rate, Inflation rate, GDP (satu nilai per tahun masuk); Debtor, Tuition fees up to date, Scholarship holder (waktu pengukuran tidak didokumentasikan); International (berulang dengan Nacionality).
- Aturan pengolahan sama dengan v1.3: one-hot dengan kategori < 15 baris digabung menjadi "Lainnya", numerik distandarkan pada sampel yang dianalisis, kolom konstan dibuang, SHAP dijumlahkan per grup.

## 5. Sampel

- UCI_s1 sampai UCI_s5: lima subsampel berstrata label, masing-masing N = 800 (313 Dropout), diambil tanpa pengembalian dengan kunci acak beku `[20261018, 1505, s]`. Ukurannya dipilih agar sebanding dengan kohort KIP (708 dan 829). Subsampel boleh saling beririsan.
- UCI_full: seluruh 3.630 baris, sebagai acuan pengaruh ukuran sampel.

## 6. Analisis

Semua komponen dari v1.3 tanpa perubahan: pembagian latih/evaluasi 70/30 berstrata dengan benih 20261018; tiga model dengan pengaturan tetap; LR analitik dan TreeSHAP; lima metrik (GS, J5, LS, J3, SC); strata dekat batas 20%.

| Tahap | Sampel | Pengaturan |
|---|---|---|
| Utama | UCI_s1–s5, UCI_full | R = 100; LR/boot, RF/seed, RF/boot, XGB/seed, XGB/boot |
| Null | UCI_s1–s5 | P = 100 permutasi label latih, 25 refit bootstrap per permutasi |
| Null | UCI_full | P = 20 permutasi, 25 refit bootstrap |

Nilai teramati untuk perbandingan dengan null dihitung dari 25 refit bootstrap pertama pada label asli (kunci acak sama dengan tahap utama), seperti v1.3.

## 7. Aturan keputusan (beku)

Sel = subsampel × model bootstrap (15 sel). "Di atas null" = p satu sisi ≤ 0,05 dengan P = 100. Ambang adalah ambang kerja penulis, bukan standar literatur.

- **U-1 Sinyal.** "Sinyal kuat" bila AUC di atas null pada ≥ 12 dari 15 sel dan median AUC teramati lintas 15 sel ≥ 0,70.
- **U-2 Pembeda.** "Protokol mendeteksi stabilitas di atas null pada data bersinyal kuat" bila GS di atas null pada ≥ 12/15 sel dan LS di atas null pada ≥ 12/15 sel.
- **U-3 Daya metrik.** Jumlah sel di atas null untuk J5, J3, SC (deskriptif).
- **U-4 Ukuran sampel.** UCI_full di atas null bila teramati > maksimum 20 nilai null; selisih GS dan LS UCI_full terhadap rata-rata lima subsampel (deskriptif).
- **U-5 Sumber variasi.** GS dan LS seed vs bootstrap (deskriptif).
- **Sekunder.** Benjamini–Hochberg q ≤ 0,10 atas 75 sel (5 metrik × 15 sel).

## 8. Komitmen pelaporan

Semua hasil dilaporkan di naskah, apa pun arahnya:

| Hasil | Yang dilaporkan |
|---|---|
| U-1 kuat dan U-2 terpenuhi | Protokol memisahkan data bersinyal kuat (stabil di atas null) dari data KIP (tidak). |
| U-1 kuat, U-2 tidak terpenuhi | Stabilitas tidak terpisah dari null bahkan dengan sinyal kuat; masalahnya bukan hanya sinyal lemah. |
| U-1 tidak kuat | Data UCI dengan fitur saat pendaftaran juga bersinyal lemah; tidak berfungsi sebagai pembanding bersinyal kuat. |

Fitur, label, model, sampel, dan ambang tidak diubah setelah hasil dilihat. Kohort KIP 2025 tetap tidak dibaca.

## 9. Catatan teknis

- Kunci acak refit memakai kode sampel 30–35 sebagai pengganti kode varian v1.3, dan kode tahun 2024 (perilaku bawaan v1.3 untuk kohort selain "2023").
- Ambang kategori langka dan standardisasi dihitung per sampel, sejajar dengan perhitungan per kohort pada KIP.
