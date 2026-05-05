import React, { useEffect, useState } from 'react'
import type { SyntaxHighlighterProps } from 'react-syntax-highlighter'

type PrismHighlighterComponent = React.ComponentType<SyntaxHighlighterProps>
type PrismStyle = Record<string, React.CSSProperties>

interface MarkdownCodeBlockProps {
  codeText: string
  language: string
  copyButton: React.ReactNode
}

export const MarkdownCodeBlock: React.FC<MarkdownCodeBlockProps> = ({
  codeText,
  language,
  copyButton,
}) => {
  const [SyntaxHighlighter, setSyntaxHighlighter] = useState<PrismHighlighterComponent | null>(null)
  const [style, setStyle] = useState<PrismStyle | null>(null)

  useEffect(() => {
    let mounted = true

    void Promise.all([
      import('react-syntax-highlighter/dist/esm/prism-async-light'),
      import('react-syntax-highlighter/dist/esm/styles/prism/one-dark'),
    ])
      .then(([module, styleModule]) => {
        if (!mounted) return
        setSyntaxHighlighter(() => module.default as PrismHighlighterComponent)
        setStyle(styleModule.default as PrismStyle)
      })
      .catch(() => {
        if (!mounted) return
        setSyntaxHighlighter(null)
        setStyle(null)
      })

    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden border border-bg-border">
      <div className="flex items-center justify-between bg-bg-tertiary px-4 py-2 text-xs text-text-secondary">
        <span>{language || 'code'}</span>
        {copyButton}
      </div>
      <div className="overflow-x-auto">
        {SyntaxHighlighter && style ? (
          <SyntaxHighlighter
            style={style}
            language={language || 'text'}
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
        ) : (
          <pre
            className="m-0 rounded-none bg-[#12121a] p-4 text-[0.8rem] text-text-primary"
          >
            <code>{codeText}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
