# Desain Rework Frontend Architecture (Shadcn, Sidebar & Light Theme)

**Tanggal:** 2026-10-16  
**Status:** Disetujui (Approved)  
**Tujuan:** Merestrukturisasi penuh arsitektur frontend web aplikasi pemantauan penghitungan ayam (Lihat.id · Poultry Counter) sesuai acuan `docs/fe-architecture.md` dengan navigasi Sidebar, UI berbasis Shadcn, tema Light (Terang), dan Bahasa Indonesia.

---

## 1. Latar Belakang & Kebutuhan

Struktur kode frontend saat ini menumpuk seluruh tampilan di dalam folder komponen tunggal dengan peralihan tab berbasis state lokal dan tema gelap (`bg-slate-900`). 

Kebutuhan rework:
1. Mengadopsi struktur berbasis domain (*feature-based*) sesuai panduan `docs/fe-architecture.md`.
2. Menggunakan tata letak **Sidebar** di sisi kiri dengan menu berbahasa Indonesia:
   - **Dashboard** (`/`)
   - **Lini Produksi** (`/lini-produksi`)
   - **Alarm** (`/alarm`)
   - **Laporan** (`/laporan`)
   - **Pengaturan** (`/pengaturan`)
3. Menggunakan **Header** yang bersih dan minimal:
   - **Tanpa pemilihan peran (*no role selection*)** di header.
   - **Tanpa badge status (*no status badge*)** di header.
   - Hanya memuat toggle sidebar untuk tampilan mobile dan breadcrumb/judul halaman.
4. Menempatkan **Pemilih Lini Produksi (Line Selector)** dan **Badge Status Koneksi** di dalam konten/toolbar masing-masing halaman yang membutuhkan data lini.
5. Menggunakan **Light Theme (Tema Terang)** yang konsisten dengan estetika desain Shadcn UI (latar belakang `bg-slate-50`, kartu `bg-white`, border `border-slate-200`, dan tipografi berjarak rapi).
6. Menggunakan **React Router DOM** untuk navigasi URL riil dengan *lazy loading* antar halaman.

---

## 2. Struktur Direktori Baru

Struktur `frontend/src/` ditata ulang mengikuti panduan:

```
frontend/
├── src/
│   ├── app/                         # Bootstrapping aplikasi
│   │   ├── App.tsx                  # Root component (Router & Providers)
│   │   ├── router.tsx               # Konfigurasi rute React Router & lazy loading
│   │   └── providers.tsx            # QueryClientProvider, AppProvider, Toaster
│   │
│   ├── features/                    # Modul domain mandiri
│   │   ├── overview/                # Dashboard ringkasan & grafik
│   │   │   ├── api/                 # overview.api.ts, overview.queries.ts
│   │   │   ├── components/          # KpiCards.tsx, HourlyRateChart.tsx, OverviewToolbar.tsx
│   │   │   ├── pages/DashboardPage.tsx
│   │   │   └── index.ts
│   │   ├── livestream/              # Siaran langsung & pemantauan kamera lini
│   │   │   ├── api/                 # livestream.api.ts
│   │   │   ├── components/          # VideoPlayer.tsx, StreamMetrics.tsx, StreamToolbar.tsx
│   │   │   ├── pages/LiniProduksiPage.tsx
│   │   │   └── index.ts
│   │   ├── alarms/                  # Manajemen alarm & riwayat anomali
│   │   │   ├── api/                 # alarms.api.ts, alarms.queries.ts
│   │   │   ├── components/          # AlarmsTable.tsx, AlarmsFilterBar.tsx
│   │   │   ├── pages/AlarmPage.tsx
│   │   │   └── index.ts
│   │   ├── reports/                 # Riwayat penghitungan & ekspor laporan
│   │   │   ├── api/                 # reports.api.ts, reports.queries.ts
│   │   │   ├── components/          # ReportsTable.tsx, ReportsFilterBar.tsx
│   │   │   ├── pages/LaporanPage.tsx
│   │   │   └── index.ts
│   │   └── settings/                # Konfigurasi lini & perangkat
│   │       ├── api/                 # settings.api.ts
│   │       ├── components/          # LineConfigCard.tsx, SystemInfoCard.tsx
│   │       ├── pages/PengaturanPage.tsx
│   │       └── index.ts
│   │
│   ├── components/                  # UI bersama (shared)
│   │   ├── ui/                      # Komponen primitif Shadcn (Button, Card, Badge, Table, Input, Select, Dialog)
│   │   ├── layout/                  # AppShell.tsx, Sidebar.tsx, Header.tsx, PageHeader.tsx, LineSelector.tsx
│   │   └── common/                  # StatusBadge.tsx, EmptyState.tsx, LoadingSpinner.tsx
│   │
│   ├── hooks/                       # Hook bersama (useLiveStream.ts, useMediaQuery.ts)
│   ├── lib/                         # Konfigurasi library & utilitas
│   │   ├── http.ts                  # Klien HTTP fetch dengan auth token & error handler
│   │   ├── queryClient.ts           # Instance TanStack QueryClient terpusat
│   │   └── utils.ts                 # Utilitas kelas Tailwind (cn helper)
│   ├── config/                      # Konfigurasi statis
│   │   ├── navigation.ts            # Definisi menu navigasi sidebar
│   │   ├── env.ts                   # Validasi variabel environment
│   │   └── constants.ts             # Konstanta aplikasi (fallback data, dll.)
│   ├── types/                       # Tipe data DTO & TypeScript global
│   ├── index.css                    # Tailwind CSS base + variabel warna Light Theme
│   └── main.tsx                     # Entry point React Vite
```

---

## 3. Komponen Tata Letak (Layout & Navigation)

### 3.1 Sidebar (`src/components/layout/Sidebar.tsx`)
- Tampil tetap (*sticky/fixed*) di desktop dengan lebar `w-64`, dan laci (*drawer*) responsif di ponsel/tablet.
- Identitas brand di bagian atas:
  - Teks: **Lihat.id** dengan aksen emerald (`text-emerald-600 font-bold`).
  - Subtitle: **Poultry Counter**.
- Item navigasi dibaca dari `src/config/navigation.ts`:
  1. **Dashboard** (`/`) — Ikon: `LayoutDashboard`
  2. **Lini Produksi** (`/lini-produksi`) — Ikon: `Radio`
  3. **Alarm** (`/alarm`) — Ikon: `AlertTriangle`
  4. **Laporan** (`/laporan`) — Ikon: `FileText`
  5. **Pengaturan** (`/pengaturan`) — Ikon: `Settings`
- Status tautan aktif: `bg-slate-100 text-slate-900 font-semibold border-r-2 border-emerald-600` (atau `border-l-2`).

### 3.2 Header (`src/components/layout/Header.tsx`)
- Minimal dan bersih: `h-14 border-b border-slate-200 bg-white px-6 flex items-center justify-between`.
- Sisi Kiri: Tombol pemicu buka-tutup Sidebar di mobile, serta judul/breadcrumb navigasi halaman saat ini.
- Sisi Kanan: Bersih. **Tidak memuat pemilihan role/peran dan tidak memuat badge status koneksi.**

### 3.3 Penempatan Line Selector & Status Koneksi di Konten Halaman
- Komponen `LineSelector` (`src/components/layout/LineSelector.tsx`) diletakkan di dalam toolbar/header konten setiap halaman yang membutuhkan pemilihan lini (`DashboardPage`, `LiniProduksiPage`, `AlarmPage`, `LaporanPage`, `PengaturanPage`).
- Badge status koneksi (`StatusBadge`: TERHUBUNG / TERPUTUS) diletakkan berdampingan dengan pemilih lini di toolbar halaman.

---

## 4. Desain Sistem Tema Terang (Light Theme) & Shadcn UI

### 4.1 Token Warna & Gaya
- Latar Belakang Kanvas: `bg-slate-50`
- Latar Belakang Kartu / Dialog: `bg-white`
- Border: `border-slate-200`
- Teks Utama: `text-slate-900`
- Teks Sekunder / Meta: `text-slate-500`
- Aksen Sukses / Aktif: `text-emerald-600`, `bg-emerald-50`, `border-emerald-200`
- Aksen Peringatan: `text-amber-600`, `bg-amber-50`, `border-amber-200`
- Aksen Bahaya / Error: `text-rose-600`, `bg-rose-50`, `border-rose-200`

### 4.2 Komponen Primitif Shadcn (`src/components/ui/`)
1. `button.tsx`: Varian `default` (slate-900), `outline`, `ghost`, `destructive`, `secondary`.
2. `card.tsx`: `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`.
3. `badge.tsx`: Varian `default`, `secondary`, `outline`, `destructive`, `success`.
4. `table.tsx`: `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`.
5. `input.tsx`: Input teks standar bergaya shadcn.
6. `select.tsx`: Dropdown select yang bersih.

### 4.3 ECharts Light Theme
- Grafik laju penghitungan per jam di Dashboard disesuaikan ke tema terang:
  - Background: transparan
  - Garis bantu sumbu (*splitLine*): `rgba(0, 0, 0, 0.06)`
  - Warna label sumbu: `#64748b` (slate-500)
  - Area warna gradien: gradien halus hijau emerald (`#10b981` ke `#34d399` dengan opasitas rendah).

---

## 5. Konfigurasi Dependensi & Path Alias

1. **Path Alias `@/`:**
   - Dikonfigurasi di `frontend/vite.config.ts` (`resolve.alias: { '@': path.resolve(__dirname, './src') }`).
   - Dikonfigurasi di `frontend/tsconfig.json` (`compilerOptions.paths: { "@/*": ["src/*"] }`).
2. **Dependensi Tambahan:**
   - `react-router-dom`: Untuk routing berbasis URL.
   - `clsx` dan `tailwind-merge`: Untuk helper `cn()` Shadcn.

---

## 6. Rencana Verifikasi

1. **Build & Type Check:**
   Menjalankan `npm run build` di direktori `frontend` untuk memvalidasi tidak ada kesalahan TypeScript atau impor path alias.
2. **Navigasi & Rute URL:**
   Memverifikasi bahwa mengakses `/`, `/lini-produksi`, `/alarm`, `/laporan`, dan `/pengaturan` memuat halaman yang sesuai secara benar.
3. **Fungsionalitas Kontrol Lini:**
   Memverifikasi bahwa memilih lini pada toolbar halaman berhasil memperbarui konteks data dan grafik/tabel yang relevan.
4. **Tampilan UI & Responsivitas:**
   Memverifikasi tampilan tema terang bebas dari glitch warna kontras gelap yang tertinggal dan sidebar responsif di layar mobile/desktop.
