import { createContext, useContext } from 'react'
import type { PageResults } from './api'

// Shared state for the chat -> page feature: the chat widget writes results,
// the ChatResultsPanel at the top of every page renders them.
export interface ChatResultsState {
  results: PageResults | null
  expanded: boolean
  version: number // bumps on every new result set (restarts the highlight animation)
  showResults: (results: PageResults) => void
  setExpanded: (expanded: boolean) => void
  clear: () => void
}

export const ChatResultsContext = createContext<ChatResultsState | null>(null)

export function useChatResults(): ChatResultsState {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
