import type { ReactNode } from 'react'

/** Renders the small Markdown subset returned by the AI without injecting HTML. */
export function FormattedText({ value }: { value: string }) {
  return value.split(/\n{2,}/).map((paragraph, paragraphIndex) => (
    <p key={`${paragraph.slice(0, 24)}-${paragraphIndex}`}>
      {paragraph.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex): ReactNode => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={`${part}-${partIndex}`}>{part.slice(2, -2)}</strong>
        }
        return part
      })}
    </p>
  ))
}
