import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ReportMarkdownProps {
  content: string
}

const ReportMarkdown: React.FC<ReportMarkdownProps> = ({ content }) => {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
}

export default ReportMarkdown
