import { api } from './client'
import type {
  Project,
  CreateProjectResponse,
  IngestMessageResponse,
  IngestDocumentResponse,
  ChatMessage,
  ChatHistoryResponse,
  PlannerDraftResponse,
  PlannerFeedbackRequest,
  PlannerFeedbackResponse,
  PlannerApproveResponse,
  PlannerHistoryResponse,
  PlannerSuggestionsResponse,
  AcceptPlannerSuggestionResponse,
  DismissPlannerSuggestionResponse,
  GitHubConnectResponse,
  GitHubInsightsResponse,
  PersonalChatRequest,
  PersonalChatResponse,
  GroupChatRequest,
  GroupChatResponse,
  AddTeamMemberRequest,
  TeamMember,
  TeamMembersResponse,
  RoadmapTask,
  DashboardOverview,
  DashboardKanbanResponse,
  PitchResponse,
  PitchGenerateResponse,
} from '@/types'

// ─── Projects ─────────────────────────────────────────────────────────────

export const projectsApi = {
  create: (name: string) => api.post<CreateProjectResponse>('/projects', { name }),
  get: (projectId: string) => api.get<Project>(`/projects/${projectId}`),
}

// ─── Ingest ──────────────────────────────────────────────────────────────

export const ingestApi = {
  sendMessage: (projectId: string, content: string) =>
    api.post<IngestMessageResponse>(`/projects/${projectId}/ingest/message`, { message: content }),

  uploadDocument: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<IngestDocumentResponse>(`/projects/${projectId}/ingest/document`, form)
  },

  getHistory: (projectId: string) =>
    api.get<ChatHistoryResponse>(`/projects/${projectId}/ingest/history`),
}

// ─── Planner (was planApi) ──────────────────────────────────────────────────
// v1 backend surface: draft (GET /plan/draft) → feedback (POST /plan/chat) →
// approve (POST /plan/approve).

export const roadmapTasksApi = {
  move: (projectId: string, taskId: string, status: RoadmapTask['status']) =>
    api.patch<{ task: RoadmapTask; risk_flagged: boolean }>(
      `/projects/${projectId}/roadmap/tasks/${taskId}`,
      { status }
    ),
}

export const plannerApi = {
  draft: (projectId: string) =>
    api.get<PlannerDraftResponse>(`/projects/${projectId}/plan/draft`),

  feedback: (projectId: string, body: PlannerFeedbackRequest) =>
    api.post<PlannerFeedbackResponse>(`/projects/${projectId}/plan/chat`, body),

  approve: (projectId: string) =>
    api.post<PlannerApproveResponse>(`/projects/${projectId}/plan/approve`),

  history: (projectId: string) =>
    api.get<PlannerHistoryResponse>(`/projects/${projectId}/planner/history`),
}

// ─── Planner Suggestions ────────────────────────────────────────────────────
// The Risk Watcher produces suggestions that the user explicitly accepts
// or dismisses.

export const plannerSuggestionsApi = {
  list: (projectId: string) =>
    api.get<PlannerSuggestionsResponse>(`/projects/${projectId}/planner/suggestions`),

  accept: (projectId: string, suggestionId: string) =>
    api.post<AcceptPlannerSuggestionResponse>(
      `/projects/${projectId}/planner/suggestions/${suggestionId}/accept`
    ),

  dismiss: (projectId: string, suggestionId: string) =>
    api.post<DismissPlannerSuggestionResponse>(
      `/projects/${projectId}/planner/suggestions/${suggestionId}/dismiss`
    ),
}

// ─── GitHub ──────────────────────────────────────────────────────────────────

export const githubApi = {
  connect: (
    projectId: string,
    body: { repo_full_name: string; access_token: string; poll_interval_seconds: number }
  ) => api.post<GitHubConnectResponse>(`/projects/${projectId}/github/connect`, body),
}

export const githubInsightsApi = {
  list: (projectId: string) =>
    api.get<GitHubInsightsResponse>(`/projects/${projectId}/github/insights`),
}

// ─── Chat — split into personal / group (was a single chatApi) ─────────────

export const personalChatApi = {
  send: (projectId: string, body: PersonalChatRequest) =>
    api.post<PersonalChatResponse>(`/projects/${projectId}/chat/personal`, body),

  history: (projectId: string) =>
    api.get<ChatHistoryResponse>(`/projects/${projectId}/chat/personal/history`),
}

export const groupChatApi = {
  send: (projectId: string, body: GroupChatRequest) =>
    api.post<GroupChatResponse>(`/projects/${projectId}/chat/group`, body),

  history: (projectId: string) =>
    api.get<ChatHistoryResponse>(`/projects/${projectId}/chat/group/history`),
}

// ─── Team Members ────────────────────────────────────────────────────────────

export const teamMembersApi = {
  list: (projectId: string) =>
    api.get<TeamMembersResponse>(`/projects/${projectId}/team-members`),

  add: (projectId: string, body: AddTeamMemberRequest) =>
    api.post<TeamMember>(`/projects/${projectId}/team-members`, body),

  remove: (projectId: string, memberId: string) =>
    api.delete<void>(`/projects/${projectId}/team-members/${memberId}`),
}

// ─── Dashboard aggregation ───────────────────────────────────────────────────

export const dashboardApi = {
  overview: (projectId: string) =>
    api.get<DashboardOverview>(`/projects/${projectId}/dashboard/overview`),

  kanban: (projectId: string) =>
    api.get<DashboardKanbanResponse>(`/projects/${projectId}/dashboard/kanban`),
}

// ─── Pitch ───────────────────────────────────────────────────────────────────

export const pitchApi = {
  get: (projectId: string) => api.get<PitchResponse>(`/projects/${projectId}/pitch`),

  generate: (projectId: string) =>
    api.post<PitchGenerateResponse>(`/projects/${projectId}/pitch/generate`),
}

// ─── Chat message helper type re-export (used by some hooks) ───────────────

export type { ChatMessage }
