# Desain Redesain Dashboard Sesuai Mockup Klien

- **Tanggal:** 2026-10-17
- **Topik:** Penyelarasan UI/UX Dashboard dan Shell Aplikasi Berdasarkan Mockup Klien
- **Status:** Disetujui (Approved)

---

## 1. Ringkasan Eksekutif & Tujuan

Klien mengajukan desain usulan (mockup) untuk antarmuka dashboard utama sistem penghitungan ayam (CDC Chicken Counting). Desain ini memperkenalkan tata letak yang lebih modern, bersih, dan informatif untuk operator industri, yang mencakup:
1. **Header & Shell Aplikasi:** Penambahan ikon lonceng notifikasi alarm aktif, badge profil "Operator Lapangan", dan ikon identitas brand ayam outline.
2. **Baris Metrik Utama (KPI):** 4 kartu metrik informatif (Total Terhitung Hari Ini, Laju Rata-rata, Status Kamera, dan Akurasi Deteksi).
3. **Baris Analisis Produksi:**
   - Kolom Kiri: Tren Penghitungan per Jam dengan area kurva halus berseri biru dan gradient fill.
   - Kolom Kanan: Capaian Target Harian dengan circular progress ring dan progress bar horizontal.
4. **Pratinjau Langsung (Live Preview):** Video streaming deteksi real-time terintegrasi langsung di bagian bawah dashboard dengan timecode/status kontrol.

Dokumen ini mendefinisikan spesifikasi arsitektur, kontrak API, komponen antarmuka, dan rencana pengujian untuk mengimplementasikan mockup tersebut.

---

## 2. Arsitektur Komponen UI & Layout

### 2.1 Shell & Navigasi
- **Sidebar (`frontend/src/components/layout/Sidebar.tsx`):**
  - **Logo Identitas:** Ikon ayam outline SVG di bagian atas sidebar sesuai identitas brand pada mockup.
  - **Daftar Menu:**
    - Dashboard (`/`) — Ikon grid 4 kotak dengan pill rounded background saat aktif.
    - Lini Produksi (`/lini-produksi`) — Ikon hierarki / diagram pohon.
    - Alarm (`/alarm`) — Ikon lonceng alarm.
    - Laporan (`/laporan`) — Ikon dokumen laporan.
    - Pengaturan (`/pengaturan`) — Ikon gear pengaturan.
- **Header (`frontend/src/components/layout/Header.tsx`):**
  - Menggantikan header kosong sebelah kanan dengan:
    - **Tombol Lonceng Notifikasi:** Menampilkan ikon lonceng berbingkai rounded, dengan badge merah penanda jumlah alarm aktif (`active_alarms_count`). Mengklik tombol ini langsung mengarahkan pengguna ke halaman `/alarm`.
    - **Badge Profil Pengguna:** Komponen pill biru tua/slate (`bg-slate-800 text-white`) yang menampilkan nama/peran `"Operator Lapangan"` beserta ikon avatar profil.
- **Dashboard Header (`frontend/src/features/overview/pages/DashboardPage.tsx`):**
  - Judul: `"Ringkasan Hari Ini"` (`text-2xl font-bold text-slate-900`).
  - Posisi `LineSelector` dan `StatusBadge` diletakkan di sisi kanan atas header dashboard secara harmonis agar operator tetap dapat beralih lini produksi (misal: Lini A, Lini B).

---

## 3. Spesifikasi Komponen Halaman Dashboard

### 3.1 Baris 1: 4 Kartu Metrik Utama (`KpiCards.tsx`)
Grid 4 kolom responsif (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`):
1. **Total Ayam Terhitung Hari Ini:**
   - Label: `Total Ayam Terhitung Hari Ini`
   - Nilai: format lokal Indonesia (contoh: `48.250 ekor`)
   - Indikator: Ikon panah naik `↗` berwarna biru/teal dan ikon grafik mini.
2. **Laju Rata-rata:**
   - Label: `Laju Rata-rata`
   - Nilai: `120 ekor/menit` (angka tebal + unit ekor/menit)
   - Indikator: Ikon *speedometer / gauge* di kanan kartu.
3. **Status Kamera:**
   - Label: `Status Kamera`
   - Nilai: Badge/titik hijau `● Online` (atau merah `● Offline` / kuning `● Degraded` sesuai kondisi koneksi kamera).
4. **Akurasi Deteksi:**
   - Label: `Akurasi Deteksi`
   - Nilai: Format koma desimal Indonesia (contoh: `99,2%`)
   - Indikator: Ikon sasaran (*target / bullseye*) di kanan kartu.

### 3.2 Baris 2: Tren Penghitungan & Capaian Target
Grid 2 kolom (`grid-cols-1 lg:grid-cols-3 gap-4` di mana grafik per jam mengambil 2 span kolom dan target harian mengambil 1 span kolom):
1. **Tren Penghitungan per Jam (`HourlyRateChart.tsx`):**
   - Menggunakan ECharts dengan garis kurva halus (*smooth spline*).
   - Area di bawah garis diisi dengan *linear gradient* biru (`rgba(37, 99, 235, 0.25)` ke `rgba(37, 99, 235, 0.01)`).
   - Sumbu X menampilkan jam (`08:00`, `09:00`, dst.) dan tooltip interaktif menampilkan jumlah ayam terhitung pada jam tersebut.
2. **Capaian Target Harian (`TargetAttainmentCard.tsx`):**
   - Menampilkan judul kartu: `Capaian Target Harian`.
   - **Circular Gauge / Donut Ring:** Menampilkan persentase ketercapaian target (contoh: `78%`) di tengah lingkaran dengan indikator melingkar biru.
   - **Progress Bar Horizontal:** Baris kemajuan horizontal di sebelah kanan/bawah lingkaran.
   - **Keterangan Teks:** `Daily goal Achievement` dan angka target (contoh: `62.000 ekor`).

### 3.3 Baris 3: Pratinjau Kamera Langsung (`DashboardLivePreview.tsx`)
- Judul kartu: `Pratinjau Kamera Langsung: [Nama Lini, misal: Lini A]`.
- Menggunakan endpoint stream preview video MJPEG `/api/v1/lines/{line_id}/preview` yang menampilkan deteksi kotak bounding box ayam secara real-time.
- Kontrol playback di bagian bawah video:
  - Tombol Play / Pause.
  - Indikator durasi/timecode (contoh: `19:39 / 18:35` atau badge `LIVE` real-time).
- Penanganan status offline/koneksi terputus dengan opsi "Coba Hubungkan Ulang" (*reconnect*).

---

## 4. Spesifikasi Kontrak Backend & API

### 4.1 Endpoint `GET /api/v1/lines/{line_id}/summary`
Model respons `LineSummaryResponse` diperluas dengan field:
```python
class LineSummaryResponse(BaseModel):
    line_id: str
    period: str
    total_count: int
    target_count: int
    target_attainment_pct: float
    current_speed_cpm: float
    target_speed_cpm: float
    active_alarms_count: int
    camera_status: str
    last_event_time: Optional[str]
    fps: float
    latency_p95_ms: float
    detection_accuracy_pct: float = 99.2  # Field baru
```
Logika kalkulasi di backend:
- Menghitung rata-rata `confidence` dari `CountEvent` untuk lini dan periode terkait:
  ```python
  avg_conf = db.scalar(
      select(func.avg(CountEvent.confidence))
      .where(CountEvent.line_id == line_id)
      .where(CountEvent.ts_utc >= start_time)
  )
  detection_accuracy = round(float(avg_conf) * 100.0, 1) if avg_conf else 99.2
  ```

### 4.2 TypeScript Model (`frontend/src/types/index.ts`)
```typescript
export interface LineSummaryResponse {
  line_id: string;
  period: string;
  total_count: number;
  target_count: number;
  target_attainment_pct: number;
  current_speed_cpm: number;
  target_speed_cpm: number;
  active_alarms_count: number;
  camera_status: "online" | "offline" | "degraded" | string;
  last_event_time: string | null;
  fps: number;
  latency_p95_ms: number;
  detection_accuracy_pct?: number;
}
```

---

## 5. State Management & Real-Time Sync

1. **Sinkronisasi Telemetri SSE:**
   - Data real-time dari hook `useLiveStream(currentLineId)` memperbarui `totalToday`, `liveSpeed`, `fps`, dan `latencyMs` secara instan tanpa perlu menunggu polling.
   - Perhitungan ketercapaian target `attainment_pct` diperbarui otomatis berdasarkan `totalToday` terhadap `target_count`.
2. **Polling Data Berkala:**
   - Ringkasan summary dan data agregasi per jam di-polling setiap 10 detik agar grafik per jam dan metrik agregat tetap mutakhir.
3. **Peralihan Lini:**
   - Saat operator mengganti lini via `LineSelector`, seluruh komponen (KPI cards, grafik tren, target harian, dan pratinjau kamera langsung) beralih ke lini yang dipilih secara mulus.

---

## 6. Rencana Pengujian & Verifikasi

1. **Backend Unit Tests:**
   - Menjalankan `pytest services/api/tests/test_summary_api.py` untuk memverifikasi penambahan field `detection_accuracy_pct` dan nilai default-nya.
2. **Frontend Type Check & Build:**
   - Menjalankan `npm run build` di direktori `frontend` untuk memastikan seluruh tipe data, komponen baru, dan import bebas dari error kompilasi.
3. **Verifikasi Visual & Fungsional:**
   - Memastikan 4 kartu KPI, grafik kurva area per jam, circular progress target, dan pratinjau live stream video ter-render presisi sesuai mockup klien.
   - Memastikan navigasi tombol lonceng alarm dan badge Operator Lapangan berfungsi dengan baik.
