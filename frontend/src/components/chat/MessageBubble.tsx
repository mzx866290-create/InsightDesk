import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check } from 'lucide-react'
import type { PanelMessage } from '../../stores/chatStore'
import { CitationPanel } from './CitationPanel'
import { ErrorBanner } from './ErrorBanner'
import { IntentCardRenderer, stripIntentBlocks } from '../cards/IntentCardRenderer'
import { TaskProgressCard } from '../cards/TaskProgressCard'
import { useChatStore } from '../../stores/chatStore'
import { clearSessionMessages } from '../../api/client'

interface MessageBubbleProps {
  message: PanelMessage
  panelId?: string
}

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-bg-tertiary/80 text-text-secondary hover:text-text-primary opacity-0 group-hover:opacity-100 transition-opacity"
      title="复制代码"
    >
      {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
    </button>
  )
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, panelId }) => {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  const { currentSessionId, clearMessages, setSettingsOpen } = useChatStore()

  const handleClearContext = async () => {
    if (currentSessionId) {
      await clearSessionMessages(currentSessionId)
    }
    clearMessages()
  }

  if (isError) {
    return (
      <ErrorBanner
        content={message.content}
        errorCode={message.errorCode}
        suggestion={message.suggestion}
        onClearContext={handleClearContext}
        onOpenSettings={() => setSettingsOpen(true)}
      />
    )
  }

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="max-w-[85%] bg-accent-blue/20 border border-accent-blue/30 text-text-primary px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    )
  }

  void panelId

  return (
    <div className="flex justify-start mb-4 animate-fade-in">
      <div className={`max-w-[95%] text-sm ${message.streaming ? 'streaming-cursor' : ''}`}>
        {message.taskId && (
          <TaskProgressCard
            taskId={message.taskId}
            taskType={message.taskType}
          />
        )}
        <IntentCardRenderer content={message.content} streaming={message.streaming} />
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ node, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '')
              const codeText = String(children).replace(/\n$/, '')
              const isBlock = codeText.includes('\n') || match

              if (isBlock) {
                return (
                  <div className="relative group my-3 rounded-lg overflow-hidden border border-bg-border">
                    <div className="flex items-center justify-between bg-bg-tertiary px-4 py-2 text-xs text-text-secondary">
                      <span>{match ? match[1] : 'code'}</span>
                      <CopyButton text={codeText} />
                    </div>
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match ? match[1] : 'text'}
                      PreTag="div"
                      customStyle={{
                        margin: 0,
                        borderRadius: 0,
                        background: '#12121a',
                        fontSize: '0.8rem',
                        padding: '1rem',
                      }}
                    >
                      {codeText}
                    </SyntaxHighlighter>
                  </div>
                )
              }

              return (
                <code
                  className="bg-bg-tertiary border border-bg-border text-accent-blue px-1.5 py-0.5 rounded text-[0.8em] font-mono"
                  {...props}
                >
                  {children}
                </code>
              )
            },
            p({ children }) {
              return <p className="mb-3 last:mb-0 leading-relaxed text-text-primary">{children}</p>
            },
            h1({ children }) {
              return <h1 className="text-lg font-bold text-text-primary mt-4 mb-2">{children}</h1>
            },
            h2({ children }) {
              return <h2 className="text-base font-semibold text-text-primary mt-3 mb-2">{children}</h2>
            },
            h3({ children }) {
              return <h3 className="text-sm font-semibold text-text-primary mt-2 mb-1.5">{children}</h3>
            },
            ul({ children }) {
              return <ul className="list-disc list-inside space-y-1 mb-3 text-text-primary ml-2">{children}</ul>
            },
            ol({ children }) {
              return <ol className="list-decimal list-inside space-y-1 mb-3 text-text-primary ml-2">{children}</ol>
            },
            li({ children }) {
              return <li className="leading-relaxed">{children}</li>
            },
            blockquote({ children }) {
              return (
                <blockquote className="border-l-2 border-accent-blue/50 pl-4 my-3 text-text-secondary italic">
                  {children}
                </blockquote>
              )
            },
            a({ href, children }) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-blue hover:text-accent-blue-hover underline underline-offset-2 transition-colors"
                >
                  {children}
                </a>
              )
            },
            table({ children }) {
              return (
                <div className="overflow-x-auto my-3">
                  <table className="text-xs border-collapse w-full">{children}</table>
                </div>
              )
            },
            th({ children }) {
              return (
                <th className="border border-bg-border bg-bg-tertiary px-3 py-1.5 text-left text-text-primary font-medium">
                  {children}
                </th>
              )
            },
            td({ children }) {
              return (
                <td className="border border-bg-border px-3 py-1.5 text-text-secondary">
                  {children}
                </td>
              )
            },
            hr() {
              return <hr className="border-bg-border my-4" />
            },
            strong({ children }) {
              return <strong className="font-semibold text-text-primary">{children}</strong>
            },
          }}
        >
          {stripIntentBlocks(message.content)}
        </ReactMarkdown>
        {message.sources && message.sources.length > 0 && (
          <CitationPanel sources={message.sources} streaming={message.streaming} />
        )}
      </div>
    </div>
  )
}
