import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useStore } from '@/store'
import type { WSEvent, AgentNodeKey, AgentRunEntry, Risk, RoadmapTask, ChatMessage } from '@/types'
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
          const msg = event.payload as unknown as ChatMessage
          if (!msg.phase || msg.phase === 'coaching') {
            appendCoachMessage({ ...msg, id: msg.id || generateId() })
          }
          break
        }
      }
    },
    [projectId, queryClient, setActiveNode, addRun, addRisk, resolveRisk, updateTask, patchProject, appendCoachMessage]
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