import { useEffect, useRef, useState } from 'react'
import {
  Bot, MessageSquare, Plus, Send, Trash2, User,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useChat, useChatSessions } from '@/hooks/useChat'
import chatService from '@/services/chatService'
import type { ChatSession } from '@/services/chatService'
import { useProjectStore } from '@/store/projectStore'

// ── Session sidebar item ───────────────────────────────────────

function SessionItem({
  session,
  active,
  onSelect,
  onDelete,
}: {
  session: ChatSession
  active: boolean
  onSelect: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
        active ? 'bg-blue-900/30 border border-blue-700/30' : 'hover:bg-slate-800/60'
      }`}
      onClick={onSelect}
    >
      <MessageSquare className="w-3.5 h-3.5 text-slate-500 shrink-0" />
      <span className="text-sm text-slate-300 truncate flex-1">
        {session.title || 'Conversation'}
      </span>
      <button
        onClick={e => { e.stopPropagation(); onDelete() }}
        className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </div>
  )
}

// ── Message bubble ─────────────────────────────────────────────

function MessageBubble({ role, content, sources }: {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ type: string; id?: string }> | null
}) {
  const isUser = role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
        isUser ? 'bg-blue-600' : 'bg-slate-700'
      }`}>
        {isUser
          ? <User className="w-3.5 h-3.5 text-white" />
          : <Bot className="w-3.5 h-3.5 text-blue-400" />
        }
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-blue-700/60 text-white'
          : 'bg-slate-800 text-slate-200'
      }`}>
        {content === '…' ? (
          <span className="inline-flex gap-1 items-center text-slate-400">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:300ms]" />
          </span>
        ) : isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}

        {/* Sources */}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-slate-700 flex flex-wrap gap-1">
            {sources.map((s, i) => (
              <span
                key={i}
                className="text-xs bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full"
              >
                {s.type}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Starter prompts ────────────────────────────────────────────

const STARTER_PROMPTS = [
  'What are the most common failure patterns in recent runs?',
  'Show me tests that have been consistently failing this week',
  'What was the pass rate trend for the last 7 days?',
  'Are there any critical regressions I should be aware of?',
  'Which tests are showing flaky behaviour?',
  'Summarise the latest test run results',
]

// ── Main page ──────────────────────────────────────────────────

export default function ChatPage() {
  const { activeProject } = useProjectStore()
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: sessions = [], mutate: reloadSessions } = useChatSessions()
  const { messages, isSending, sendMessage, error } = useChat(
    activeSessionId,
    activeProject?.id,
  )

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleNewSession = async () => {
    try {
      const res = await chatService.createSession({
        project_id: activeProject?.id,
        title: 'New conversation',
      })
      await reloadSessions()
      setActiveSessionId(res.data.id)
    } catch {
      toast.error('Failed to create session')
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('Delete this conversation?')) return
    try {
      await chatService.deleteSession(sessionId)
      if (activeSessionId === sessionId) setActiveSessionId(null)
      await reloadSessions()
    } catch {
      toast.error('Failed to delete session')
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isSending) return
    const text = input
    setInput('')

    let sid = activeSessionId
    if (!sid) {
      // Auto-create session on first message, then pass the new ID directly to
      // sendMessage so we don't rely on the state update propagating first.
      try {
        const res = await chatService.createSession({ project_id: activeProject?.id })
        sid = res.data.id
        setActiveSessionId(sid)
        await reloadSessions()
      } catch {
        setInput(text) // restore on failure
        toast.error('Could not create chat session')
        return
      }
    }

    await sendMessage(text, sid)
    await reloadSessions()
  }

  const handleStarterPrompt = async (prompt: string) => {
    if (!activeSessionId) {
      try {
        const res = await chatService.createSession({ project_id: activeProject?.id })
        await reloadSessions()
        setActiveSessionId(res.data.id)
        setInput(prompt)
        return
      } catch {
        return
      }
    }
    setInput(prompt)
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-4">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col gap-2">
        <button
          onClick={handleNewSession}
          className="btn-primary flex items-center gap-2 text-sm justify-center py-2"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>

        <div className="flex-1 overflow-y-auto space-y-1">
          {sessions.length === 0 ? (
            <p className="text-xs text-slate-500 text-center mt-4">No conversations yet</p>
          ) : (
            sessions.map((s: ChatSession) => (
              <SessionItem
                key={s.id}
                session={s}
                active={activeSessionId === s.id}
                onSelect={() => setActiveSessionId(s.id)}
                onDelete={() => handleDeleteSession(s.id)}
              />
            ))
          )}
        </div>

        <div className="text-xs text-slate-600 p-2 border-t border-slate-800">
          <p className="font-medium text-slate-500 mb-1">Context</p>
          <p>{activeProject?.name || 'All projects'}</p>
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col card overflow-hidden">
        {!activeSessionId ? (
          /* Empty state with starter prompts */
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-8">
            <div className="w-14 h-14 rounded-2xl bg-slate-800 flex items-center justify-center">
              <Bot className="w-7 h-7 text-blue-400" />
            </div>
            <div className="text-center">
              <h3 className="font-semibold text-slate-200 mb-1">QA Insight Chat</h3>
              <p className="text-sm text-slate-500 max-w-xs">
                Ask questions about test results, failures, trends, and AI analysis findings.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl w-full">
              {STARTER_PROMPTS.map(prompt => (
                <button
                  key={prompt}
                  onClick={() => handleStarterPrompt(prompt)}
                  className="text-left text-sm text-slate-300 bg-slate-800/60 hover:bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message list */
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !isSending && (
              <div className="text-center text-sm text-slate-500 mt-8">
                Send your first message to start the conversation.
              </div>
            )}
            {messages.map(msg => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                sources={msg.sources}
              />
            ))}
            {error && (
              <div className="text-xs text-red-400 text-center">{error}</div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input */}
        <div className="border-t border-slate-700/50 p-3">
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Ask about test results, failures, trends…"
              rows={1}
              className="input flex-1 resize-none text-sm py-2 leading-relaxed"
              style={{ maxHeight: '120px', overflow: 'auto' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="btn-primary p-2.5 shrink-0 disabled:opacity-40"
            >
              {isSending ? <LoadingSpinner size="sm" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-1">Press Enter to send · Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  )
}
