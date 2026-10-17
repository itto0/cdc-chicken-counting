# Desain Redesain Halaman Lini Produksi (Live Monitoring) Sesuai Mockup Klien

## 1. Ringkasan Eksekutif & Tujuan

Dokumen desain ini merinci spesifikasi teknis untuk mengimplementasikan halaman pemantauan langsung konveyor ayam potong (**Live Monitoring / Lini Produksi**) pada rute `/lini-produksi` agar 100% selaras dengan desain mockup klien ([Image 1]).

Desain ini menggabungkan:
1. **Header**: Judul kontekstual dinamis (`Live Monitoring: [Nama Lini]`) dengan `LineSelector` terintegrasi.
2. **Video Monitor & Overlay**: Wadah streaming video deteksi ayam potong dengan overlay bar gelap bertuliskan hitungan langsung (`Terhitung: [totalToday]`).
3. **Status Sistem (System Status)**: Kartu 3 metrik terpisah (FPS, Latensi, Status Edge) dengan penanda status tri-state (*Online / Degraded / Offline*).
4. **Alarm & Notifikasi (Live Alarms)**: Kartu daftar alarm aktif lini berjalan dengan indikator keparahan (*Kritis / Peringatan*), pesan alarm, dan format waktu WIB.
5. **Matriks Ambang Batas (Threshold Matrix)**: Tabel referensi batas operasional pabrik yang memuat parameter peringatan dan kritis.

---

## 2. Arsitektur Komponen Frontend

Struktur folder komponen di `frontend/src/features/livestream/`:

```
frontend/src/features/livestream/
├── components/
│   ├── LiveVideoMonitor.tsx       # Player MJPEG dengan overlay bar "Terhitung: [Jumlah]" & kontrol
│   ├── SystemStatusCard.tsx       # Kartu 3 kolom: FPS, Latensi, Status Edge (tri-state)
│   ├── LiveAlarmsCard.tsx         # Daftar alarm & notifikasi aktif untuk lini berjalan
│   ├── ThresholdMatrixCard.tsx    # Tabel standar referensi matriks batas operasional
│   ├── VideoPlayer.tsx            # (Existing component / refactored atau disesuaikan)
│   └── StreamMetrics.tsx          # (Existing component / dipertahankan untuk backward compatibility)
└── pages/
    └── LiniProduksiPage.tsx       # Halaman utama menyatukan seluruh sub-komponen
```

---

## 3. Spesifikasi Rinci Setiap Komponen

### 3.1 Header Halaman (`LiniProduksiPage.tsx`)
* **Judul**: `"Live Monitoring: " + (selectedLine?.name || currentLineId || "Lini A")`.
* **LineSelector**: Terintegrasi di sisi kanan header, memungkinkan operator mengganti lini produksi secara dinamis.
* **State Source**: Mengambil `currentLineId`, `lines`, dan `isConnected` dari `AppContext`.

### 3.2 Komponen `LiveVideoMonitor.tsx`
* **Wadah Card**:
  * Judul: `"Pratinjau Kamera Langsung"`.
  * Background kartu putih dengan border `border-slate-200/80 shadow-xs rounded-2xl`.
  * Viewport video rasio aspek responsif (`aspect-[16/10]` atau `aspect-[16/9]`), latar gelap `bg-slate-950 rounded-xl overflow-hidden relative`.
* **Streaming MJPEG**:
  * Endpoint URL: `/api/v1/lines/{line_id}/preview` dengan cache-busting `?retry={nonce}` saat tombol hubungkan ulang ditekan.
  * Dukungan play/pause: Ketika di-pause, elemen `<img>` di-unmount untuk memutus koneksi HTTP streaming server guna menghemat bandwidth.
* **Overlay Bar "Terhitung"**:
  * Diposisikan di bagian bawah video (`w-full bg-[#1e293b]/90 text-white py-2.5 px-4 flex items-center justify-center`).
  * Teks: `"Terhitung: " + (totalToday ?? 0).toLocaleString("id-ID")` (contoh: `"Terhitung: 12.480"`).
  * Tipografi: `text-xl sm:text-2xl font-bold tracking-tight text-white`.
* **Overlay Penanganan Status**:
  * Ketika koneksi terputus atau video error: Menampilkan pesan status *"Kamera offline / terputus"* dan tombol *"Hubungkan Ulang"*.

### 3.3 Komponen `SystemStatusCard.tsx`
* **Wadah Card**:
  * Judul: `"Status Sistem"`.
  * Background putih, `rounded-2xl border border-slate-200/80 shadow-xs p-5`.
* **Layout 3 Kolom Bersekat**:
  1. **FPS**:
     * Label: `"FPS"` (`text-xs text-slate-500 font-medium`).
     * Nilai: Nilai dinamis dari telemetri live stream, misal `30` (`text-2xl font-bold text-slate-900`).
  2. **Latensi**:
     * Label: `"Latensi"` (`text-xs text-slate-500 font-medium`).
     * Nilai: Nilai latensi dari live stream, misal `42 ms` (`text-2xl font-bold text-slate-900`).
  3. **Status Edge**:
     * Label: `"Status Edge"` (`text-xs text-slate-500 font-medium`).
     * Indikator Tri-State:
       * `Online`: Titik hijau `bg-emerald-500 ring-4 ring-emerald-100` + teks `Online` (`text-emerald-700 font-bold`).
       * `Degraded`: Titik amber `bg-amber-500 ring-4 ring-amber-100` + teks `Degraded` (`text-amber-700 font-bold`).
       * `Offline`: Titik merah `bg-rose-500 ring-4 ring-rose-100` + teks `Offline` (`text-rose-700 font-bold`).

### 3.4 Komponen `LiveAlarmsCard.tsx`
* **Wadah Card**:
  * Judul: `"Alarm & Notifikasi"`.
  * Background putih, `rounded-2xl border border-slate-200/80 shadow-xs p-5`.
* **Data & Polling**:
  * Menggunakan `alarmsApi.list(currentLineId)` setiap 10 detik.
  * Memfilter alarm aktif (`status !== "RESOLVED"`).
  * Batasi hingga 5 alarm terbaru untuk menjaga kerapian tata letak kartu.
* **Daftar Alarm**:
  * Tiap item menampilkan:
    * **Indikator Severitas**:
      * `CRITICAL`: Titik merah bercahaya + teks `Kritis` berwarna merah bold (`text-rose-600`).
      * `WARNING`: Titik amber bercahaya + teks `Peringatan` berwarna kuning/amber bold (`text-amber-600`).
    * **Pesan Alarm**: Teks deskripsi (misal: `"Kamera offline"`, `"Laju produksi di bawah target"`).
    * **Timestamp**: Tanggal dan waktu dalam format WIB (contoh: `2024-03-18 00:20:08`).
* **Empty State**:
  * Jika tidak ada alarm aktif: Menampilkan ikon centang/shield hijau lembut dengan teks *"Tidak ada alarm aktif pada lini ini"*.

### 3.5 Komponen `ThresholdMatrixCard.tsx`
* **Wadah Card**:
  * Judul: `"Matriks Ambang Batas (Threshold Matrix)"`.
  * Background putih, `rounded-2xl border border-slate-200/80 shadow-xs p-5`.
* **Tabel Standar Operasional**:
  * Header Tabel: `Metrik`, `Peringatan (Amber)`, `Kritis (Red)`.
  * Baris Data (sesuai spesifikasi evaluasi ambang batas pabrik dan mockup):
    1. `Laju Produksi (ekor/menit)` | `< 130` | `< 110`
    2. `Latensi (ms)` | `130` (atau `> 130`) | `110` (atau `> 110`)
    3. `Akurasi Deteksi (%)` | `0.096` (atau `< 96%`) | `0.075` (atau `< 75%`)
    4. `Downtime (menit)` | `17` | `10`
  * Styling:
    * Header tabel bernuansa slate lembut (`bg-slate-50 text-slate-700 text-xs font-semibold`).
    * Kolom Peringatan dengan aksen teks amber `text-amber-600 font-semibold`.
    * Kolom Kritis dengan aksen teks merah `text-rose-600 font-semibold`.
    * Border baris halus dengan padding proporsional.

---

## 4. Keamanan, Penanganan Error, & Aksesibilitas

1. **Keamanan URL & Parameter**:
   * Penggunaan `encodeURIComponent(currentLineId)` dalam query API alarm dan stream endpoint untuk mencegah manipulasi parameter rute.
2. **Koneksi HTTP & Efisiensi Bandwidth**:
   * Pemutusan sambungan gambar MJPEG ketika komponen di-unmount atau di-pause untuk menghindari pemborosan koneksi socket/HTTP server.
3. **Aksesibilitas (A11y)**:
   * Label ARIA pada tombol kontrol (Play, Pause, Hubungkan Ulang).
   * Status dot menggunakan atribut `aria-hidden="true"` dan teks semantik pendamping untuk pembaca layar (*screen readers*).
4. **Indonesian Localization**:
   * Format angka pemisah ribuan titik (`id-ID`) untuk hitungan ayam.
   * Format waktu tanggal yang ramah standar WIB.

---

## 5. Rencana Pengujian

1. **Frontend Compilation & Typecheck**:
   * Menjalankan `npm run build` (`tsc && vite build`) di folder `frontend/` untuk memastikan 0 error tipe TypeScript dan hasil bundle bersih.
2. **Backend Regression Testing**:
   * Menjalankan `py -m pytest services/api/tests/ -v` memastikan endpoint API alarm dan live stream tidak terganggu.
