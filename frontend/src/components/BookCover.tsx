import type { Book } from '../types/api'

const coverByTitle: Record<string, string> = {
  'Don Quijote de la Mancha': '/assets/covers/don-quijote.png',
  'Orgullo y prejuicio': '/assets/covers/orgullo-prejuicio.png',
  Frankenstein: '/assets/covers/frankenstein.png',
  'La metamorfosis': '/assets/covers/metamorfosis.png',
  'Versos sencillos': '/assets/covers/versos-sencillos.png',
}

export function BookCover({ book, small = false }: { book: Pick<Book, 'title' | 'cover_url'>; small?: boolean }) {
  const source = book.cover_url || coverByTitle[book.title]
  if (source) {
    return <img className={`book-cover ${small ? 'book-cover--small' : ''}`} src={source} alt={`Portada de ${book.title}`} />
  }
  return (
    <div className={`book-cover book-cover--fallback ${small ? 'book-cover--small' : ''}`}>
      <span>{book.title}</span>
    </div>
  )
}
