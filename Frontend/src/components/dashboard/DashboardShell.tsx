import { Link, Outlet, useParams, useNavigate, useLocation } from 'react-router-dom'
import { MessageSquare, Bell, LayoutDashboard, GitBranch } from 'lucide-react'
import { useStore } from '@/store'
import { useProject } from '@/hooks/useProject'
import { useProjectSocket } from '@/hooks/useProjectSocket'
import { AGENT_LIST } from '@/lib/agents'
import { formatHours } from '@/lib/utils'
import { AgentNavItem } from './AgentNavItem'
import { CoachChatPanel } from '@/components/chat/CoachChatPanel'
import { SkeletonTile } from '@/components/ui'

export function DashboardShell() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const { data: project, isLoading } = useProject(projectId)
  const { wsConnected, toggleChatPanel } = useStore()

  // Establish WebSocket
  useProjectSocket(projectId)

  // Route guard
  if (!isLoading && project) {
    if (project.status === 'intake') {
      navigate(`/projects/${projectId}/ingest`, { replace: true })
    } else if (project.status === 'planning') {
      navigate(`/projects/${projectId}/plan`, { replace: true })
    }
  }

  const isOverview = location.pathname === `/projects/${projectId}/dashboard`
  const isPitch = location.pathname.includes('/pitch')

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* ── Sidebar ── */}
      <aside className="w-[220px] flex-none bg-white border-r border-border flex flex-col overflow-y-auto">
        {/* Brand */}
        <div className="px-4 py-4 flex items-center gap-2.5 border-b border-border-soft">
          <div className="w-7 h-7 rounded-[9px] bg-primary flex items-center justify-center font-800 text-white text-xs shadow-md shadow-primary/30 flex-none">
            HC
          </div>
          <div>
            <p className="text-sm font-800 text-navy leading-none">Coach</p>
            <p className="text-[10px] text-muted-2 mt-0.5">
              {isLoading ? (
                <SkeletonTile className="h-2.5 w-20 inline-block" />
              ) : (
                project?.name ?? 'Hackathon'
              )}
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-4">
          {/* Main */}
          <div>
            <p className="text-[10px] font-700 uppercase tracking-widest text-muted-2 px-2.5 mb-1.5">
              Workspace
            </p>
            <div className="space-y-0.5">
              <Link
                to={`/projects/${projectId}/dashboard`}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-[9px] text-xs transition border-l-[3px] ${
                  isOverview
                    ? 'bg-primary-soft border-primary text-primary-dark font-700 rounded-l-none'
                    : 'border-transparent text-text hover:bg-bg font-500'
                }`}
              >
                <div className="w-6 h-6 rounded-[7px] bg-navy-soft text-navy flex items-center justify-center flex-none">
                  <LayoutDashboard size={12} />
                </div>
                Overview
              </Link>
              <Link
                to={`/projects/${projectId}/dashboard/pitch`}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-[9px] text-xs transition border-l-[3px] ${
                  isPitch
                    ? 'bg-primary-soft border-primary text-primary-dark font-700 rounded-l-none'
                    : 'border-transparent text-text hover:bg-bg font-500'
                }`}
              >
                <div className="w-6 h-6 rounded-[7px] bg-success-soft text-success-dark flex items-center justify-center flex-none">
                  <GitBranch size={12} />
                </div>
                Pitch
              </Link>
            </div>
          </div>

          {/* Agents */}
          <div>
            <p className="text-[10px] font-700 uppercase tracking-widest text-muted-2 px-2.5 mb-1.5">
              Agents
            </p>
            <div className="space-y-0.5">
              {AGENT_LIST.map((agent) => (
                <AgentNavItem key={agent.key} agent={agent} projectId={projectId!} />
              ))}
            </div>
          </div>
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-border-soft">
          {/* Hours remaining */}
          {project && (
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-[10px] text-muted-2 font-600">Time left</span>
              <span className="text-xs font-800 text-navy font-mono">
                {formatHours(project.hours_remaining)}
              </span>
            </div>
          )}
          {/* WS status */}
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-none ${wsConnected ? 'dot-live' : 'bg-danger'}`}
            />
            <span className="text-[10px] text-muted-2">
              {wsConnected ? 'Live updates on' : 'Reconnecting…'}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-13 bg-white border-b border-border flex items-center px-5 gap-3 flex-none">
          <div className="flex-1 min-w-0">
            {isLoading ? (
              <SkeletonTile className="h-4 w-48" />
            ) : (
              <h1 className="text-sm font-700 text-navy truncate">{project?.name}</h1>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Notification bell (static for now) */}
            <button className="w-8 h-8 rounded-[9px] border border-border bg-white hover:bg-bg flex items-center justify-center relative text-muted transition">
              <Bell size={14} />
            </button>

            {/* Coach chat toggle */}
            <button
              onClick={toggleChatPanel}
              className="flex items-center gap-1.5 h-8 px-3 rounded-[9px] bg-primary text-white text-xs font-600 hover:bg-primary-dark transition shadow-sm shadow-primary/25"
            >
              <MessageSquare size={13} />
              Ask Coach
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* Coach Chat Panel */}
      {projectId && <CoachChatPanel projectId={projectId} />}
    </div>
  )
}
