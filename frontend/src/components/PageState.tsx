import { LoaderCircle, TriangleAlert } from 'lucide-react'

export function LoadingState({ label = 'Consultando los archivos…' }: { label?: string }) {
  return (
    <div className="page-state" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="page-state page-state--error" role="alert">
      <TriangleAlert size={22} />
      <span>{message}</span>
    </div>
  )
}

export function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{copy}</p>
    </div>
  )
}
