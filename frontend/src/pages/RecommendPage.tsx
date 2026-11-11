import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'

import { AnswerView } from '../components/AnswerView'
import { ErrorState } from '../components/PageState'
import { api, ApiError } from '../lib/api'
import type { RecommendationResponse } from '../types/api'

export function RecommendPage() {
  const [query, setQuery] = useState('Busco una novela breve que explore la responsabilidad y la identidad')
  const [maxPages, setMaxPages] = useState(350)
  const recommendation = useMutation({
    mutationFn: () => api<RecommendationResponse>('/ai/recommend', {
      method: 'POST',
      body: JSON.stringify({ query, language_code: 'es', max_pages: maxPages, limit: 5 }),
    }),
  })

  return (
    <div className="tool-page">
      <header className="tool-heading"><Sparkles size={30} /><div><h1>Recomendador de lecturas</h1><p>Describe lo que quieres leer y compararemos las obras disponibles.</p></div></header>
      <form className="recommend-form" onSubmit={(event) => { event.preventDefault(); if (query.trim().length >= 3) recommendation.mutate() }}>
        <label className="wide-field"><span>¿Qué te gustaría encontrar?</span><textarea rows={4} value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <label><span>Extensión máxima</span><select value={maxPages} onChange={(event) => setMaxPages(Number(event.target.value))}><option value={200}>Hasta 200 páginas</option><option value={350}>Hasta 350 páginas</option><option value={500}>Hasta 500 páginas</option><option value={1000}>Sin preferencia</option></select></label>
        <button className="primary-button" disabled={recommendation.isPending}>{recommendation.isPending ? 'Comparando obras…' : 'Preparar recomendación'}</button>
      </form>
      {recommendation.isError && <ErrorState message={recommendation.error instanceof ApiError ? recommendation.error.message : 'No fue posible generar recomendaciones.'} />}
      {recommendation.data && (
        <section className="result-section">
          <AnswerView answer={recommendation.data.answer} sources={recommendation.data.recommendations.map((book) => ({ title: book.title, subtitle: book.authors.join(', ') }))} />
          <div className="recommendation-strip">
            {recommendation.data.recommendations.map((book, index) => <article key={book.book_id}><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{book.title}</h3><p>{book.authors.join(', ')}</p><small>{book.genres.join(' · ')}{book.page_count ? ` · ${book.page_count} páginas` : ''}</small></div></article>)}
          </div>
        </section>
      )}
    </div>
  )
}
