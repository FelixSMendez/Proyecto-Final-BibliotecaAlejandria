import { useQuery } from '@tanstack/react-query'
import { BookOpen, Clock3, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/PageState'
import { api } from '../lib/api'
import type { ConversationDetail, ConversationSummary } from '../types/api'

const serviceNames: Record<string, string> = {
  rag_librarian: 'Bibliotecario',
  book_recommender: 'Recomendación',
  literary_research: 'Investigación',
}

export function HistoryPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const history = useQuery({ queryKey: ['history'], queryFn: () => api<ConversationSummary[]>('/history?limit=100') })
  useEffect(() => {
    if (!selectedId && history.data?.length) setSelectedId(history.data[0].id)
  }, [history.data, selectedId])
  const detail = useQuery({
    queryKey: ['history-detail', selectedId],
    queryFn: () => api<ConversationDetail>(`/history/${selectedId}`),
    enabled: Boolean(selectedId),
  })

  return (
    <div className="history-page">
      <header className="simple-heading"><h1>Historial de conversaciones</h1><p>Regresa a tus consultas, recomendaciones e investigaciones.</p></header>
      {history.isLoading && <LoadingState />}
      {history.isError && <ErrorState message="No fue posible consultar el historial." />}
      {history.data?.length === 0 && <EmptyState title="Aún no hay conversaciones" copy="Haz una pregunta al bibliotecario para iniciar tu archivo personal." />}
      {Boolean(history.data?.length) && (
        <div className="history-workspace">
          <aside className="history-list">
            {history.data!.map((item) => (
              <button key={item.id} onClick={() => setSelectedId(item.id)} className={selectedId === item.id ? 'history-item history-item--active' : 'history-item'}>
                <span>{serviceNames[item.service_code] ?? item.service_name}</span>
                <strong>{item.title || 'Conversación sin título'}</strong>
                <small><Clock3 size={13} />{new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium' }).format(new Date(item.updated_at))} · {item.message_count} mensajes</small>
              </button>
            ))}
          </aside>
          <section className="history-detail">
            {detail.isLoading && <LoadingState />}
            {detail.data?.messages.map((message) => (
              <article className={`history-message history-message--${message.role}`} key={message.id}>
                <span>{message.role === 'user' ? <UserRound /> : <BookOpen />}</span>
                <div><strong>{message.role === 'user' ? 'Tu consulta' : serviceNames[detail.data.service_code] ?? 'Alejandría'}</strong><p>{message.content}</p>{message.sources.length > 0 && <small>{message.sources.length} fuentes · {message.prompt_tokens + message.completion_tokens} tokens</small>}</div>
              </article>
            ))}
          </section>
        </div>
      )}
    </div>
  )
}
