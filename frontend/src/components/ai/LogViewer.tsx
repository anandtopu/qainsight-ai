import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import toast from 'react-hot-toast'

interface Props { content?: string; title?: string }

export default function LogViewer({ content, title = 'Stack Trace' }: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    if (!content) return
    await navigator.clipboard.writeText(content)
    setCopied(true)
    toast.success('Copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl overflow-hidden border border-slate-700/50">
      {/* Terminal title bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500/70" />
            <div className="h-3 w-3 rounded-full bg-amber-500/70" />
            <div className="h-3 w-3 rounded-full bg-emerald-500/70" />
          </div>
          <span className="text-xs text-slate-400 font-mono ml-2">{title}</span>
        </div>
        <button
          onClick={handleCopy}
          className="text-slate-500 hover:text-slate-300 transition-colors p-1 rounded"
          disabled={!content}
        >
          {copied
            ? <Check className="h-3.5 w-3.5 text-emerald-400" />
            : <Copy className="h-3.5 w-3.5" />
          }
        </button>
      </div>

      {/* Log content */}
      <div className="bg-slate-950 overflow-auto max-h-96">
        {content ? (
          <pre className="p-4 text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
            {content}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-32 text-slate-600 text-sm font-mono">
            No log content available
          </div>
        )}
      </div>
    </div>
  )
}
