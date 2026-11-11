import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'

import { BookCover } from '../components/BookCover'
import { EmptyState, ErrorState, LoadingState } from '../components/PageState'
import { api } from '../lib/api'
import type { Book } from '../types/api'

export function CatalogPage() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Book | null>(null)
  const books = useQuery({
    queryKey: ['books'],
    queryFn: () => api<Book[]>('/catalog/books?active_only=true&limit=200'),
  })
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return books.data ?? []
    return (books.data ?? []).filter((book) =>
      [book.title, book.subtitle, book.synopsis, ...book.authors.map((author) => author.full_name), ...book.genres.map((genre) => genre.name)]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(query)),
    )
  }, [books.data, search])

  return (
    <div className="catalog-page">
      <div className="catalog-search">
        <Search size={21} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por título, autor o tema" />
        {search && <button onClick={() => setSearch('')} aria-label="Limpiar búsqueda"><X size={18} /></button>}
      </div>
      <section className="catalog-hero">
        <div className="catalog-hero-copy">
          <h1>La Biblioteca de Alejandría</h1>
          <span className="short-rule" />
          <p>Una biblioteca digital e inteligente que reúne grandes obras para explorar, investigar y descubrir nuevas conexiones entre ideas, autores y épocas.</p>
        </div>
        <img src="/assets/library-hall.png" alt="Sala histórica de la Biblioteca de Alejandría" />
      </section>
      <section className="content-section">
        <div className="section-heading">
          <h2>Explora el catálogo</h2>
          <div className="rail-actions" aria-hidden="true"><button><ArrowLeft /></button><button><ArrowRight /></button></div>
        </div>
        {books.isLoading && <LoadingState />}
        {books.isError && <ErrorState message="No fue posible consultar el catálogo." />}
        {!books.isLoading && !books.isError && filtered.length === 0 && <EmptyState title="Sin coincidencias" copy="Prueba con otro título, autor o tema." />}
        <div className="book-rail">
          {filtered.map((book) => (
            <button className="book-item" key={book.id} onClick={() => setSelected(book)}>
              <BookCover book={book} />
              <strong>{book.title}</strong>
              <span>{book.authors.map((author) => author.full_name).join(', ')}</span>
              <small>{book.genres[0]?.name ?? 'Literatura'}{book.publication_year ? ` · ${book.publication_year}` : ''}</small>
            </button>
          ))}
        </div>
      </section>
      <section className="topics-band">
        <h2>Navega por temas</h2>
        <div>
          {['Literatura', 'Filosofía', 'Historia', 'Ciencias', 'Arte'].map((topic) => <button key={topic} onClick={() => setSearch(topic)}>{topic}</button>)}
        </div>
      </section>
      {selected && (
        <div className="drawer-scrim" onClick={() => setSelected(null)}>
          <aside className="book-drawer" onClick={(event) => event.stopPropagation()}>
            <button className="drawer-close" onClick={() => setSelected(null)} aria-label="Cerrar detalle"><X /></button>
            <BookCover book={selected} />
            <h2>{selected.title}</h2>
            <p className="book-byline">{selected.authors.map((author) => author.full_name).join(', ')}</p>
            <div className="book-meta"><span>{selected.publication_year ?? 'Año desconocido'}</span><span>{selected.page_count ? `${selected.page_count} páginas` : 'Extensión desconocida'}</span><span>{selected.language_code.toUpperCase()}</span></div>
            <p>{selected.synopsis ?? 'Esta obra todavía no cuenta con una sinopsis.'}</p>
            <div className="genre-list">{selected.genres.map((genre) => <span key={genre.id}>{genre.name}</span>)}</div>
          </aside>
        </div>
      )}
    </div>
  )
}
