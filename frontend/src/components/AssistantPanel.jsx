import { useState, useRef, useEffect } from 'react'
import { Bot, User, Send, Loader2, MessageSquare, ChevronRight } from 'lucide-react'
import { useAssistantChat } from '../hooks/useSoundPulse'
import { useAssistantVisibility } from '../contexts/AssistantVisibilityContext'

function Bubble({ role, content }) {
  const isBot = role === 'assistant'
  return (
    <div className={`flex gap-2 ${isBot ? '' : 'flex-row-reverse'}`}>
      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
        isBot ? 'bg-violet-600/20' : 'bg-zinc-700'
      }`}>
        {isBot
          ? <Bot size={12} className="text-violet-400" />
          : <User size={12} className="text-zinc-300" />
        }
      </div>
      <div className={`max-w-[82%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
        isBot
          ? 'bg-zinc-800 border border-zinc-700/60 text-zinc-200'
          : 'bg-violet-600/20 border border-violet-500/30 text-zinc-200'
      }`}>
        <p className="whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  )
}

const SUGGESTIONS = [
  "What genres are trending?",
  "Best tempo for viral pop?",
  "Which tracks have rising velocity?",
  "Compare indie pop vs electronic",
]

export default function AssistantPanel() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const chatMutation = useAssistantChat()
  const scrollRef = useRef(null)
  const { hide } = useAssistantVisibility()

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, chatMutation.isPending])

  const handleSend = (text) => {
    const question = (text || input).trim()
    if (!question) return
    const newMessages = [...messages, { role: 'user', content: question }]
    setMessages(newMessages)
    setInput('')
    chatMutation.mutate(
      { body: { question, history: messages.slice(-6) } },
      {
        onSuccess: (data) => {
          const answer = data?.data?.data?.answer || data?.data?.answer || 'No response.'
          setMessages(prev => [...prev, { role: 'assistant', content: answer }])
        },
        onError: () => {
          setMessages(prev => [...prev, { role: 'assistant', content: 'Could not reach the assistant. Check your API key and Groq config.' }])
        },
      }
    )
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col border-l border-zinc-800 bg-zinc-950">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3.5 border-b border-zinc-800">
        <MessageSquare size={14} className="text-violet-400" />
        <span className="text-sm font-semibold text-zinc-200">Assistant</span>
        <span className="ml-auto text-xs text-zinc-600">Groq · Llama 3</span>
        <button
          onClick={hide}
          title="Hide Assistant (Cmd/Ctrl + .)"
          className="p-1 rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
        >
          <ChevronRight size={14} />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full py-6">
            <Bot size={36} className="text-zinc-700 mb-4" />
            <p className="text-xs text-zinc-600 text-center mb-4 leading-relaxed px-2">
              Ask me about trends, genres, blueprints, or how to plan your next release.
            </p>
            <div className="w-full space-y-1.5">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="w-full text-left px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <Bubble key={i} role={msg.role} content={msg.content} />
        ))}

        {chatMutation.isPending && (
          <div className="flex gap-2">
            <div className="w-6 h-6 rounded-full bg-violet-600/20 flex items-center justify-center flex-shrink-0">
              <Loader2 size={12} className="text-violet-400 animate-spin" />
            </div>
            <div className="bg-zinc-800 border border-zinc-700/60 rounded-lg px-3 py-2">
              <div className="flex gap-1 items-center h-3">
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-3 py-3 border-t border-zinc-800">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
            rows={1}
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none focus:border-violet-500/50 leading-relaxed"
            style={{ minHeight: '36px', maxHeight: '120px' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || chatMutation.isPending}
            className="px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-30 rounded-lg transition-colors flex-shrink-0"
          >
            <Send size={13} />
          </button>
        </div>
        <p className="mt-1.5 text-[10px] text-zinc-700 text-center">Enter to send · Shift+Enter for newline</p>
      </div>
    </aside>
  )
}
