import { useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import type { PageResults } from './api'
import { ChatResultsContext, type ChatResultsState } from './useChatResults'

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<PageResults | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [version, setVersion] = useState(0)

  // When the shopper opens a product (or any other page), fold the results into a
  // one-line bar so the new page is visible right away. They can expand it again.
  const { pathname } = useLocation()
  const [lastPath, setLastPath] = useState(pathname)
  if (pathname !== lastPath) {
    setLastPath(pathname)
    setExpanded(false)
  }

  const value: ChatResultsState = {
    results,
    expanded,
    version,
    showResults: (next) => {
      setResults(next)
      setExpanded(true)
      setVersion((v) => v + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    setExpanded,
    clear: () => {
      setResults(null)
      setExpanded(false)
    },
  }

  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>
}
