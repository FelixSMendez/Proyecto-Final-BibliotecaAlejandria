export function LogoMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark ${compact ? 'brand-mark--compact' : ''}`} aria-label="La Biblioteca de Alejandría">
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M8 23 32 10l24 13M13 25h38M17 27v19m10-19v19m10-19v19m10-19v19M11 49h42M7 54h50" />
      </svg>
      {!compact && <span>La Biblioteca<br />de Alejandría</span>}
    </div>
  )
}
