import { create } from 'zustand'
import type { ChatMessage } from '../types'

interface ChatState {
  conversationId: string
  messages: ChatMessage[]
  setMessages(messages: ChatMessage[]): void
  addMessage(message: ChatMessage): void
  updateMessage(id: string, content: string): void
  clear(): void
}

export const useChatStore = create<ChatState>((set) => ({
  conversationId: crypto.randomUUID(),
  messages: [],
  setMessages(messages) {
    set({ messages })
  },
  addMessage(message) {
    set((state) => ({ messages: [...state.messages, message] }))
  },
  updateMessage(id, content) {
    set((state) => ({ messages: state.messages.map((message) => message.id === id ? { ...message, content } : message) }))
  },
  clear() {
    set({ conversationId: crypto.randomUUID(), messages: [] })
  },
}))
