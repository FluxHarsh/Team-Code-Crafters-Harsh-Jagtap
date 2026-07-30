import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useStore } from '@/store'
import type { AgentMeta } from '@/types'

interface AgentNavItemProps {
  agent: AgentMeta
  projectId: string
}

export function AgentNavItem({ agent, projectId }: AgentNavItemProps) {
  const location = useLocation()
  const activeNode = useStore((s) => s.agentGraph.active_node)
  const isActive = location.pathname.includes(`/agents/${agent.key}`)
  const isLive = activeNode === agent.key

  return (
    <Link
      to={`/projects/${projectId}/dashboard/agents/${agent.key}`}
      className={cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-[9px] text-xs transition group border-l-[3px]',
        isActive
          ? 'bg-primary-soft border-primary text-primary-dark font-700 rounded-l-none'
          : 'border-transparent text-text hover:bg-bg font-500'
      )}
    >
      {/* Icon badge */}
      <div
        className={cn(
          'w-6 h-6 rounded-[7px] flex items-center justify-center text-[9px] font-800 flex-none',
          agent.bgColor,
          agent.iconColor
        )}
      >
        {agent.shortLabel}
      </div>

      <span className="flex-1 truncate">{agent.label}</span>

      {/* Live/Idle dot */}
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full flex-none',
          isLive ? 'dot-live' : 'bg-muted-2/50'
        )}
      />
    </Link>
  )
}
