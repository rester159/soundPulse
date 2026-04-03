import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Bot, User, Loader2 } from 'lucide-react'
import { useAssistantChat } from '../hooks/useSoundPulse'

function ChatMessage({ role, content }) {
  const isBot = role === 'assistant'
  return (
    <div className={`flex gap-3 ${isBot ? '' : 'flex-row-reverse'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        isBot ? 'bg-violet-600/20' : 'bg-zinc-700'
      }`}>
        {isBot ? <Bot size={16} className="text-violet-400" /> : <User size={16} className="text-zinc-300" />}
      </div>
      <div className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
        isBot
          ? 'bg-zinc-900 border border-zinc-800 text-zinc-200'
          : 'bg-violet-600/20 border border-violet-500/30 text-zinc-200'
      }`}>
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
    </div>
  )
}

const SUGGESTIONS = [
  "What genres are trending right now?",
  "If I wanted to make a melodic trap song, what should it sound like?",
  "Which tracks have the highest velocity this month?",
  "What's the opportunity score for indie pop vs electronic?",
  "How many tracks and artists are in the database?",
  "What would a Christian rock artist profile look like?",
]

export default function Assistant() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const chatMutation = useAssistantChat()
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async (text) => {
    const question = text || input
    if (!question.trim()) return

    const userMsg = { role: 'user', content: question }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')

    chatMutation.mutate(
      { body: { question, history: messages.slice(-6) } },
      {
        onSuccess: (data) => {
          const answer = data?.data?.answer || 'No response received.'
          setMessages(prev => [...prev, { role: 'assistant', content: answer }])
        },
        onError: () => {
          setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Could not reach the assistant. Check your API key and Groq configuration.' }])
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
    <div className="flex flex-col h-[calc(100vh-2rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <MessageSquare size={28} className="text-violet-400" />
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Assistant</h1>
          <p className="text-sm text-zinc-500">Ask anything about your music data</p>
        </div>
      </div>

      {/* Chat area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pr-2 pb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full">
            <Bot size={64} className="text-zinc-700 mb-6" />
            <h3 className="text-lg font-medium text-zinc-400 mb-2">What do you want to know?</h3>
            <p className="text-sm text-zinc-600 mb-8 text-center max-w-md">
              I can analyze trends, suggest song blueprints, compare artists,
              explain predictions, and help plan your next release.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full max-w-2xl">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="text-left px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} />
        ))}

        {chatMutation.isPending && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-violet-600/20 flex items-center justify-center">
              <Loader2 size={16} className="text-violet-400 animate-spin" />
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-zinc-800 pt-4">
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about trends, genres, artists, blueprints..."
            rows={1}
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none focus:border-violet-500/50"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || chatMutation.isPending}
            className="px-4 py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-30 rounded-lg transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
