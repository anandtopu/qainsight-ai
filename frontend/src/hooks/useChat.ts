import { useCallback, useEffect, useRef, useState } from 'react'
import useSWR from 'swr'
import chatService, { ChatMessage, ChatSession } from '@/services/chatService'

export function useChatSessions() {
  return useSWR(
    '/chat/sessions',
    () => chatService.listSessions().then(r => r.data),
    { revalidateOnFocus: false },
  )
}

export function useChatMessages(sessionId: string | null) {
  return useSWR(
    sessionId ? `/chat/sessions/${sessionId}/messages` : null,
    () => chatService.getMessages(sessionId!).then(r => r.data),
    { revalidateOnFocus: false },
  )
}

interface UseChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  isSending: boolean
  sendMessage: (text: string) => Promise<void>
  error: string | null
}

export function useChat(sessionId: string | null, projectId?: string | null): UseChatReturn {
  const { data: fetchedMessages = [], mutate } = useChatMessages(sessionId)
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pendingRef = useRef<string | null>(null)

  // Merge fetched + optimistic (deduplicate by id)
  const fetchedIds = new Set(fetchedMessages.map(m => m.id))
  const merged = [
    ...fetchedMessages,
    ...optimisticMessages.filter(m => !fetchedIds.has(m.id)),
  ].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isSending) return

      const tempUserMsg: ChatMessage = {
        id: `temp-user-${Date.now()}`,
        session_id: sessionId,
        role: 'user',
        content: text,
        sources: null,
        created_at: new Date().toISOString(),
      }
      const tempAssistantMsg: ChatMessage = {
        id: `temp-assistant-${Date.now()}`,
        session_id: sessionId,
        role: 'assistant',
        content: '…',
        sources: null,
        created_at: new Date().toISOString(),
      }

      setOptimisticMessages(prev => [...prev, tempUserMsg, tempAssistantMsg])
      setIsSending(true)
      setError(null)

      try {
        const res = await chatService.sendMessage(sessionId, text, projectId)
        // Replace temp assistant with real reply
        setOptimisticMessages(prev =>
          prev.filter(m => m.id !== tempAssistantMsg.id && m.id !== tempUserMsg.id),
        )
        await mutate()
      } catch (err: any) {
        setOptimisticMessages(prev =>
          prev.filter(m => m.id !== tempAssistantMsg.id),
        )
        setError(err?.response?.data?.detail ?? 'Failed to send message')
      } finally {
        setIsSending(false)
      }
    },
    [sessionId, projectId, isSending, mutate],
  )

  return {
    messages: merged,
    isLoading: !fetchedMessages && !error,
    isSending,
    sendMessage,
    error,
  }
}
