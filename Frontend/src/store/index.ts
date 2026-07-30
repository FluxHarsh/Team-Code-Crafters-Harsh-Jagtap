import { create } from 'zustand'
import type {
  Project,
  AgentNodeKey,
  AgentRunEntry,
  Risk,
  RoadmapTask,
  ChatMessage,
  TeamMember,
  PlannerSuggestion,
  GitHubInsight,
  ProjectFile,
} from '@/types'

interface StoreState {
  // ─── Project ────────────────────────────────────────────────────────────
  project: Project | null
  setProject: (project: Project) => void
  patchProject: (patch: Partial<Project>) => void
  updateTask: (task: RoadmapTask) => void
  addRisk: (risk: Risk) => void
  resolveRisk: (riskId: string) => void

  // ─── WebSocket ──────────────────────────────────────────────────────────
  wsConnected: boolean
  setWsConnected: (connected: boolean) => void

  // ─── Agent graph ────────────────────────────────────────────────────────
  activeNode: AgentNodeKey | null
  recentRuns: AgentRunEntry[]
  setActiveNode: (node: AgentNodeKey | null) => void
  addRun: (run: AgentRunEntry) => void

  // ─── Chat (legacy single coaching thread, kept for AgentPage) ──────────
  coachMessages: ChatMessage[]
  appendCoachMessage: (msg: ChatMessage) => void

  // ─── v2: Personal / Group chat ──────────────────────────────────────────
  personalMessages: ChatMessage[]
  groupMessages: ChatMessage[]
  appendPersonalMessage: (msg: ChatMessage) => void
  appendGroupMessage: (msg: ChatMessage) => void

  // ─── v2: Team members ─────────────────────────────────────────────────
  teamMembers: TeamMember[]
  setTeamMembers: (members: TeamMember[]) => void
  upsertTeamMember: (member: TeamMember) => void
  removeTeamMember: (memberId: string) => void

  // ─── v2: Planner suggestions ─────────────────────────────────────────
  plannerSuggestions: PlannerSuggestion[]
  setPlannerSuggestions: (suggestions: PlannerSuggestion[]) => void
  addPlannerSuggestion: (suggestion: PlannerSuggestion) => void
  markPlannerSuggestionAccepted: (suggestionId: string) => void

  // ─── v2: GitHub insights ─────────────────────────────────────────────
  githubInsights: GitHubInsight[]
  setGithubInsights: (insights: GitHubInsight[]) => void
  addGithubInsight: (insight: GitHubInsight) => void

  // ─── v2: Files ───────────────────────────────────────────────────────
  files: ProjectFile[]
  setFiles: (files: ProjectFile[]) => void
  upsertFile: (file: ProjectFile) => void
}

export const useStore = create<StoreState>((set) => ({
  // ─── Project ────────────────────────────────────────────────────────────
  project: null,
  setProject: (project) => set({ project }),
  patchProject: (patch) =>
    set((state) => ({ project: state.project ? { ...state.project, ...patch } : state.project })),
  updateTask: (task) =>
    set((state) => {
      if (!state.project?.roadmap) return state
      return {
        project: {
          ...state.project,
          roadmap: state.project.roadmap.map((t) => (t.id === task.id ? task : t)),
        },
      }
    }),
  addRisk: (risk) =>
    set((state) => {
      if (!state.project) return state
      const risks = state.project.risks ? [...state.project.risks, risk] : [risk]
      return { project: { ...state.project, risks } }
    }),
  resolveRisk: (riskId) =>
    set((state) => {
      if (!state.project?.risks) return state
      return {
        project: {
          ...state.project,
          risks: state.project.risks.map((r) => (r.id === riskId ? { ...r, resolved: true } : r)),
        },
      }
    }),

  // ─── WebSocket ──────────────────────────────────────────────────────────
  wsConnected: false,
  setWsConnected: (wsConnected) => set({ wsConnected }),

  // ─── Agent graph ────────────────────────────────────────────────────────
  activeNode: null,
  recentRuns: [],
  setActiveNode: (activeNode) => set({ activeNode }),
  addRun: (run) => set((state) => ({ recentRuns: [run, ...state.recentRuns].slice(0, 50) })),

  // ─── Chat (legacy single coaching thread, kept for AgentPage) ──────────
  coachMessages: [],
  appendCoachMessage: (msg) => set((state) => ({ coachMessages: [...state.coachMessages, msg] })),

  // ─── v2: Personal / Group chat ──────────────────────────────────────────
  personalMessages: [],
  groupMessages: [],
  appendPersonalMessage: (msg) =>
    set((state) => ({ personalMessages: [...state.personalMessages, msg] })),
  appendGroupMessage: (msg) =>
    set((state) => ({ groupMessages: [...state.groupMessages, msg] })),

  // ─── v2: Team members ─────────────────────────────────────────────────
  teamMembers: [],
  setTeamMembers: (teamMembers) => set({ teamMembers }),
  upsertTeamMember: (member) =>
    set((state) => {
      const exists = state.teamMembers.some((m) => m.id === member.id)
      return {
        teamMembers: exists
          ? state.teamMembers.map((m) => (m.id === member.id ? member : m))
          : [...state.teamMembers, member],
      }
    }),
  removeTeamMember: (memberId) =>
    set((state) => ({ teamMembers: state.teamMembers.filter((m) => m.id !== memberId) })),

  // ─── v2: Planner suggestions ─────────────────────────────────────────
  plannerSuggestions: [],
  setPlannerSuggestions: (plannerSuggestions) => set({ plannerSuggestions }),
  addPlannerSuggestion: (suggestion) =>
    set((state) => ({ plannerSuggestions: [suggestion, ...state.plannerSuggestions] })),
  markPlannerSuggestionAccepted: (suggestionId) =>
    set((state) => ({
      plannerSuggestions: state.plannerSuggestions.map((s) =>
        s.id === suggestionId ? { ...s, status: 'accepted' } : s
      ),
    })),

  // ─── v2: GitHub insights ─────────────────────────────────────────────
  githubInsights: [],
  setGithubInsights: (githubInsights) => set({ githubInsights }),
  addGithubInsight: (insight) =>
    set((state) => ({ githubInsights: [insight, ...state.githubInsights] })),

  // ─── v2: Files ───────────────────────────────────────────────────────
  files: [],
  setFiles: (files) => set({ files }),
  upsertFile: (file) =>
    set((state) => {
      const exists = state.files.some((f) => f.id === file.id)
      return {
        files: exists ? state.files.map((f) => (f.id === file.id ? file : f)) : [...state.files, file],
      }
    }),
}))

// Non-hook accessor used inside the WS handler (matches existing usage of
// useStore.getState() in useProjectSocket.ts)
export const getStoreState = () => useStore.getState()
