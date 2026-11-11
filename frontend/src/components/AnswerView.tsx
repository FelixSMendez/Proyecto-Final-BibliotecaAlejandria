import { BookOpen, ExternalLink } from 'lucide-react'

import { FormattedText } from './FormattedText'

interface SourceView {
  title: string
  provider?: string
  url?: string | null
  subtitle?: string
}

export function AnswerView({ answer, sources }: { answer: string; sources: SourceView[] }) {
  return (
    <div className="answer-layout">
      <article className="answer-text">
        <FormattedText value={answer} />
      </article>
      <aside className="sources-rail">
        <h2>Fuentes consultadas</h2>
        {sources.length === 0 ? <p className="muted-copy">La respuesta no necesitó fuentes adicionales.</p> : sources.map((source, index) => (
          <a className="source-row" key={`${source.title}-${index}`} href={source.url || undefined} target={source.url ? '_blank' : undefined} rel="noreferrer">
            <span className="source-icon"><BookOpen size={21} /></span>
            <span><strong>{source.title}</strong><small>{source.subtitle || source.provider || 'Catálogo interno'}</small></span>
            {source.url && <ExternalLink size={16} />}
          </a>
        ))}
      </aside>
    </div>
  )
}
