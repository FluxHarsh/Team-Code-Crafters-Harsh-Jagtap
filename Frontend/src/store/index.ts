import { create } from 'zustand'
import type {
  Project,
  AgentGraphState,
  AgentNodeKey,
  AgentRunEntry,
  Risk,
  RoadmapTask,
  ChatMessage,
} from '@/types'

// ─── Project slice ────────────────────────────────────────────────────────────

interface ProjectSlice {
  project: Project | null
  setProject: (p: Project) => void
  patchProject: (updates: Partial<Project>) => void
  updateTask: (task: RoadmapTask) => void
  addRisk: (risk: Risk) => void
  resolveRisk: (riskId: string) => void
}

// ─── Agent graph live slice ───────────────────────────────────────────────────

interface AgentGraphSlice {
  agentGraph: AgentGraphState
  setActiveNode: (node: AgentNodeKey | null) => void
  addRun: (run: AgentRunEntry) => void
  setAgentGraph: (state: AgentGraphState) => void
}

// ─── Connection / WS slice ────────────────────────────────────────────────────

interface ConnectionSlice {
  wsConnected: boolean
  setWsConnected: (v: boolean) => void
}

// ─── UI slice ─────────────────────────────────────────────────────────────────

interface UISlice {
  chatPanelOpen: boolean
  setChatPanelOpen: (v: boolean) => void
  toggleChatPanel: () => void
  selectedAgentKey: string | null
  setSelectedAgentKey: (k: string | null) => void
  coachMessages: ChatMessage[]
  appendCoachMessage: (m: ChatMessage) => void
  setCoachMessages: (msgs: ChatMessage[]) => void
}

// ─── Root store ───────────────────────────────────────────────────────────────

type Store = ProjectSlice & AgentGraphSlice & ConnectionSlice & UISlice

export const useStore = create<Store>((set) => ({
  // Project
  project: null,
  setProject: (p) => set({ project: p }),
  patchProject: (updates) =>
    set((s) => ({ project: s.project ? { ...s.project, ...updates } : s.project })),
  updateTask: (task) =>
    set((s) => ({
      project: s.project
        ? {
            ...s.project,
            roadmap: s.project.roadmap?.map((t) =>
              t.id === task.id ? task : t
            ),
          }
        : s.project,
    })),
  addRisk: (risk) =>
    set((s) => ({
      project: s.project
        ? { ...s.project, risks: [risk, ...(s.project.risks ?? [])] }
        : s.project,
    })),
  resolveRisk: (riskId) =>
    set((s) => ({
      project: s.project
        ? {
            ...s.project,
            risks: s.project.risks?.map((r) =>
              r.id === riskId ? { ...r, resolved: true } : r
            ),
          }
        : s.project,
    })),

  // Agent Graph
  agentGraph: { active_node: null, recent_runs: [] },
  setActiveNode: (node) =>
    set((s) => ({ agentGraph: { ...s.agentGraph, active_node: node } })),
  addRun: (run) =>
    set((s) => ({
      agentGraph: {
        ...s.agentGraph,
        recent_runs: [run, ...s.agentGraph.recent_runs].slice(0, 20),
      },
    })),
  setAgentGraph: (state) => set({ agentGraph: state }),

  // Connection
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // UI
  chatPanelOpen: false,
  setChatPanelOpen: (v) => set({ chatPanelOpen: v }),
  toggleChatPanel: () => set((s) => ({ chatPanelOpen: !s.chatPanelOpen })),
  selectedAgentKey: null,
  setSelectedAgentKey: (k) => set({ selectedAgentKey: k }),
  coachMessages: [],
  appendCoachMessage: (m) =>
    set((s) => ({
      coachMessages: [...s.coachMessages.filter((x) => x.id !== m.id), m],
    })),
  setCoachMessages: (msgs) => set({ coachMessages: msgs }),
}))
