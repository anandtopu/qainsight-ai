import { ReactNode } from 'react'

interface Props { icon: ReactNode; title: string; description?: string; action?: ReactNode }

export default function EmptyState({ icon, title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="p-4 bg-slate-800 rounded-2xl mb-4 text-slate-500">{icon}</div>
      <h3 className="text-lg font-semibold text-slate-300 mb-1">{title}</h3>
      {description && <p className="text-sm text-slate-500 max-w-sm mb-4">{description}</p>}
      {action}
    </div>
  )
}
