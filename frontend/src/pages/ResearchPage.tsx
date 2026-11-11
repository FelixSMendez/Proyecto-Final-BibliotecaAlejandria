import { useMutation } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'

import { AnswerView } from '../components/AnswerView'
import { ErrorState } from '../components/PageState'
import { api, ApiError } from '../lib/api'
import type { ResearchResponse } from '../types/api'

export function ResearchPage() {
  const [query, setQuery] = useState('Influencia del romanticismo y la responsabilidad científica en Frankenstein')
  const research = useMutation({
    mutationFn: () => api<ResearchResponse>('/ai/research', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: 4, max_external_sources: 4 }),
    }),
  })

  return (
    <div className="tool-page">
      <header className="tool-heading"><Search size={30} /><div><h1>Investigación literaria</h1><p>Contrasta el catálogo con fuentes bibliográficas externas.</p></div></header>
      <form className="research-form" onSubmit={(event) => { event.preventDefault(); if (query.trim().length >= 3) research.mutate() }}>
        <textarea rows={3} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Autor, obra, corriente o tema" />
        <button className="primary-button" disabled={research.isPending}>{research.isPending ? 'Consultando fuentes…' : 'Iniciar investigación'}</button>
      </form>
      <div className="source-notice"><strong>Fuentes transparentes.</strong><span>El resultado separa el catálogo interno, Open Library y Wikipedia.</span></div>
      {research.isError && <ErrorState message={research.error instanceof ApiError ? research.error.message : 'No fue posible completar la investigación.'} />}
      {research.data && <section className="result-section"><AnswerView answer={research.data.answer} sources={research.data.sources.map((source) => ({ title: source.title, provider: source.provider.replace('_', ' '), url: source.url }))} /></section>}
    </div>
  )
}
