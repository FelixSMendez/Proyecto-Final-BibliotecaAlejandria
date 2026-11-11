import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  BookCopy,
  BookOpen,
  Clock3,
  Library,
  LogOut,
  Menu,
  Search,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthProvider'
import { api } from '../lib/api'
import type { UsageSummary } from '../types/api'
import { LogoMark } from './LogoMark'

const mainNavigation = [
  { to: '/catalog', label: 'Catálogo', icon: BookOpen },
  { to: '/librarian', label: 'Bibliotecario', icon: Library },
  { to: '/recommend', label: 'Recomendar', icon: Sparkles },
  { to: '/research', label: 'Investigar', icon: Search },
  { to: '/history', label: 'Historial', icon: Clock3 },
]

export function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const usage = useQuery({
    queryKey: ['usage'],
    queryFn: () => api<UsageSummary>('/usage/me'),
  })

  const closeMenu = () => setMenuOpen(false)
  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <button className="mobile-menu-button" onClick={() => setMenuOpen(true)} aria-label="Abrir navegación">
        <Menu />
      </button>
      {menuOpen && <button className="sidebar-scrim" onClick={closeMenu} aria-label="Cerrar navegación" />}
      <aside className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}>
        <button className="sidebar-close" onClick={closeMenu} aria-label="Cerrar navegación"><X /></button>
        <LogoMark />
        <nav className="sidebar-nav" aria-label="Navegación principal">
          {mainNavigation.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={closeMenu} className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>
              <Icon size={21} strokeWidth={1.7} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {user?.role_code === 'admin' && (
            <NavLink to="/admin" onClick={closeMenu} className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>
              <BarChart3 size={21} strokeWidth={1.7} />
              <span>Administración</span>
            </NavLink>
          )}
          <div className="usage-meter">
            <div><BookCopy size={17} /><span>Consumo mensual</span></div>
            <div className="usage-track"><span style={{ width: `${Math.min(usage.data?.usage_percent ?? 0, 100)}%` }} /></div>
            <small>{usage.data ? `${usage.data.tokens_remaining.toLocaleString('es-GT')} tokens disponibles` : 'Consultando cuota'}</small>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <LogoMark compact />
          <div className="topbar-account">
            <div className="account-avatar"><UserRound size={18} /></div>
            <div>
              <strong>{user?.display_name}</strong>
              <span>{user?.role_code === 'admin' ? 'Administrador' : 'Lector'}</span>
            </div>
            <button onClick={handleLogout} className="icon-button" title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={19} /></button>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  )
}
