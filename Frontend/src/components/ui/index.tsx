import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

// ─── Status Dot ───────────────────────────────────────────────────────────────

interface StatusDotProps {
  live: boolean
  className?: string
}
export function StatusDot({ live, className }: StatusDotProps) {
  return (
    <span
      className={cn(
        'inline-block w-1.5 h-1.5 rounded-full flex-none',
        live ? 'dot-live' : 'bg-muted-2',
        className
      )}
    />
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

export function SkeletonTile({ className }: { className?: string }) {
  return <div className={cn('skeleton', className)} />
}

export function SkeletonCard() {
  return (
    <div className="bg-card border border-border rounded-card p-4 shadow-card space-y-3">
      <SkeletonTile className="h-3 w-24" />
      <SkeletonTile className="h-7 w-16" />
      <SkeletonTile className="h-2.5 w-32" />
    </div>
  )
}

// ─── Empty State ──────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
      {icon && <div className="text-muted-2 mb-3 text-3xl">{icon}</div>}
      <p className="text-sm font-600 text-muted">{title}</p>
      {description && <p className="text-xs text-muted-2 mt-1 max-w-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ─── Severity Badge ───────────────────────────────────────────────────────────

export function SeverityDot({ severity }: { severity: string }) {
  return (
    <span
      className={cn(
        'w-2 h-2 rounded-full flex-none mt-1',
        severity === 'high' && 'bg-danger',
        severity === 'med' && 'bg-gold',
        severity === 'low' && 'bg-success'
      )}
    />
  )
}

// ─── Tag / Pill ───────────────────────────────────────────────────────────────

interface TagProps {
  live?: boolean
  children: ReactNode
  className?: string
}
export function Tag({ live, children, className }: TagProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-700 px-2.5 py-1 rounded-full',
        live
          ? 'bg-success-soft text-success-dark'
          : 'bg-border-soft text-muted',
        className
      )}
    >
      {children}
    </span>
  )
}

// ─── Button ───────────────────────────────────────────────────────────────────

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 font-600 rounded-[9px] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed',
        size === 'sm' && 'text-xs px-3 py-1.5',
        size === 'md' && 'text-sm px-4 py-2',
        size === 'lg' && 'text-sm px-5 py-2.5',
        variant === 'primary' &&
          'bg-primary text-white hover:bg-primary-dark shadow-sm',
        variant === 'secondary' &&
          'bg-white border border-border text-text hover:bg-bg',
        variant === 'ghost' &&
          'text-muted hover:bg-bg hover:text-text',
        variant === 'danger' &&
          'bg-danger-soft text-danger hover:bg-red-100',
        className
      )}
      {...props}
    >
      {loading ? (
        <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : null}
      {children}
    </button>
  )
}

// ─── Input ────────────────────────────────────────────────────────────────────

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
  label?: string
}
export function Input({ error, label, className, id, ...props }: InputProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={id} className="text-xs font-600 text-muted">
          {label}
        </label>
      )}
      <input
        id={id}
        className={cn(
          'w-full bg-white border rounded-[9px] px-3 py-2 text-sm text-text placeholder:text-muted-2 outline-none transition focus:border-primary focus:ring-1 focus:ring-primary/20',
          error ? 'border-danger' : 'border-border',
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}

// ─── Card ─────────────────────────────────────────────────────────────────────

export function Card({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'bg-card border border-border rounded-card shadow-card p-4',
        className
      )}
    >
      {children}
    </div>
  )
}

// ─── Inline Error ─────────────────────────────────────────────────────────────

export function InlineError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 bg-danger-soft border border-red-200 text-danger text-xs rounded-[9px] px-3 py-2">
      <span>⚠</span>
      <span>{message}</span>
    </div>
  )
}
