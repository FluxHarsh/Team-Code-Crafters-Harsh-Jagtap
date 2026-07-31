import { useEffect } from 'react'
import { NavLink as RouterNavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  MessageCircle,
  MessagesSquare,
  Lightbulb,
  Github,
  Rocket,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useProject } from '@/hooks/useProject'
import { useProjectSocket } from '@/hooks/useProjectSocket'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: 'team', label: 'Team', icon: Users },
  { to: 'chat/personal', label: 'Coach', icon: MessageCircle },
  { to: 'chat/group', label: 'Group Chat', icon: MessagesSquare },
  { to: 'suggestions', label: 'Suggestions', icon: Lightbulb },
  { to: 'github', label: 'GitHub Insights', icon: Github },
  { to: 'pitch', label: 'Pitch', icon: Rocket },
] as const

export function DashboardShell() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading, isError } = useProject(projectId)
  const wsConnected = useStore((s) => s.wsConnected)

  useProjectSocket(projectId)

  // ─── Route guard ──────────────────────────────────────────────────────
  // FIXED: navigate() must never be called directly in the render body —
  // doing so throws "Cannot update a component while rendering a different
  // component" and can cause redirect loops. It now runs inside an effect,
  // gated on the query actually having settled.
  useEffect(() => {
    if (!projectId) {
      navigate('/', { replace: true })
      return
    }
    if (isError) {
      navigate('/', { replace: true })
      return
    }
    if (!isLoading && project) {
      if (project.status === 'intake') {
        navigate(`/projects/${projectId}/ingest`, { replace: true })
      } else if (project.status === 'planning') {
        navigate(`/projects/${projectId}/plan`, { replace: true })
      }
    }
  }, [projectId, isLoading, isError, project, navigate])

  if (isLoading || !project) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="skeleton h-8 w-48" />
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-bg">
      <aside className="flex w-60 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
            {project.name.slice(0, 1).toUpperCase()}
          </div>
          <div className="truncate text-sm font-semibold text-text">{project.name}</div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} label={item.label} Icon={item.icon} end={'end' in item ? item.end : false} />
          ))}
        </nav>

        <div className="flex items-center gap-2 border-t border-border px-5 py-4 text-xs">
          {wsConnected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-success" />
              <span className="text-success">Live</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-danger" />
              <span className="text-danger">Reconnecting…</span>
            </>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}

function NavLink({
  to,
  label,
  Icon,
  end,
}: {
  to: string
  label: string
  Icon: typeof LayoutDashboard
  end?: boolean
}) {
  return (
    <RouterNavLink
      to={to || '.'}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
          isActive ? 'bg-primary-soft text-primary font-medium' : 'text-muted hover:bg-bg hover:text-text'
        )
      }
    >
      <Icon className="h-4 w-4" />
      {label}
    </RouterNavLink>
  )
}
