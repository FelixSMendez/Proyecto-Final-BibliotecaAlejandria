import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart3, BookCopy, Database, FileText, RefreshCw, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ErrorState, LoadingState } from '../components/PageState'
import { api, ApiError } from '../lib/api'
import type { BulkIndexResult, IndexState, ManualDocument, ReportSummary, UsageReportRow, User } from '../types/api'

type AdminTab = 'overview' | 'index' | 'documents' | 'users'

export function AdminPage() {
  const [tab, setTab] = useState<AdminTab>('overview')
  const queryClient = useQueryClient()
  const summary = useQuery({ queryKey: ['report-summary'], queryFn: () => api<ReportSummary>('/reports/summary') })
  const usage = useQuery({ queryKey: ['report-usage'], queryFn: () => api<UsageReportRow[]>('/reports/usage') })
  const indexStates = useQuery({ queryKey: ['index-states'], queryFn: () => api<IndexState[]>('/rag/books/status') })
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users?limit=200') })
  const documents = useQuery({ queryKey: ['manual-documents'], queryFn: () => api<ManualDocument[]>('/rag/documents') })
  const bulkIndex = useMutation({
    mutationFn: () => api<BulkIndexResult>('/rag/books/index-all', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['index-states'] }),
  })
  const [documentForm, setDocumentForm] = useState({ title: '', content: '', source_url: '' })
  const createDocument = useMutation({
    mutationFn: () => api('/rag/documents', {
      method: 'POST',
      body: JSON.stringify({ ...documentForm, source_url: documentForm.source_url || null }),
    }),
    onSuccess: () => {
      setDocumentForm({ title: '', content: '', source_url: '' })
      queryClient.invalidateQueries({ queryKey: ['manual-documents'] })
    },
  })

  const chartData = (usage.data ?? []).slice().reverse().map((row) => ({
    date: new Intl.DateTimeFormat('es-GT', { month: 'short', day: 'numeric' }).format(new Date(`${row.execution_date}T12:00:00`)),
    tokens: row.total_tokens,
    requests: row.request_count,
  }))

  return (
    <div className="admin-page">
      <header className="simple-heading"><h1>Administración</h1><p>Gobierna el catálogo, el índice y la actividad de la biblioteca.</p></header>
      <nav className="admin-tabs">
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}><BarChart3 />Resumen</button>
        <button className={tab === 'index' ? 'active' : ''} onClick={() => setTab('index')}><Database />Índice RAG</button>
        <button className={tab === 'documents' ? 'active' : ''} onClick={() => setTab('documents')}><FileText />Documentos</button>
        <button className={tab === 'users' ? 'active' : ''} onClick={() => setTab('users')}><UsersRound />Usuarios</button>
      </nav>
      {tab === 'overview' && (
        <section className="admin-overview">
          {summary.isLoading ? <LoadingState /> : summary.data && (
            <div className="metric-row">
              <article><UsersRound /><span>Lectores activos</span><strong>{summary.data.active_users}</strong></article>
              <article><BookCopy /><span>Libros activos</span><strong>{summary.data.active_books}</strong></article>
              <article><BarChart3 /><span>Consultas</span><strong>{summary.data.requests}</strong></article>
              <article><Database /><span>Tokens utilizados</span><strong>{summary.data.total_tokens.toLocaleString('es-GT')}</strong></article>
            </div>
          )}
          <div className="report-chart">
            <div><h2>Actividad reciente</h2><p>Consumo de tokens registrado por servicio y fecha.</p></div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(104,76,44,.22)" /><XAxis dataKey="date" tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: '#f8f1e4', border: '1px solid rgba(104,76,44,.3)' }} /><Bar dataKey="tokens" fill="#173c35" radius={[3, 3, 0, 0]} /></BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
      {tab === 'index' && (
        <section className="admin-section">
          <div className="admin-section-heading"><div><h2>Estado del índice</h2><p>Los documentos desactualizados no participan en respuestas.</p></div><button className="primary-button" onClick={() => bulkIndex.mutate()} disabled={bulkIndex.isPending}><RefreshCw className={bulkIndex.isPending ? 'spin' : ''} />{bulkIndex.isPending ? 'Indexando…' : 'Indexar catálogo'}</button></div>
          {indexStates.isLoading && <LoadingState />}
          {bulkIndex.data && (
            <div className={`index-summary ${bulkIndex.data.failed ? 'index-summary--warning' : ''}`}>
              <strong>{bulkIndex.data.indexed} libros indexados</strong>
              <span>{bulkIndex.data.failed} fallidos · {bulkIndex.data.unchanged} sin cambios</span>
              {bulkIndex.data.failed > 0 && <small>{bulkIndex.data.items.find((item) => item.error)?.error}</small>}
            </div>
          )}
          <div className="data-table">
            <div className="data-row data-row--head"><span>Libro</span><span>Estado</span><span>Fragmentos</span></div>
            {indexStates.data?.map((item) => <div className="data-row" key={item.book_id}><strong>{item.title}</strong><span className={`status-text status-text--${item.status}`}>{item.status === 'current' ? 'Actual' : item.status === 'stale' ? 'Desactualizado' : item.status === 'not_indexed' ? 'Pendiente' : 'Inactivo'}</span><span>{item.chunks_indexed}</span></div>)}
          </div>
          {bulkIndex.isError && <ErrorState message={bulkIndex.error instanceof ApiError ? bulkIndex.error.message : 'No fue posible actualizar el índice.'} />}
        </section>
      )}
      {tab === 'documents' && (
        <section className="admin-section document-admin">
          <form onSubmit={(event) => { event.preventDefault(); createDocument.mutate() }}>
            <h2>Agregar documento interno</h2>
            <label><span>Título</span><input value={documentForm.title} onChange={(event) => setDocumentForm({ ...documentForm, title: event.target.value })} required /></label>
            <label><span>URL de origen</span><input type="url" value={documentForm.source_url} onChange={(event) => setDocumentForm({ ...documentForm, source_url: event.target.value })} /></label>
            <label><span>Contenido</span><textarea rows={8} minLength={20} value={documentForm.content} onChange={(event) => setDocumentForm({ ...documentForm, content: event.target.value })} required /></label>
            <button className="primary-button" disabled={createDocument.isPending}>{createDocument.isPending ? 'Indexando…' : 'Guardar e indexar'}</button>
          </form>
          <div><h2>Documentos disponibles</h2>{documents.isLoading && <LoadingState />}{documents.data?.map((document) => <article className="document-row" key={document.id}><FileText /><div><strong>{document.title}</strong><small>{document.chunks_indexed} fragmentos · {document.is_active ? 'Activo' : 'Inactivo'}</small></div></article>)}</div>
        </section>
      )}
      {tab === 'users' && (
        <section className="admin-section">
          <div className="admin-section-heading"><div><h2>Usuarios</h2><p>Cuentas, roles y cuotas mensuales.</p></div></div>
          {users.isLoading && <LoadingState />}
          <div className="data-table users-table"><div className="data-row data-row--head"><span>Usuario</span><span>Rol</span><span>Consumo</span><span>Estado</span></div>{users.data?.map((user) => <div className="data-row" key={user.id}><span><strong>{user.display_name}</strong><small>{user.email}</small></span><span>{user.role_code === 'admin' ? 'Administrador' : 'Lector'}</span><span>{user.monthly_tokens_used.toLocaleString('es-GT')} / {user.monthly_token_limit.toLocaleString('es-GT')}</span><span className={user.is_active ? 'status-text status-text--current' : 'status-text status-text--inactive'}>{user.is_active ? 'Activo' : 'Inactivo'}</span></div>)}</div>
        </section>
      )}
    </div>
  )
}
