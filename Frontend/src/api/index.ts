import { api } from './client'
import type {
  Project,
  CreateProjectResponse,
  ContextMessageResponse,
  ContextFileUploadResponse,
  ChatMessage,
  ChatHistoryResponse,
  PlannerDraftRequest,
  PlannerDraftResponse,
  PlannerFeedbackRequest,
  PlannerFeedbackResponse,
  PlannerApproveResponse,
  PlannerHistoryResponse,
  PlannerSuggestionsResponse,
  AcceptPlannerSuggestionResponse,
  ScopeCriticRunResponse,
  GitHubConnectResponse,
  GitHubInsightsResponse,
  PersonalChatRequest,
  PersonalChatResponse,
  GroupChatRequest,
  GroupChatResponse,
  AddTeamMemberRequest,
  TeamMembersResponse,
  FileUploadResponse,
  FilesResponse,
  DashboardSummaryResponse,
  PitchResponse,
  PitchHistoryResponse,
} from '@/types'

// ─── Projects ─────────────────────────────────────────────────────────────

export const projectsApi = {
  create: (idea: string) => api.post<CreateProjectResponse>('/projects', { idea }),
  get: (projectId: string) => api.get<Project>(`/projects/${projectId}`),
}

// ─── Project Context (was ingestApi) ───────────────────────────────────────
// /ingest/* is deprecated in v2, kept temporarily but marked for removal.
// Frontend now calls the v2 /context/* endpoints exclusively.

export const projectContextApi = {
  sendMessage: (projectId: string, content: string) =>
    api.post<ContextMessageResponse>(`/projects/${projectId}/context/message`, { content }),

  uploadFile: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<ContextFileUploadResponse>(`/projects/${projectId}/context/files`, form)
  },

  getHistory: (projectId: string) =>
    api.get<ChatHistoryResponse>(`/projects/${projectId}/context/history`),
}

// ─── Planner (was planApi) ──────────────────────────────────────────────────
// v2 is iterative and versioned — draft → feedback → approve — there is no
// single "chat" endpoint anymore. roadmapApi.replan is gone; suggestions
// are accepted through plannerSuggestionsApi instead.

export const plannerApi = {
  draft: (projectId: string, body?: PlannerDraftRequest) =>
    api.post<PlannerDraftResponse>(`/projects/${projectId}/planner/draft`, body),

  feedback: (projectId: string, body: PlannerFeedbackRequest) =>
    api.post<PlannerFeedbackResponse>(`/projects/${projectId}/planner/feedback`, body),

  approve: (projectId: string) =>
    api.post<PlannerApproveResponse>(`/projects/${projectId}/planner/approve`),

  history: (projectId: string) =>
    api.get<PlannerHistoryResponse>(`/projects/${projectId}/planner/history`),
}

// ─── Planner Suggestions (replaces roadmapApi.replan / risksApi.reprioritize) ─
// The old /roadmap/replan and /reprioritize endpoints, and the Reprioritizer
// agent node, no longer exist. The Risk Watcher now produces suggestions
// that the user explicitly accepts or dismisses.

export const plannerSuggestionsApi = {
  list: (projectId: string) =>
    api.get<PlannerSuggestionsResponse>(`/projects/${projectId}/planner-suggestions`),

  accept: (projectId: string, suggestionId: string) =>
    api.post<AcceptPlannerSuggestionResponse>(
      `/projects/${projectId}/planner-suggestions/${suggestionId}/accept`
    ),

  dismiss: (projectId: string, suggestionId: string) =>
    api.post<{ dismissed: boolean }>(
      `/projects/${projectId}/planner-suggestions/${suggestionId}/dismiss`
    ),
}

// ─── Scope Critic ────────────────────────────────────────────────────────────

export const scopeCriticApi = {
  run: (projectId: string) =>
    api.post<ScopeCriticRunResponse>(`/projects/${projectId}/scope-critic/run`),
}

// ─── GitHub ──────────────────────────────────────────────────────────────────

export const githubApi = {
  connect: (projectId: string, repoUrl: string) =>
    api.post<GitHubConnectResponse>(`/projects/${projectId}/github/connect`, { repo_url: repoUrl }),
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
    api.post<TeamMembersResponse>(`/projects/${projectId}/team-members`, body),

  remove: (projectId: string, memberId: string) =>
    api.post<{ removed: boolean }>(`/projects/${projectId}/team-members/${memberId}/remove`),
}

// ─── Files (general upload surface — not just project-context intake) ──────

export const fileUploadApi = {
  upload: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<FileUploadResponse>(`/projects/${projectId}/files`, form)
  },

  list: (projectId: string) => api.get<FilesResponse>(`/projects/${projectId}/files`),
}

// ─── Dashboard aggregation ───────────────────────────────────────────────────

export const dashboardApi = {
  summary: (projectId: string) =>
    api.get<DashboardSummaryResponse>(`/projects/${projectId}/dashboard`),

  kanban: (projectId: string) =>
    api.get<DashboardSummaryResponse>(`/projects/${projectId}/dashboard/kanban`),
}

// ─── Pitch ───────────────────────────────────────────────────────────────────

export const pitchApi = {
  get: (projectId: string) => api.get<PitchResponse>(`/projects/${projectId}/pitch`),

  regenerate: (projectId: string) =>
    api.post<PitchResponse>(`/projects/${projectId}/pitch/regenerate`),

  getHistory: (projectId: string) =>
    api.get<PitchHistoryResponse>(`/projects/${projectId}/pitch/history`),
}

// ─── Chat message helper type re-export (used by some hooks) ───────────────

export type { ChatMessage }
