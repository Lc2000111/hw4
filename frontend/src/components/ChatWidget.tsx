import { Fragment, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import {
  ApiError,
  clearChatHistory,
  fetchChatHistory,
  formatPrice,
  streamChatMessage,
  type ChatTurn,
  type PageContext,
  type PageResults,
  type PageType,
  type Product,
  type User,
} from '../api'
import { useAuth } from '../useAuth'
import Patch from './Patch'
import { useChatResults } from '../useChatResults'

interface Message {
  role: 'user' | 'assistant'
  content: string
  products?: Product[]
  pageResults?: PageResults // this reply put products on the page
  local?: boolean // greeting or error shown by the widget itself; not sent to the agent
  saved?: boolean // reloaded from the shopper's saved history
  notice?: string // safety notice shown under a shopper message (sensitive data removed)
}

// Other components (e.g. "Ask about this item" on a product page) open the chat with this event.
export const OPEN_CHAT_EVENT = 'cc:open-chat'

// Quick-question chips (Problem 9): one tap instead of typing, tailored to the page.
function quickQuestions(page: PageContext, loggedIn: boolean): string[] {
  if (page.page_type === 'product') {
    return ['Is this in M?', 'What colors does it come in?', 'How many are left in L?', 'Show me similar items']
  }
  const chips = ['What hoodies do you have?', 'Anything under $50?', 'Show me bulldog designs', 'Navy crewnecks in M?']
  return loggedIn ? ['What did you show me last time?', ...chips] : chips
}

function greeting(user: User | null): Message {
  const content = user
    ? `Welcome back, ${user.first_name}! Our chat is saved to your account, so you can pick up where you left off.`
    : "Hi! I'm the Campus Customs assistant. Ask me about hoodies, tees, sizes, or what's in stock. Log in to save our chat for next time."
  return { role: 'assistant', content, local: true }
}

const PAGE_TYPES: [string, PageType][] = [
  ['/', 'home'],
  ['/products', 'products'],
  ['/products/:productId', 'product'],
  ['/about', 'about'],
  ['/login', 'login'],
  ['/signup', 'signup'],
]

// Where the shopper is, sent with every message so "this" / "it" can be resolved.
function pageContext(pathname: string, resultsTitle: string | null): PageContext {
  for (const [pattern, page_type] of PAGE_TYPES) {
    const match = matchPath(pattern, pathname)
    if (match) {
      return { path: pathname, page_type, product_id: match.params.productId ?? null, results_title: resultsTitle }
    }
  }
  return { path: pathname, page_type: 'other', product_id: null, results_title: resultsTitle }
}

// Saved replies may contain **bold**; render it without using raw HTML.
function renderText(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  )
}

export default function ChatWidget() {
  const { user, ready } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([greeting(null)])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState('') // live progress from the agent while it works
  const endRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const { results, showResults } = useChatResults()

  // Whenever the logged-in shopper changes (log in, log out, switch account), start a
  // fresh conversation so one person's chat is never shown to the next.
  const [chatOwner, setChatOwner] = useState<number | null | undefined>(undefined)
  const currentOwner = ready ? (user?.id ?? null) : undefined
  if (currentOwner !== chatOwner) {
    setChatOwner(currentOwner)
    setMessages([greeting(user)])
  }

  // ...then reload a logged-in shopper's saved chat from the server.
  useEffect(() => {
    if (!user) return
    let ignore = false
    fetchChatHistory()
      .then((saved) => {
        if (ignore || saved.length === 0) return
        const history: Message[] = saved.map((m) => ({
          role: m.role,
          content: m.content,
          products: m.products,
          pageResults: m.page_results ?? undefined,
          saved: true,
        }))
        setMessages([...history, greeting(user)])
      })
      .catch(() => {
        // keep the greeting; history is a nice-to-have
      })
    return () => {
      ignore = true
    }
  }, [user])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open, status])

  useEffect(() => {
    const openChat = () => setOpen(true)
    window.addEventListener(OPEN_CHAT_EVENT, openChat)
    return () => window.removeEventListener(OPEN_CHAT_EVENT, openChat)
  }, [])

  const page = pageContext(location.pathname, results?.title ?? null)

  function viewOnPage(pageResults: PageResults) {
    showResults(pageResults)
    // On small screens the chat covers the page, so close it to reveal the cards.
    if (window.innerWidth < 820) setOpen(false)
  }

  async function handleClear() {
    if (!window.confirm('Delete your saved chat history? This cannot be undone.')) return
    try {
      await clearChatHistory()
      setMessages([greeting(user)])
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: "Sorry, I couldn't clear the history.", local: true }])
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || sending) return

    // Guests: send the conversation so far. Logged in: the server reads saved history itself.
    const history: ChatTurn[] = user
      ? []
      : messages.filter((m) => !m.local).map(({ role, content }) => ({ role, content }))

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setSending(true)
    setStatus('Thinking…')
    try {
      const res = await streamChatMessage(text, history, page, setStatus)
      const pageResults = res.page_results ?? undefined
      setMessages((prev) => {
        const next = [...prev]
        // Sensitive-data guard: show the shopper the cleaned message that was actually sent and saved.
        const last = next.length - 1
        if (res.redactions.length && next[last]?.role === 'user') {
          next[last] = {
            ...next[last],
            content: res.message ?? next[last].content,
            notice: `For your safety we removed the ${res.redactions.join(' and ')} from your message. Please never share payment details or passwords in chat.`,
          }
        }
        return [...next, { role: 'assistant', content: res.reply, products: res.products, pageResults }]
      })
      // Chat -> page: render the matches as product cards on the page.
      if (pageResults) showResults(pageResults)
    } catch (err) {
      const content =
        err instanceof ApiError && err.fromServer
          ? err.message // friendly message written by the backend
          : "Sorry, I can't reach the shop right now. Please try again in a moment."
      setMessages((prev) => [...prev, { role: 'assistant', content, local: true }])
    } finally {
      setSending(false)
      setStatus('')
    }
  }

  const firstNew = messages.findIndex((m) => !m.saved)
  const hasSaved = messages.some((m) => m.saved)

  return (
    <div className="chat">
      {open && (
        <section className="chat-panel" aria-label="Campus Customs chat">
          <header className="chat-header">
            <Patch size={42} className="chat-header-patch" />
            <div className="chat-header-text">
              <strong>Campus Customs Assistant</strong>
              <span>
                <i className="online-dot" aria-hidden="true" />
                {user ? `Chatting as ${user.first_name} · saved to your account` : 'Guest chat · not saved'}
              </span>
            </div>
            <div className="chat-header-actions">
              {user && hasSaved && (
                <button className="chat-clear" onClick={handleClear}>
                  Clear history
                </button>
              )}
              <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </header>

          <div className="chat-messages">
            {hasSaved && <p className="chat-divider">Saved conversation</p>}
            {messages.map((m, i) => (
              <Fragment key={i}>
                {hasSaved && i === firstNew && <p className="chat-divider">Today</p>}
                <div className={`chat-msg chat-msg-${m.role}`}>
                  {m.role === 'assistant' && <Patch size={26} className="chat-avatar" />}
                  <p>{renderText(m.content)}</p>
                  {m.notice && <p className="chat-notice">{m.notice}</p>}
                  {m.pageResults && (
                    <button className="chat-page-link" onClick={() => viewOnPage(m.pageResults!)}>
                      View {m.pageResults.products.length} {m.pageResults.title.toLowerCase()} on the page ↑
                    </button>
                  )}
                  {m.products && m.products.length > 0 && (
                    <div className="chat-products">
                      {m.products.map((p) => (
                        <Link key={p.product_id} to={`/products/${p.product_id}`}>
                          <img src={p.image_url} alt="" />
                          <span>{p.name}</span>
                          <span className="price">{formatPrice(p.price)}</span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </Fragment>
            ))}
            {sending && (
              <div className="chat-msg chat-msg-assistant chat-typing" aria-live="polite">
                <Patch size={26} className="chat-avatar" />
                <span className="typing-dots" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="typing-status">{status || 'Thinking…'}</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {!sending && (
            <div className="chat-chips" aria-label="Suggested questions">
              {quickQuestions(page, !!user).map((q) => (
                <button key={q} type="button" onClick={() => void send(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}

          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Do you have navy hoodies in M?"
              aria-label="Chat message"
            />
            <button type="submit" className="btn" disabled={sending || !input.trim()}>
              Send
            </button>
          </form>
        </section>
      )}

      <button
        className={`chat-toggle ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          <span className="chat-toggle-x">×</span>
        ) : (
          <>
            <Patch size={44} text="ASK" />
            <span className="chat-toggle-label">Ask Campus Customs</span>
          </>
        )}
      </button>
    </div>
  )
}
