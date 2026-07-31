import type { AgentMeta } from '@/types'

// 9-node roster matching the real backend.
export const AGENT_LIST: AgentMeta[] = [
  {
    key: 'supervisor',
    label: 'Supervisor',
    shortLabel: 'SUP',
    desc: 'Routes between all agents based on project state and time remaining.',
    loop: 'Router',
    iconColor: 'text-navy',
    bgColor: 'bg-navy-soft',
  },
  {
    key: 'intake',
    label: 'Intake',
    shortLabel: 'INT',
    desc: 'Gathers the problem statement and solution through conversation and uploaded files.',
    loop: 'Planning loop',
    iconColor: 'text-info',
    bgColor: 'bg-info-soft',
  },
  {
    key: 'scope_critic',
    label: 'Scope Critic',
    shortLabel: 'SCP',
    desc: 'Flags over-scoping and assumption gaps against past postmortem patterns.',
    loop: 'Planning loop',
    iconColor: 'text-purple',
    bgColor: 'bg-purple-soft',
  },
  {
    key: 'planner',
    label: 'Planner',
    shortLabel: 'PLN',
    desc: 'Builds and revises the hour-by-hour roadmap from scope and time remaining, iterating on feedback.',
    loop: 'Planning loop',
    iconColor: 'text-primary',
    bgColor: 'bg-primary-soft',
  },
  {
    key: 'reprioritizer',
    label: 'Reprioritizer',
    shortLabel: 'RPR',
    desc: 'Proposes roadmap fixes for the user to accept or dismiss instead of auto-replanning.',
    loop: 'Monitoring loop',
    iconColor: 'text-gold',
    bgColor: 'bg-gold-soft',
  },
  {
    key: 'github_watcher',
    label: 'GitHub Watcher',
    shortLabel: 'GHW',
    desc: 'Polls the repo every 2 min. Maps commits and PRs to roadmap milestones and surfaces insights.',
    loop: 'Monitoring loop',
    iconColor: 'text-teal',
    bgColor: 'bg-teal-soft',
  },
  {
    key: 'risk_watcher',
    label: 'Risk Watcher',
    shortLabel: 'RSK',
    desc: 'Flags stalled tasks, unreviewed PRs, and ETA breaches.',
    loop: 'Monitoring loop',
    iconColor: 'text-danger',
    bgColor: 'bg-danger-soft',
  },
  {
    key: 'pitch_agent',
    label: 'Pitch Agent',
    shortLabel: 'PTC',
    desc: 'Generates the pitch outline when the roadmap is mostly complete or time is low.',
    loop: 'Output',
    iconColor: 'text-success',
    bgColor: 'bg-success-soft',
  },
  {
    key: 'team_assistant',
    label: 'Team Assistant',
    shortLabel: 'TMA',
    desc: 'Handles team member management and group chat coordination.',
    loop: 'Output',
    iconColor: 'text-pink',
    bgColor: 'bg-pink-soft',
  },
]

export const AGENT_MAP = Object.fromEntries(
  AGENT_LIST.map((a) => [a.key, a])
) as Record<string, AgentMeta>
