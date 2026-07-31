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
  PlannerSuggestion,
  TeamMember,
} from '@/types'
import { generateId } from '@/lib/utils'

export function useProjectSocket(projectId: string | undefined) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
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
    // v2
    appendPersonalMessage,
    appendGroupMessage,
    addPlannerSuggestion,
    markPlannerSuggestionAccepted,
    markPlannerSuggestionDismissed,
    upsertTeamMember,
  } = useStore()

  const handleEvent = useCallback(
    (event: WSEvent) => {
      // Backend sends "event" key, not "type"
      const eventType = event.event

      switch (eventType) {
        case 'connected':
          break

        case 'node_activated': {
          const { node, trigger, finished_at } = event.payload as {
            node: AgentNodeKey
            trigger: string
            finished_at?: string
          }
          setActiveNode(node)
          if (finished_at) {
            addRun({
              node,
              trigger: trigger as AgentRunEntry['trigger'],
              finished_at,
              status: 'done',
            })
          }
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
          const suggestion = event.payload.suggestion as PlannerSuggestion
          addPlannerSuggestion(suggestion)
          break
        }

        case 'planner_suggestion_accepted': {
          const { suggestion_id, updated_roadmap } = event.payload as {
            suggestion_id: string
            updated_roadmap?: RoadmapTask[]
          }
          markPlannerSuggestionAccepted(suggestion_id)
          if (updated_roadmap) patchProject({ roadmap: updated_roadmap })
          break
        }

        case 'planner_suggestion_dismissed': {
          const { suggestion_id } = event.payload as { suggestion_id: string }
          markPlannerSuggestionDismissed(suggestion_id)
          break
        }

        case 'team_updated': {
          const member = event.payload.member as TeamMember
          upsertTeamMember(member)
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
        upsertTeamMember,
    ]
  )

  const connect = useCallback(() => {
    if (!projectId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/projects/${projectId}/updates`)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
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
      reconnectTimer.current = setTimeout(() => connect(), 3000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [projectId, setWsConnected, handleEvent])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
      setWsConnected(false)
    }
  }, [connect, setWsConnected])
}