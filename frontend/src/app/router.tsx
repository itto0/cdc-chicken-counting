import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";

const DashboardPage = lazy(() => import("@/features/overview/pages/DashboardPage"));
const LiniProduksiPage = lazy(() => import("@/features/livestream/pages/LiniProduksiPage"));
const AlarmPage = lazy(() => import("@/features/alarms/pages/AlarmPage"));
const LaporanPage = lazy(() => import("@/features/reports/pages/LaporanPage"));
const PengaturanPage = lazy(() => import("@/features/settings/pages/PengaturanPage"));

const PageLoader = () => (
  <div
    role="status"
    aria-label="Memuat halaman..."
    className="flex items-center justify-center min-h-[300px]"
  >
    <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

function RouteErrorBoundary() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-6 text-center">
      <h2 className="text-xl font-semibold text-slate-900 mb-2">Terjadi Kesalahan</h2>
      <p className="text-sm text-slate-500 mb-4">Gagal memuat halaman atau terjadi masalah koneksi.</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="px-4 py-2 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 transition-colors"
      >
        Muat Ulang
      </button>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<PageLoader />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: "lini-produksi",
        element: (
          <Suspense fallback={<PageLoader />}>
            <LiniProduksiPage />
          </Suspense>
        ),
      },
      {
        path: "alarm",
        element: (
          <Suspense fallback={<PageLoader />}>
            <AlarmPage />
          </Suspense>
        ),
      },
      {
        path: "laporan",
        element: (
          <Suspense fallback={<PageLoader />}>
            <LaporanPage />
          </Suspense>
        ),
      },
      {
        path: "pengaturan",
        element: (
          <Suspense fallback={<PageLoader />}>
            <PengaturanPage />
          </Suspense>
        ),
      },
      {
        path: "*",
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
