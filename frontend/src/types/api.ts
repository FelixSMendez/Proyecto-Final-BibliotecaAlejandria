export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface User {
  id: string
  email: string
  display_name: string
  is_active: boolean
  monthly_token_limit: number
  monthly_tokens_used: number
  token_period_start: string
  role_code: 'admin' | 'user'
  last_login_at: string | null
  created_at: string
}

export interface AuthorSummary {
  id: string
  full_name: string
  contribution: string
}

export interface GenreSummary {
  id: number
  name: string
}

export interface Book {
  id: string
  title: string
  subtitle: string | null
  synopsis: string | null
  isbn_10: string | null
  isbn_13: string | null
  publication_year: number | null
  language_code: string
  page_count: number | null
  cover_url: string | null
  source_url: string | null
  is_active: boolean
  publisher: { id: string; name: string } | null
  authors: AuthorSummary[]
  genres: GenreSummary[]
  created_at: string
  updated_at: string
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface RagSource {
  document_id: string
  chunk_id: string
  book_id: string | null
  title: string
  source_url: string | null
  distance: number
}

export interface RagResponse {
  conversation_id: string
  answer: string
  sources: RagSource[]
  usage: TokenUsage
}

export interface RecommendedBook {
  book_id: string
  title: string
  authors: string[]
  genres: string[]
  page_count: number | null
  score: number
}

export interface RecommendationResponse {
  conversation_id: string
  answer: string
  recommendations: RecommendedBook[]
  usage: TokenUsage
}

export interface ResearchSource {
  provider: string
  title: string
  url: string | null
  excerpt: string | null
}

export interface ResearchResponse {
  conversation_id: string
  answer: string
  sources: ResearchSource[]
  usage: TokenUsage
}

export interface ConversationSummary {
  id: string
  service_code: string
  service_name: string
  title: string | null
  status: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Record<string, unknown>[]
  prompt_tokens: number
  completion_tokens: number
  created_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[]
}

export interface UsageSummary {
  user_id: string
  period_start: string
  token_limit: number
  tokens_used: number
  tokens_remaining: number
  usage_percent: number
}

export interface IndexState {
  book_id: string
  title: string
  status: 'current' | 'stale' | 'not_indexed' | 'inactive'
  document_id: string | null
  chunks_indexed: number
}

export interface BulkIndexResult {
  total: number
  indexed: number
  unchanged: number
  failed: number
  items: Array<{
    book_id: string
    title: string
    status: 'indexed' | 'unchanged' | 'failed'
    chunks_indexed: number
    error: string | null
  }>
}

export interface ManualDocument {
  id: string
  title: string
  source_url: string | null
  is_active: boolean
  chunks_indexed: number
  created_at: string
  updated_at: string
}

export interface ReportSummary {
  active_users: number
  active_books: number
  conversations: number
  requests: number
  total_tokens: number
  successful_requests: number
  failed_requests: number
  average_duration_ms: number | null
}

export interface UsageReportRow {
  user_id: string
  email: string
  service_code: string
  service_name: string
  model_name: string | null
  execution_date: string
  request_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  success_count: number
  failed_count: number
  average_duration_ms: number | null
}
