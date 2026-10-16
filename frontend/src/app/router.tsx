import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";

const DashboardPage = lazy(() => import("@/features/overview/pages/DashboardPage"));
const LiniProduksiPage = lazy(() => import("@/features/livestream/pages/LiniProduksiPage"));
const AlarmPage = lazy(() => import("@/features/alarms/pages/AlarmPage"));
const LaporanPage = lazy(() => import("@/features/reports/pages/LaporanPage"));
const PengaturanPage = lazy(() => import("@/features/settings/pages/PengaturanPage"));

const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[300px]">
    <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
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
