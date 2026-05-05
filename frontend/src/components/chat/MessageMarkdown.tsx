import React, { useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy } from 'lucide-react'

import { MarkdownTableChart } from '../charts/MarkdownTableChart'
import { MarkdownCodeBlock } from './MarkdownCodeBlock'

interface MessageMarkdownProps {
  content: string
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

const MessageMarkdown: React.FC<MessageMarkdownProps> = ({ content }) => {
  const tableHeadersRef = useRef<string[]>([])
  const tableRowsRef = useRef<(string | number)[][]>([])

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          const codeText = String(children).replace(/\n$/, '')
          const isBlock = codeText.includes('\n') || match

          if (isBlock) {
            return (
              <MarkdownCodeBlock
                codeText={codeText}
                language={match ? match[1] : 'text'}
                copyButton={<CopyButton text={codeText} />}
              />
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
          return <p className="mb-3 last:mb-0 leading-relaxed text-text-primary break-words">{children}</p>
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
          return <li className="leading-relaxed break-words">{children}</li>
        },
        blockquote({ children }) {
          return (
            <blockquote className="border-l-2 border-accent-blue/50 pl-4 my-3 text-text-secondary italic">
              {children}
            </blockquote>
          )
        },
        a({ href, children }) {
          const isInternalAnchor = typeof href === 'string' && href.startsWith('#')

          if (isInternalAnchor) {
            return (
              <a
                href={href}
                className="text-accent-blue hover:text-accent-blue-hover underline underline-offset-2 transition-colors"
              >
                {children}
              </a>
            )
          }

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
          const headers = tableHeadersRef.current
          const rows = tableRowsRef.current
          const tableEl = <table className="text-xs border-collapse w-full">{children}</table>
          tableHeadersRef.current = []
          tableRowsRef.current = []
          return (
            <MarkdownTableChart rawHeaders={headers} rawRows={rows}>
              {tableEl}
            </MarkdownTableChart>
          )
        },
        th({ children }) {
          tableHeadersRef.current = [...tableHeadersRef.current, String(children ?? '')]
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
        tr({ children, ...props }) {
          const isHeader = (props as Record<string, unknown>)['data-header']
          if (!isHeader) {
            const cells: (string | number)[] = []
            React.Children.forEach(children, (child) => {
              if (React.isValidElement(child)) {
                const text = String((child.props as Record<string, unknown>).children ?? '')
                cells.push(text)
              }
            })
            if (cells.length > 0) {
              tableRowsRef.current = [...tableRowsRef.current, cells]
            }
          }
          return <tr>{children}</tr>
        },
        hr() {
          return <hr className="border-bg-border my-4" />
        },
        strong({ children }) {
          return <strong className="font-semibold text-text-primary">{children}</strong>
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default MessageMarkdown
