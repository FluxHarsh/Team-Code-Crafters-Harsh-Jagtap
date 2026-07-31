import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useStore } from '@/store'
import type {
  WSEvent,
  AgentNodeKey,
  AgentRunEntry,
  Risk,
  RoadmapTask,
  ChatMessage,
  TeamMember,
} from '@/types'
import { generateId } from '@/lib/utils'

export function useProjectSocket(projectId: string | undefined) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isIntentionalCloseRef = useRef<boolean>(false)
  const queryClient = useQueryClient()

  const {
    setWsConnected,
    setActiveNode,
    addRun,
    addRisk,
    resolveRisk,
    updateTask,
    patchProject,
    appendCoachMessage,
    appendPersonalMessage,
    appendGroupMessage,
    addPlannerSuggestion,
    markPlannerSuggestionAccepted,
    markPlannerSuggestionDismissed,
    setTeamMembers,
  } = useStore()

  const handleEvent = useCallback(
    (event: WSEvent) => {
      // Backend sends "event" key, not "type"
      const eventType = event.event

      switch (eventType) {
        case 'connected':
          break

        case 'node_activated': {
          const { node, trigger } = event.payload as {
            node: AgentNodeKey
            trigger: string
          }
          setActiveNode(node)
          // The backend payload has no finished_at, so synthesize one to
          // populate the AgentPage run history.
          addRun({
            node,
            trigger: trigger as AgentRunEntry['trigger'],
            finished_at: new Date().toISOString(),
            status: 'done',
          })
          break
        }

        case 'state_updated': {
          queryClient.invalidateQueries({ queryKey: ['project', projectId] })
          const { path, value } = event.payload as { path: string; value: unknown }
          if (path === 'roadmap') patchProject({ roadmap: value as RoadmapTask[] })
          if (path === 'risks') patchProject({ risks: value as Risk[] })
          if (path === 'hours_remaining') patchProject({ hours_remaining: value as number })
          break
        }

        case 'task_moved': {
          const { task_id, to } = event.payload as { task_id: string; from: string; to: string }
          const project = useStore.getState().project
          const task = project?.roadmap?.find((t) => t.id === task_id)
          if (task) updateTask({ ...task, status: to as RoadmapTask['status'] })
          break
        }

        case 'risk_flagged': {
          addRisk(event.payload.risk as Risk)
          break
        }

        case 'risk_resolved': {
          resolveRisk(event.payload.risk_id as string)
          break
        }

        case 'plan_approved': {
          queryClient.invalidateQueries({ queryKey: ['project', projectId] })
          break
        }

        case 'plan_draft_updated': {
          queryClient.invalidateQueries({ queryKey: ['plan-draft', projectId] })
          break
        }

        case 'pitch_ready': {
          queryClient.invalidateQueries({ queryKey: ['pitch', projectId] })
          patchProject({ pitch_outline: {} as never })
          break
        }

        case 'chat_message': {
          // Legacy single-thread coaching event. Kept for backward
          // compatibility during the v1 → v2 transition; the backend now
          // prefers 'personal_chat_message' / 'group_chat_message' below.
          const msg = event.payload as unknown as ChatMessage
          if (!msg.phase || (msg.phase !== 'personal' && msg.phase !== 'group')) {
            appendCoachMessage({ ...msg, id: msg.id || generateId() })
          }
          break
        }

        // ─── v2 events ──────────────────────────────────────────────────

        case 'planner_revision_created': {
          // A new planner draft/feedback version was produced — refetch
          // the draft/history rather than trying to patch it in place.
          queryClient.invalidateQueries({ queryKey: ['plan-draft', projectId] })
          queryClient.invalidateQueries({ queryKey: ['planner-history', projectId] })
          break
        }

        case 'planner_suggestion_created': {
          // Backend broadcasts { id, risk_id, decision, rationale }.
          const { id, risk_id, decision, rationale } = event.payload as {
            id: string
            risk_id?: string | null
            decision?: string | null
            rationale: string
          }
          addPlannerSuggestion({
            id,
            source: 'risk_reprioritization',
            risk_id,
            decision,
            rationale,
            status: 'pending',
            created_at: new Date().toISOString(),
          })
          break
        }

        case 'planner_suggestion_accepted': {
          // Backend broadcasts { id } only; the roadmap change is applied
          // server-side, so refetch the project + board.
          const { id } = event.payload as { id: string }
          markPlannerSuggestionAccepted(id)
          queryClient.invalidateQueries({ queryKey: ['project', projectId] })
          queryClient.invalidateQueries({ queryKey: ['dashboard-kanban', projectId] })
          queryClient.invalidateQueries({ queryKey: ['dashboard-overview', projectId] })
          queryClient.invalidateQueries({ queryKey: ['planner-suggestions', projectId] })
          break
        }

        case 'planner_suggestion_dismissed': {
          // Backend broadcasts { id } only.
          const { id } = event.payload as { id: string }
          markPlannerSuggestionDismissed(id)
          queryClient.invalidateQueries({ queryKey: ['planner-suggestions', projectId] })
          break
        }

        case 'team_updated': {
          // Backend broadcasts { team: [...] } — replace the whole list.
          const { team } = event.payload as { team: TeamMember[] }
          setTeamMembers(team)
          break
        }

        case 'group_chat_message': {
          const msg = event.payload as unknown as ChatMessage
          appendGroupMessage({ ...msg, id: msg.id || generateId(), phase: 'group' })
          break
        }

        case 'personal_chat_message': {
          const msg = event.payload as unknown as ChatMessage
          appendPersonalMessage({ ...msg, id: msg.id || generateId(), phase: 'personal' })
          break
        }
      }
    },
    [
      projectId,
      queryClient,
      setActiveNode,
      addRun,
      addRisk,
      resolveRisk,
      updateTask,
      patchProject,
      appendCoachMessage,
      appendPersonalMessage,
      appendGroupMessage,
      addPlannerSuggestion,
      markPlannerSuggestionAccepted,
      markPlannerSuggestionDismissed,
      setTeamMembers,
    ]
  )

  const connect = useCallback(() => {
    if (!projectId) return

    // Close existing socket if open before establishing a new connection
    if (wsRef.current) {
      isIntentionalCloseRef.current = true
      wsRef.current.close()
      wsRef.current = null
    }

    isIntentionalCloseRef.current = false

    const envWsUrl = import.meta.env?.VITE_WS_BASE_URL
    let wsUrl: string
    if (envWsUrl) {
      wsUrl = `${envWsUrl}/api/v1/projects/${projectId}/updates`
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsUrl = `${protocol}//${window.location.host}/api/v1/projects/${projectId}/updates`
    }

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        handleEvent(event)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
      if (!isIntentionalCloseRef.current) {
        reconnectTimer.current = setTimeout(() => connect(), 3000)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [projectId, setWsConnected, handleEvent])

  useEffect(() => {
    connect()
    return () => {
      isIntentionalCloseRef.current = true
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
      setWsConnected(false)
    }
  }, [connect, setWsConnected])
}