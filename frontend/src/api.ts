// Typed helpers for talking to the FastAPI backend (backend/main.py).
// Vite proxies /api and /media to http://localhost:8000 during development.

export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  category: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  inventory: SizeStock[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface SearchFilters {
  query: string
  category: string | null
  color: string | null
  max_price: number | null
  size: string | null
}

// Chat -> page contract (Problem 7): matches the agent chose to show on the page.
export interface PageResults {
  search_id: string
  title: string
  filters: SearchFilters
  total_matches: number
  products: Product[]
}

// Which page the shopper is on (Problem 8): lets the agent resolve "this" / "it".
export type PageType = 'home' | 'products' | 'product' | 'about' | 'login' | 'signup' | 'other'

export interface PageContext {
  path: string
  page_type: PageType
  product_id: string | null
  results_title: string | null
}

export interface StoredChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  products: Product[]
  page_results: PageResults | null
}

export interface ChatReply {
  reply: string
  message: string | null // the shopper's message as stored, after the sensitive-data guard
  redactions: string[] // e.g. ["card number"]
  products: Product[] // small cards inside the chat
  page_results: PageResults | null // if set, rendered as product cards on the page
}

export interface User {
  id: number
  first_name: string
  last_name: string
  email: string
}

export interface SignupInput {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

// Error that carries the HTTP status and the backend's friendly message.
export class ApiError extends Error {
  status: number
  fromServer: boolean // true if the message is the backend's own "detail" text
  constructor(status: number, message: string, fromServer = false) {
    super(message)
    this.status = status
    this.fromServer = fromServer
  }
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  // Same-origin requests send the HttpOnly session cookie automatically.
  const res = await fetch(url, { credentials: 'same-origin', ...init })
  if (!res.ok) {
    let message = res.status === 404 ? 'Not found' : `Request failed (${res.status})`
    let fromServer = false
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') {
        message = body.detail
        fromServer = true
      }
    } catch {
      // keep the default message
    }
    throw new ApiError(res.status, message, fromServer)
  }
  return res.json() as Promise<T>
}

function postJson<T>(url: string, body: unknown): Promise<T> {
  return getJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchProducts(): Promise<Product[]> {
  return getJson<Product[]>('/api/products')
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

// Chat with the PydanticAI shop assistant. Guests send their recent turns so
// it can follow up; for logged-in shoppers the server uses their saved history
// instead. The page context tells the agent which product "this" is.
const HISTORY_TURNS = 12

export function sendChatMessage(message: string, history: ChatTurn[], page: PageContext): Promise<ChatReply> {
  return postJson<ChatReply>('/api/chat', {
    message,
    history: history.slice(-HISTORY_TURNS),
    page,
  })
}

// Streaming version (Problem 9): the server sends Server-Sent Events, so the widget can
// show progress ("Checking stock for … in XL…") while the agent works.
export async function streamChatMessage(
  message: string,
  history: ChatTurn[],
  page: PageContext,
  onStatus: (text: string) => void,
): Promise<ChatReply> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history: history.slice(-HISTORY_TURNS), page }),
  })
  if (!res.ok || !res.body) throw new ApiError(res.status, `Request failed (${res.status})`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const raw of events) {
      if (!raw.startsWith('data: ')) continue
      const event = JSON.parse(raw.slice(6))
      if (event.type === 'status') onStatus(event.text)
      else if (event.type === 'result') return event.data as ChatReply
      else if (event.type === 'error') throw new ApiError(event.status, event.detail, true)
    }
  }
  throw new ApiError(502, 'The chat stream ended early.')
}

// Saved chat for the logged-in shopper (Problem 8).
export async function fetchChatHistory(): Promise<StoredChatMessage[]> {
  const res = await getJson<{ messages: StoredChatMessage[] }>('/api/chat/history')
  return res.messages
}

export function clearChatHistory(): Promise<{ deleted: number }> {
  return getJson('/api/chat/history', { method: 'DELETE' })
}

// Accounts (Problem 4). The backend sets/clears an HttpOnly session cookie;
// the browser never sees the password hash or the raw session in JS.
export function signup(input: SignupInput): Promise<User> {
  return postJson<User>('/api/auth/signup', input)
}

export function login(email: string, password: string): Promise<User> {
  return postJson<User>('/api/auth/login', { email, password })
}

export function logout(): Promise<{ ok: boolean }> {
  return postJson('/api/auth/logout', {})
}

export async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await getJson<User>('/api/auth/me')
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null
    throw e
  }
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`
}

export const LOW_STOCK = 5
export const GOING_FAST = 30 // total units at or below this → "Going fast" (real stock, not a fake timer)
