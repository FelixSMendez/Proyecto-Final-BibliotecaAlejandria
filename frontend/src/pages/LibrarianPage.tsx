import { useMutation, useQuery } from '@tanstack/react-query'
import { BookOpen, Send, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'

import { AnswerView } from '../components/AnswerView'
import { FormattedText } from '../components/FormattedText'
import { ErrorState } from '../components/PageState'
import { api, ApiError } from '../lib/api'
import type { ConversationDetail, ConversationSummary, RagResponse, RagSource } from '../types/api'

interface TranscriptMessage {
  role: 'user' | 'assistant'
  content: string
}

export function LibrarianPage() {
  const [question, setQuestion] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<TranscriptMessage[]>([])
  const [sources, setSources] = useState<RagSource[]>([])
  const history = useQuery({ queryKey: ['history'], queryFn: () => api<ConversationSummary[]>('/history?limit=100') })
  const selectedHistory = useQuery({
    queryKey: ['history-detail', conversationId],
    queryFn: () => api<ConversationDetail>(`/history/${conversationId}`),
    enabled: Boolean(conversationId) && messages.length === 0,
  })
  useEffect(() => {
    if (selectedHistory.data) {
      setMessages(selectedHistory.data.messages.map((message) => ({ role: message.role, content: message.content })))
      const lastAssistant = [...selectedHistory.data.messages].reverse().find((message) => message.role === 'assistant')
      setSources((lastAssistant?.sources ?? []) as unknown as RagSource[])
    }
  }, [selectedHistory.data])

  const chat = useMutation({
    mutationFn: (value: string) => api<RagResponse>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ question: value, conversation_id: conversationId, top_k: 5 }),
    }),
    onSuccess: (response, value) => {
      setConversationId(response.conversation_id)
      setMessages((current) => [...current, { role: 'user', content: value }, { role: 'assistant', content: response.answer }])
      setSources(response.sources)
      setQuestion('')
    },
  })

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const value = question.trim()
    if (value.length >= 3) chat.mutate(value)
  }

  const librarianHistory = history.data?.filter((item) => item.service_code === 'rag_librarian') ?? []
  const lastAnswer = [...messages].reverse().find((message) => message.role === 'assistant')

  return (
    <div className="agent-page">
      <div className="agent-heading">
        <div><h1>Bibliotecario virtual</h1><p>Pregunta sobre las obras indexadas en el catálogo.</p></div>
        <select value={conversationId ?? ''} onChange={(event) => { setConversationId(event.target.value || null); setMessages([]); setSources([]) }}>
          <option value="">Nueva conversación</option>
          {librarianHistory.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>
      </div>
      <div className="conversation-workspace">
        <section className="transcript">
          {messages.length === 0 && (
            <div className="conversation-intro"><BookOpen size={32} /><h2>Consulta los archivos de Alejandría</h2><p>Las respuestas se construyen únicamente con fuentes recuperadas del catálogo.</p></div>
          )}
          {messages.map((message, index) => (
            <div className={`message message--${message.role}`} key={`${message.role}-${index}`}>
              <span>{message.role === 'user' ? <UserRound /> : <BookOpen />}</span>
              <div><strong>{message.role === 'user' ? 'Tu consulta' : 'Bibliotecario'}</strong><FormattedText value={message.content} /></div>
            </div>
          ))}
          {chat.isPending && <div className="message message--assistant message--pending"><span><BookOpen /></span><div><strong>Bibliotecario</strong><p>Consultando el catálogo…</p></div></div>}
          {chat.isError && <ErrorState message={chat.error instanceof ApiError ? chat.error.message : 'No fue posible completar la consulta.'} />}
          <form className="composer" onSubmit={submit}>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Escribe tu pregunta sobre el catálogo" rows={3} />
            <button className="primary-button" disabled={chat.isPending || question.trim().length < 3}><Send size={18} />Enviar pregunta</button>
          </form>
        </section>
        <aside className="desktop-source-panel">
          <h2>Fuentes consultadas</h2>
          {sources.length === 0 ? <p className="muted-copy">Las fuentes aparecerán aquí después de una consulta.</p> : sources.map((source) => (
            <div className="source-row" key={source.chunk_id}><span className="source-icon"><BookOpen /></span><span><strong>{source.title}</strong><small>Relevancia {source.distance < 0.4 ? 'alta' : 'media'}</small></span></div>
          ))}
        </aside>
      </div>
      {lastAnswer && <div className="mobile-answer-sources"><AnswerView answer={lastAnswer.content} sources={sources.map((source) => ({ title: source.title, url: source.source_url }))} /></div>}
    </div>
  )
}
