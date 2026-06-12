import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Send, Download, FileText, User, Bot, Loader2 } from 'lucide-react'
import { apiGet, apiPost, ApiError } from '../lib/api'
import { useToast } from '../components/Toast'
import type { ChatMessage } from '../types'

interface ChatResponse {
  reply: string
  docx_url: string
  pdf_url: string | null
}

export function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const toast = useToast()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [docxUrl, setDocxUrl] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Load history on mount
  useEffect(() => {
    apiGet<ChatMessage[]>(`/chat/${id}`)
      .then(data => setMessages(data))
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [id, toast])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return

    // Optimistic: add user message immediately
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, optimistic])
    setInput('')
    setSending(true)

    try {
      const res = await apiPost<ChatResponse>(`/chat/${id}`, { message: text })
      setDocxUrl(res.docx_url)
      setPdfUrl(res.pdf_url ?? null)

      const assistant: ChatMessage = {
        id: `local-${Date.now() + 1}`,
        role: 'assistant',
        content: res.reply,
        created_at: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistant])
    } catch (err: unknown) {
      if (!(err instanceof ApiError && err.status === 402)) {
        toast(err instanceof Error ? err.message : 'Ошибка', 'error')
      }
      // Remove optimistic message on failure
      setMessages(prev => prev.filter(m => m.id !== optimistic.id))
      setInput(text)
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        Загрузка чата...
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-4 h-[calc(100vh-120px)]">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Редактирование через чат</h1>

        {/* Download links — update after each response */}
        <div className="flex gap-2">
          {docxUrl ? (
            <a
              href={docxUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/60 text-accent
                text-xs font-medium hover:bg-accent/10 transition-colors"
            >
              <Download size={13} />
              DOCX
            </a>
          ) : (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700
              text-slate-500 text-xs">
              <FileText size={13} />
              Документ появится после первого ответа
            </span>
          )}
          {pdfUrl && (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/60 text-accent
                text-xs font-medium hover:bg-accent/10 transition-colors"
            >
              <Download size={13} />
              PDF
            </a>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1">
        {messages.length === 0 && !sending && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
            <MessageBubbleIcon />
            <p className="text-sm">Напишите первое сообщение, чтобы начать редактирование</p>
            <p className="text-xs text-slate-600 max-w-md text-center">
              Например: «Перепиши введение» или «Исправь заключение, учитывая данные из расчёта»
            </p>
          </div>
        )}

        {messages.map(msg => (
          <MessageRow key={msg.id} msg={msg} />
        ))}

        {sending && (
          <div className="flex gap-3 items-start">
            <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center shrink-0 mt-0.5">
              <Bot size={15} className="text-accent" />
            </div>
            <div className="bg-navy-light border border-slate-700 rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 size={16} className="text-slate-400 animate-spin" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-navy-light border border-slate-700 rounded-2xl flex items-end gap-2 p-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Напишите требование к документу... (Enter — отправить, Shift+Enter — перенос)"
          rows={3}
          className="flex-1 bg-transparent resize-none text-sm text-slate-100 placeholder-slate-500
            focus:outline-none px-2 py-1 leading-relaxed"
        />
        <button
          onClick={send}
          disabled={!input.trim() || sending}
          className="mb-1 mr-1 w-9 h-9 rounded-xl bg-accent hover:bg-accent-dark text-white flex items-center justify-center
            transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>
    </div>
  )
}

function MessageRow({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 items-start ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5
        ${isUser ? 'bg-navy-lighter' : 'bg-accent/20'}`}>
        {isUser
          ? <User size={15} className="text-slate-400" />
          : <Bot size={15} className="text-accent" />}
      </div>
      <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
        ${isUser
          ? 'bg-navy-lighter text-slate-200 rounded-tr-sm'
          : 'bg-navy-light border border-slate-700 text-slate-300 rounded-tl-sm'}`}>
        {msg.content}
      </div>
    </div>
  )
}

function MessageBubbleIcon() {
  return (
    <div className="w-14 h-14 rounded-2xl bg-navy-light border border-slate-700 flex items-center justify-center">
      <MessageSquareIcon />
    </div>
  )
}

function MessageSquareIcon() {
  return <Bot size={28} className="text-slate-600" />
}
