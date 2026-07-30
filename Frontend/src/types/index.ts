// ─── Project ────────────────────────────────────────────────────────────────

export type ProjectStatus =
  | 'intake'
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
}

// ─── Chat ───────────────────────────────────────────────────────────────────

export type ChatPhase = 'intake' | 'planning' | 'coaching'
export type ChatRole = 'user' | 'agent'

export interface ChatMessage {
  id: string
  project_id?: string
  // phase is not returned by GET /ingest/history or GET /chat/history
  phase?: ChatPhase
  role: ChatRole
  agent_node?: string
  speaker_name?: string
  content: string
  // created_at is not returned by GET /ingest/history
  created_at?: string
}

// ─── Agent Graph ─────────────────────────────────────────────────────────────

export type AgentNodeKey =
  | 'supervisor'
  | 'intake'
  | 'scope_critic'
  | 'planner'
  | 'github_watcher'
  | 'risk_watcher'
  | 'reprioritizer'
  | 'pitch_agent'

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

// Backend sends {"event": "...", "payload": {...}}
export interface WSEvent {
  event: WSEventType   // ← was "type", backend sends "event"
  payload: Record<string, unknown>
}

// ─── API Responses ───────────────────────────────────────────────────────────

export interface CreateProjectResponse {
  project_id: string
  status: ProjectStatus
  greeting: string
}

export interface IngestMessageResponse {
  reply: string
  ready_for_planning: boolean
}

export interface IngestDocumentResponse {
  document_id: string
  filename: string
  extracted_chars: number
}

export interface PlanChatResponse {
  reply: string
  draft_scope: ScopeData
  draft_roadmap: RoadmapTask[]
}

export interface PlanDraftResponse {
  draft_scope: ScopeData
  draft_roadmap: RoadmapTask[]
}

export interface PlanApproveResponse {
  status: ProjectStatus
  plan_approved_at: string
  dashboard_ready: boolean
}

export interface GitHubConnectResponse {
  connected: boolean
  poll_interval_seconds: number
}

export interface ReprioritizeResponse {
  decision: string
  rationale: string
  roadmap_replanned: boolean
}

export interface ChatResponse {
  reply: string
  answered_by: string
}

export interface PitchResponse {
  pitch_outline: PitchOutline
  generated_at?: string
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