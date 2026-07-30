import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const now = Date.now()
  const diff = now - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function formatHours(hours: number): string {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

export function generateId(): string {
  return Math.random().toString(36).slice(2, 10)
}

export function severityColor(sev: string) {
  if (sev === 'high') return 'bg-danger'
  if (sev === 'med') return 'bg-gold'
  return 'bg-success'
}

export function taskStatusLabel(status: string): string {
  const map: Record<string, string> = {
    todo: 'To Do',
    in_progress: 'In Progress',
    blocked: 'Blocked',
    done: 'Done',
  }
  return map[status] ?? status
}

export const KANBAN_COLUMNS = [
  { id: 'todo', label: 'To Do', dotColor: 'bg-muted-2' },
  { id: 'in_progress', label: 'In Progress', dotColor: 'bg-purple' },
  { id: 'blocked', label: 'Blocked', dotColor: 'bg-danger' },
  { id: 'done', label: 'Done', dotColor: 'bg-success' },
] as const
