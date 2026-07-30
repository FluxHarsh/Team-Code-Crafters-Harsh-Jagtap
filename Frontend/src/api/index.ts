import { api } from './client'
import type {
  Project,
  CreateProjectResponse,
  IngestMessageResponse,
  IngestDocumentResponse,
  PlanChatResponse,
  PlanDraftResponse,
  PlanApproveResponse,
  ChatMessage,
  ChatResponse,
  AgentGraphState,
  GitHubConnectResponse,
  GitHubState,
  Risk,
  RoadmapTask,
  ReprioritizeResponse,
  PitchResponse,
} from '@/types'

// ─── Projects ────────────────────────────────────────────────────────────────

export const projectsApi = {
  create: (name: string) =>
    api.post<CreateProjectResponse>('/projects', { name }),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
}

// ─── Ingest ──────────────────────────────────────────────────────────────────

export const ingestApi = {
  sendMessage: (projectId: string, message: string) =>
    api.post<IngestMessageResponse>(`/projects/${projectId}/ingest/message`, { message }),
  uploadDocument: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<IngestDocumentResponse>(
      `/projects/${projectId}/ingest/document`,
      form
    )
  },
  getHistory: (projectId: string) =>
    api.get<{ messages: ChatMessage[] }>(`/projects/${projectId}/ingest/history`),
}

// ─── Plan ────────────────────────────────────────────────────────────────────

export const planApi = {
  chat: (projectId: string, message: string) =>
    api.post<PlanChatResponse>(`/projects/${projectId}/plan/chat`, { message }),
  getDraft: (projectId: string) =>
    api.get<PlanDraftResponse>(`/projects/${projectId}/plan/draft`),
  approve: (projectId: string) =>
    api.post<PlanApproveResponse>(`/projects/${projectId}/plan/approve`),
}

// ─── Roadmap ─────────────────────────────────────────────────────────────────

export const roadmapApi = {
  get: (projectId: string) =>
    api.get<{ tasks: RoadmapTask[] }>(`/projects/${projectId}/roadmap`),
  replan: (projectId: string, reason = 'manual_request') =>
    api.post<{ status: string; roadmap: RoadmapTask[] }>(
      `/projects/${projectId}/roadmap/replan`,
      { reason }
    ),
  updateTask: (
    projectId: string,
    taskId: string,
    updates: Partial<Pick<RoadmapTask, 'status'> & { note: string }>
  ) => api.patch<{ task: RoadmapTask; risk_flagged: boolean }>(
    `/projects/${projectId}/roadmap/tasks/${taskId}`,
    updates
  ),
}

// ─── GitHub ──────────────────────────────────────────────────────────────────

export const githubApi = {
  connect: (
    projectId: string,
    data: { repo_full_name: string; access_token: string; poll_interval_seconds: number }
  ) => api.post<GitHubConnectResponse>(`/projects/${projectId}/github/connect`, data),
  getState: (projectId: string) =>
    api.get<GitHubState>(`/projects/${projectId}/github/state`),
}

// ─── Risks ───────────────────────────────────────────────────────────────────

export const risksApi = {
  get: (projectId: string) =>
    api.get<{ risks: Risk[] }>(`/projects/${projectId}/risks`),
  resolve: (projectId: string, riskId: string, resolution_note: string) =>
    api.post<{ id: string; resolved: boolean }>(
      `/projects/${projectId}/risks/${riskId}/resolve`,
      { resolution_note }
    ),
  reprioritize: (projectId: string, risk_id: string) =>
    api.post<ReprioritizeResponse>(`/projects/${projectId}/reprioritize`, { risk_id }),
}

// ─── Progress ────────────────────────────────────────────────────────────────

export const progressApi = {
  log: (projectId: string, text: string) =>
    api.post<{ logged: boolean; risk_watcher_triggered: boolean }>(
      `/projects/${projectId}/progress`,
      { text }
    ),
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export const chatApi = {
  send: (projectId: string, message: string) =>
    api.post<ChatResponse>(`/projects/${projectId}/chat`, { message }),
  getHistory: (projectId: string, cursor?: string) =>
    api.get<{ messages: ChatMessage[]; next_cursor?: string }>(
      `/projects/${projectId}/chat/history${cursor ? `?cursor=${cursor}` : ''}`
    ),
}

// ─── Pitch ───────────────────────────────────────────────────────────────────

export const pitchApi = {
  generate: (projectId: string) =>
    api.post<PitchResponse>(`/projects/${projectId}/pitch/generate`),
  get: (projectId: string) =>
    api.get<PitchResponse>(`/projects/${projectId}/pitch`),
}

// ─── Agent Graph ─────────────────────────────────────────────────────────────

export const agentGraphApi = {
  getState: (projectId: string) =>
    api.get<AgentGraphState>(`/projects/${projectId}/agent-graph/state`),
}
