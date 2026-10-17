# Desain Arsitektur: Redesain Halaman Laporan dan Data Historis

**Tanggal:** 17 Oktober 2026  
**Status:** Disetujui (Approved)  
**Tujuan:** Mengimplementasikan perombakan visual dan fungsional halaman Laporan dan Data Historis (`/laporan`) sesuai mockup klien ([Image 2]), mencakup bilah kontrol filter & pencarian, ekspor laporan resmi (PDF & Excel), 4 kartu KPI ringkasan, dan tabel riwayat penghitungan dengan paginasi interaktif.

---

## 1. Latar Belakang & Kebutuhan

Tampilan halaman Laporan yang ada saat ini (`frontend/src/features/reports/pages/LaporanPage.tsx`) masih berupa prototipe dasar dengan tombol ekspor CSV sederhana dan tabel 4 kolom. Mockup klien [Image 2] menetapkan standar visual dan fungsional baru:
1. **Bilah Kontrol Terintegrasi**: Filter periode ("Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir"), filter lini ("Semua Lini" atau lini individual), kolom pencarian instan, serta tombol aksi unduh resmi untuk **Ekspor PDF** dan **Ekspor Excel**.
2. **4 Kartu Ringkasan KPI**:
   - Total Ayam Terhitung (e.g. `142.850 ekor`)
   - Rata-rata Laju (e.g. `118 ekor/menit`)
   - Akurasi Rata-rata (e.g. `99,1%`)
   - Total Waktu Operasi (e.g. `18 jam 45 mnt`)
3. **Tabel Riwayat Data Penghitungan**:
   - Kolom lengkap: Waktu / Tanggal, Lini Produksi, Jumlah Terhitung, Laju Rata-rata, Akurasi, dan Status.
   - Paginasi client-side (10 baris per halaman) dengan pencarian instan dan penanganan kondisi kosong (*empty state*).
4. **Dukungan Backend Multi-Lini pada Ekspor Laporan**:
   - Memperbarui `services/api/src/api/reports.py` agar parameter `line_id` mendukung nilai `"all"` atau opsional untuk mengekspor rekapitulasi gabungan seluruh lini produksi pabrik.

---

## 2. Arsitektur Komponen

Struktur modular baru pada `frontend/src/features/reports/`:

```
frontend/src/features/reports/
├── api/
│   └── reports.api.ts            # getCounts & downloadReport (PDF/Excel blob downloader)
├── components/
│   ├── ReportFilterBar.tsx       # Filter periode, filter lini, search box, tombol PDF/Excel
│   ├── ReportKpiCards.tsx        # 4 kartu KPI ringkasan metrik historis
│   └── ReportsTable.tsx          # Tabel riwayat penghitungan 6 kolom + paginasi + search
├── pages/
│   └── LaporanPage.tsx           # Halaman utama merangkai Filter, KPI Cards, dan Tabel
└── index.ts                      # Barrel export
```

---

## 3. Spesifikasi Rinci Antarmuka & Logika

### 3.1 Bilah Kontrol Filter & Ekspor (`ReportFilterBar.tsx`)
- **Kontainer**: `bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 flex flex-wrap items-center justify-between gap-4`.
- **Elemen Sisi Kiri (Filter & Pencarian)**:
  - **Dropdown Periode**:
    - Pilihan: `today` ("Hari Ini"), `7d` ("7 Hari Terakhir"), `30d` ("30 Hari Terakhir").
    - Saat berubah, menghitung rentang `from` dan `to` dalam format ISO 8601 UTC untuk memfilter data historis.
  - **Dropdown Lini**:
    - Pilihan pertama: `"all"` ("Semua Lini").
    - Pilihan berikutnya: Daftar lini aktif yang diambil dari `lines` di `AppContext` (misal: `"line-1"` - Lini 1 Utama, `"line-2"` - Lini 2 Pemotongan).
  - **Input Pencarian**:
    - Input dengan ikon `Search` di sisi kiri (`w-4 h-4 text-slate-400`).
    - Placeholder: `"Cari data..."`.
    - Menyaring baris data tabel secara real-time berdasarkan pencocokan substring nama lini, status, atau waktu.
- **Elemen Sisi Kanan (Aksi Ekspor)**:
  - **Tombol Ekspor PDF**:
    - Varian outline dengan aksen merah: `border-rose-200 text-rose-700 hover:bg-rose-50`.
    - Ikon `FileText` (`w-4 h-4 mr-2 text-rose-600`).
    - Teks: `"Ekspor PDF"`.
    - Memicu pemanggilan API `reportsApi.downloadReport({ format: "pdf", lineId, startTime, endTime })`.
  - **Tombol Ekspor Excel**:
    - Varian outline dengan aksen hijau: `border-emerald-200 text-emerald-700 hover:bg-emerald-50`.
    - Ikon `FileSpreadsheet` (`w-4 h-4 mr-2 text-emerald-600`).
    - Teks: `"Ekspor Excel"`.
    - Memicu pemanggilan API `reportsApi.downloadReport({ format: "xlsx", lineId, startTime, endTime })`.
  - Dilengkapi state `isExporting` (disabled + spinner) saat proses pengunduhan sedang berlangsung untuk mencegah klik berulang.

### 3.2 Empat Kartu Ringkasan KPI (`ReportKpiCards.tsx`)
Grid responsif 4 kolom (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`), masing-masing kartu berlatar putih dengan sudut `rounded-2xl border-slate-200/80 shadow-sm p-5`:
1. **Total Ayam Terhitung**:
   - Ikon: `LineChart` dalam lingkaran `bg-blue-50 text-blue-600`.
   - Nilai: Total akumulasi ayam dari baris data yang difilter, diformat menggunakan `id-ID` (contoh: `142.850 ekor`).
   - Subteks: `"Total periode terpilih"`.
2. **Rata-rata Laju**:
   - Ikon: `Gauge` dalam lingkaran `bg-indigo-50 text-indigo-600`.
   - Nilai: Kecepatan rata-rata dari interval data (contoh: `118 ekor/menit`).
   - Subteks: `"Laju operasional rata-rata"`.
3. **Akurasi Rata-rata**:
   - Ikon: `Target` dalam lingkaran `bg-emerald-50 text-emerald-600`.
   - Nilai: Rata-rata akurasi model AI diformat dengan koma desimal Indonesia (contoh: `99,1%`).
   - Subteks: Status performa deteksi (misal: `"Sangat Baik"`).
4. **Total Waktu Operasi**:
   - Ikon: `Clock` dalam lingkaran `bg-amber-50 text-amber-600`.
   - Nilai: Dihitung dari akumulasi jam/menit interval aktif (contoh: `18 jam 45 mnt` atau `X jam Y mnt`).
   - Subteks: Indikator ketersediaan lini operasional.

### 3.3 Tabel Riwayat Data Penghitungan (`ReportsTable.tsx`)
- **Struktur Kartu**: `rounded-2xl border-slate-200/80 shadow-sm bg-white overflow-hidden`.
- **Header Tabel**:
  - Judul: `"Riwayat Data Penghitungan"` (`text-base font-semibold text-slate-800`).
  - Badge counter data: Menampilkan jumlah entri data terfilter (contoh: `"142 Data"`).
- **Kolom Data**:
  1. **Waktu / Tanggal**: Menampilkan format tanggal dan rentang jam Indonesia (contoh: `17 Okt 2026, 14:00 - 15:00`).
  2. **Lini Produksi**: Menampilkan nama lini yang jelas (contoh: `Lini 1 - Utama`).
  3. **Jumlah Terhitung**: Nilai hitungan dengan format `id-ID` (contoh: `7.120 ekor`).
  4. **Laju Rata-rata**: Nilai kecepatan (contoh: `119 cpm`).
  5. **Akurasi**: Nilai akurasi (contoh: `99,2%`).
  6. **Status**: Badge status berwarna (`Normal` bg-emerald-50 text-emerald-700, `Peringatan` bg-amber-50 text-amber-700, `Kritis` bg-rose-50 text-rose-700).
- **Paginasi Client-Side**:
  - 10 baris per halaman.
  - Teks informasi di kiri bawah: `"Menampilkan X-Y dari Z data"`.
  - Kontrol navigasi di kanan bawah: Tombol *"Sebelumnya"*, tombol nomor halaman (1, 2, 3...), dan tombol *"Berikutnya"*.
  - Tombol nonaktif (`disabled`) pada halaman pertama untuk *Sebelumnya* dan pada halaman terakhir untuk *Berikutnya*.
- **Kondisi Kosong (*Empty State*)**:
  - Jika pencarian atau filter menghasilkan 0 data, menampilkan ikon `Inbox` / `SearchX` dengan pesan ramah: *"Tidak ada data riwayat yang sesuai dengan kriteria filter."*.

---

## 4. Penyesuaian Backend & Integrasi Ekspor

### 4.1 Backend Endpoint `services/api/src/api/reports.py`
- Saat ini `export_report` memiliki signature:
  ```python
  def export_report(
      line_id: str = Query(default="lineA"),
      format: str = Query(default="xlsx"),
      start_time: str | None = Query(default=None),
      end_time: str | None = Query(default=None),
      db: Session = Depends(get_db),
  )
  ```
- **Pembaruan**:
  - Ubah query SQL agar jika `line_id` bernilai `"all"` atau `None`, klausa `where(CountAggregate.line_id == line_id)` dilewati, sehingga menghasilkan agregasi semua lini.
  - Jika `line_id == "all"`, nama file unduhan menjadi `report_semua_lini.xlsx` / `report_semua_lini.pdf`, dan judul dokumen laporan menampilkan `"Semua Lini Produksi"`.
  - Backend tetap 100% backwards-compatible untuk pemanggilan dengan `line_id` tunggal.

### 4.2 Frontend Service `reports.api.ts`
- Menambahkan fungsi helper `downloadReport`:
  ```typescript
  downloadReport: async (params: {
    lineId?: string;
    format: "xlsx" | "pdf";
    startTime?: string;
    endTime?: string;
  }) => Promise<void>
  ```
  Fungsi ini melakukan fetch ke `/api/v1/reports/export`, mengekstrak blob respons biner, membuat elemen tautan `<a download>`, memicu unduhan di peramban, dan melepaskan object URL secara bersih (`URL.revokeObjectURL`).

---

## 5. Rencana Pengujian

1. **Backend Tests**:
   - `services/api/tests/test_reports_export.py`:
     - Verifikasi ekspor XLSX untuk `line_id="all"` menghasilkan status 200 dengan header `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
     - Verifikasi ekspor PDF untuk `line_id="all"` menghasilkan status 200 dengan header `application/pdf`.
     - Verifikasi filter tanggal `start_time` dan `end_time` berfungsi konsisten.
2. **Frontend Typecheck & Build**:
   - Menjalankan `npm run build` (`tsc && vite build`) untuk memastikan kepatuhan tipe TypeScript, nol unused locals, dan bundling produksi yang bersih.
3. **Penyelarasan Desain Visual**:
   - Memastikan hierarki tampilan kartu KPI, bilah filter, dan tabel paginasi sesuai dengan tata letak visual pada mockup [Image 2].
