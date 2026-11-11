import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthProvider'
import { AppShell } from './components/AppShell'
import { LoadingState } from './components/PageState'

// Cada módulo se descarga solo cuando el usuario visita su ruta.
const AdminPage = lazy(() => import('./pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const CatalogPage = lazy(() => import('./pages/CatalogPage').then((module) => ({ default: module.CatalogPage })))
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((module) => ({ default: module.HistoryPage })))
const LibrarianPage = lazy(() => import('./pages/LibrarianPage').then((module) => ({ default: module.LibrarianPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })))
const RecommendPage = lazy(() => import('./pages/RecommendPage').then((module) => ({ default: module.RecommendPage })))
const ResearchPage = lazy(() => import('./pages/ResearchPage').then((module) => ({ default: module.ResearchPage })))

function ProtectedLayout() {
  const { user, loading } = useAuth()
  if (loading) return <div className="fullscreen-state"><LoadingState label="Abriendo la biblioteca…" /></div>
  if (!user) return <Navigate to="/login" replace />
  return <AppShell><Outlet /></AppShell>
}

function AdminRoute() {
  const { user } = useAuth()
  return user?.role_code === 'admin' ? <AdminPage /> : <Navigate to="/catalog" replace />
}

export default function App() {
  return (
    <Suspense fallback={<div className="fullscreen-state"><LoadingState label="Preparando la sala…" /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<Navigate to="/catalog" replace />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/librarian" element={<LibrarianPage />} />
          <Route path="/recommend" element={<RecommendPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/admin" element={<AdminRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
