// ─── Project ────────────────────────────────────────────────────────────────

// v2: 'intake' renamed to 'project_context'
export type ProjectStatus =
  | 'project_context'
  | 'planning'
  | 'active'
  | 'at_risk'
  | 'pitch_ready'
  | 'submitted'

export interface ProjectIdea {
  raw: string
  refined?: string
}

export interface ScopeData {
  mvp_features: string[]
  cut_features: string[]
  assumptions: string[]
}

export interface RoadmapTask {
  id: string
  task: string
  owner: string
  eta: string
  status: 'todo' | 'in_progress' | 'blocked' | 'done'
  // v2: dependency edges (Neo4j BLOCKED_BY), optional since not all
  // endpoints return them yet — see Build Deck connector-line plan
  depends_on?: string[]
}

export interface Risk {
  id: string
  risk: string
  severity: 'high' | 'med' | 'low'
  suggested_fix: string
  resolved: boolean
}

export interface ProgressEntry {
  source: 'manual' | 'github'
  text: string
  ts: string
}

export interface GitHubState {
  commits: GitHubCommit[]
  open_prs: GitHubPR[]
  // branches not returned by GET /github/state — omitted
  issues: GitHubIssue[]
  last_polled_at?: string
}

export interface GitHubCommit {
  sha: string
  message: string
  matched_task?: string
}

export interface GitHubPR {
  number: number
  title?: string
  status: string
  hours_open: number
}

export interface GitHubIssue {
  number: number
  title?: string
  state: string
  eta_breach: boolean
}

export interface PitchOutline {
  // hook and ask may not exist in older stored pitch rows
  hook?: string
  problem: string
  solution: string
  demo_flow: string[]
  differentiator: string
  ask?: string
}

// ─── v2 additions: Team, Files, GitHub Insights, Planner Suggestions ────────

export interface TeamMember {
  id: string
  name: string
  email?: string
  role?: string
  avatar_initials: string
  joined_at?: string
}

export type FileStatus = 'uploading' | 'processing' | 'processed' | 'failed'

export interface ProjectFile {
  id: string
  filename: string
  content_type: string
  status: FileStatus
  extracted_chars?: number
  uploaded_by?: string
  created_at?: string
}

export interface GitHubInsight {
  id: string
  summary: string
  related_task?: string
  severity?: 'info' | 'warn' | 'critical'
  created_at: string
}

export interface PlannerSuggestion {
  id: string
  title: string
  rationale: string
  diff_summary?: string
  status: 'pending' | 'accepted' | 'dismissed'
  created_at: string
}

export interface ScopeCriticFinding {
  id: string
  concern: string
  related_feature?: string
  severity: 'high' | 'med' | 'low'
}

export interface DashboardSummary {
  percent_complete: number
  building_count: number
  blocked_count: number
  shipped_count: number
  total_count: number
  commit_count: number
  hours_remaining: number
}

export interface Project {
  id: string
  name: string
  status: ProjectStatus
  project_idea?: ProjectIdea
  scope?: ScopeData
  roadmap?: RoadmapTask[]
  risks?: Risk[]
  // backend GET /projects/{id} does not return these — kept optional so
  // code that references them doesn't crash, but never populated from API
  progress_log?: ProgressEntry[]
  github_state?: GitHubState | null
  pitch_outline?: PitchOutline | null
  next_action?: string
  hours_remaining: number
  // backend does not return these fields either
  plan_approved_at?: string | null
  created_at?: string
  updated_at?: string
  // v2
  team_members?: TeamMember[]
  files?: ProjectFile[]
}

// ─── Chat ───────────────────────────────────────────────────────────────────

// v2: 'intake' phase renamed to 'project_context'; single coaching chat
// split into personal/group
export type ChatPhase = 'project_context' | 'planning' | 'personal' | 'group'
export type ChatRole = 'user' | 'agent'

export interface ChatMessage {
  id: string
  project_id?: string
  // phase is not returned by GET /context/history or GET /chat/*/history
  phase?: ChatPhase
  role: ChatRole
  agent_node?: string
  speaker_name?: string
  content: string
  // created_at is not returned by GET /context/history
  created_at?: string
}

// ─── Agent Graph ─────────────────────────────────────────────────────────────

// v2 node roster — 'intake' → 'project_context_builder',
// 'reprioritizer' removed, 'planner_suggestion' + 'file_intake' +
// 'team_assistant' added
export type AgentNodeKey =
  | 'supervisor'
  | 'project_context_builder'
  | 'scope_critic'
  | 'planner'
  | 'planner_suggestion'
  | 'github_watcher'
  | 'risk_watcher'
  | 'file_intake'
  | 'pitch_agent'
  | 'team_assistant'

export interface AgentRunEntry {
  node: AgentNodeKey
  trigger: 'user_action' | 'scheduled_poll' | 're-plan'
  finished_at: string
  // status not returned by GET /agent-graph/state
  status?: 'done' | 'failed' | 'running'
}

export interface AgentGraphState {
  active_node: AgentNodeKey | null
  recent_runs: AgentRunEntry[]
}

// ─── WebSocket Events ────────────────────────────────────────────────────────

// v2: 9 new event types added alongside the original 10
export type WSEventType =
  | 'plan_draft_updated'
  | 'plan_approved'
  | 'node_activated'
  | 'state_updated'
  | 'task_moved'
  | 'risk_flagged'
  | 'risk_resolved'
  | 'pitch_ready'
  | 'chat_message'
  | 'connected'
  // v2 additions
  | 'planner_revision_created'
  | 'planner_suggestion_created'
  | 'planner_suggestion_accepted'
  | 'github_insight_created'
  | 'project_context_updated'
  | 'file_processed'
  | 'team_updated'
  | 'group_chat_message'
  | 'personal_chat_message'

// Backend sends {"event": "...", "payload": {...}}
export interface WSEvent {
  event: WSEventType   // ← was "type", backend sends "event"
  payload: Record<string, unknown>
}

// ─── API Request/Response types ─────────────────────────────────────────────

export interface CreateProjectResponse {
  project_id: string
  status: ProjectStatus
  greeting: string
}

// projectContextApi (was ingestApi)
export interface ContextMessageResponse {
  reply: string
  ready_for_planning: boolean
}

export interface ContextFileUploadResponse {
  document_id: string
  filename: string
  extracted_chars: number
}

// plannerApi (was planApi) — iterative, versioned; no single "chat" endpoint
export interface PlannerDraftRequest {
  notes?: string
}

export interface PlannerDraftResponse {
  version: number
  draft_scope: ScopeData
  draft_roadmap: RoadmapTask[]
}

export interface PlannerFeedbackRequest {
  feedback: string
}

export interface PlannerFeedbackResponse {
  version: number
  reply: string
  draft_scope: ScopeData
  draft_roadmap: RoadmapTask[]
}

export interface PlannerApproveResponse {
  status: ProjectStatus
  plan_approved_at: string
  dashboard_ready: boolean
}

export interface PlannerHistoryEntry {
  version: number
  draft_scope: ScopeData
  draft_roadmap: RoadmapTask[]
  created_at: string
}

export interface PlannerHistoryResponse {
  versions: PlannerHistoryEntry[]
}

// planner suggestions (replaces roadmapApi.replan / risksApi.reprioritize)
export interface PlannerSuggestionsResponse {
  suggestions: PlannerSuggestion[]
}

export interface AcceptPlannerSuggestionResponse {
  accepted: boolean
  updated_roadmap: RoadmapTask[]
}

// scope critic
export interface ScopeCriticRunResponse {
  findings: ScopeCriticFinding[]
}

// github
export interface GitHubConnectResponse {
  connected: boolean
  poll_interval_seconds: number
}

export interface GitHubInsightsResponse {
  insights: GitHubInsight[]
}

// chat — split into personal / group
export interface PersonalChatRequest {
  content: string
}

export interface PersonalChatResponse {
  reply: string
  answered_by: string
}

export interface GroupChatRequest {
  content: string
  speaker_name: string
}

export interface GroupChatResponse {
  message: ChatMessage
}

export interface ChatHistoryResponse {
  messages: ChatMessage[]
}

// pitch
export interface PitchResponse {
  pitch_outline: PitchOutline
  generated_at?: string
}

export interface PitchHistoryEntry {
  pitch_outline: PitchOutline
  generated_at: string
}

export interface PitchHistoryResponse {
  versions: PitchHistoryEntry[]
}

// team members
export interface AddTeamMemberRequest {
  name: string
  email?: string
  role?: string
}

export interface TeamMembersResponse {
  members: TeamMember[]
}

// files (generic upload surface, not just project-context intake)
export interface FileUploadResponse {
  file: ProjectFile
}

export interface FilesResponse {
  files: ProjectFile[]
}

// dashboard aggregation
export interface DashboardSummaryResponse {
  summary: DashboardSummary
  roadmap: RoadmapTask[]
}

// ─── UI State ────────────────────────────────────────────────────────────────

export interface AgentMeta {
  key: AgentNodeKey
  label: string
  shortLabel: string
  desc: string
  loop: string
  iconColor: string
  bgColor: string
}
