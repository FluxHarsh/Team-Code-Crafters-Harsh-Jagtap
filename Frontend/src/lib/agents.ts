import type { AgentMeta } from '@/types'

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
    label: 'Intake / Clarifier',
    shortLabel: 'INT',
    desc: 'Gathers the problem statement and solution through conversation.',
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
    desc: 'Builds and rebuilds the hour-by-hour roadmap from scope and time remaining.',
    loop: 'Planning loop',
    iconColor: 'text-primary',
    bgColor: 'bg-primary-soft',
  },
  {
    key: 'github_watcher',
    label: 'GitHub Watcher',
    shortLabel: 'GHW',
    desc: 'Polls the repo every 2 min. Maps commits and PRs to roadmap milestones.',
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
    key: 'reprioritizer',
    label: 'Reprioritizer',
    shortLabel: 'RPR',
    desc: 'Decides how to fix each risk using Neo4j dependency traversal.',
    loop: 'Monitoring loop',
    iconColor: 'text-gold',
    bgColor: 'bg-gold-soft',
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
]

export const AGENT_MAP = Object.fromEntries(
  AGENT_LIST.map((a) => [a.key, a])
) as Record<string, AgentMeta>
