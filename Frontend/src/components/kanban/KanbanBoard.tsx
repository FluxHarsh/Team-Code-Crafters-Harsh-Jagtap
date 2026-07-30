import { useState } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { cn, KANBAN_COLUMNS } from '@/lib/utils'
import type { RoadmapTask } from '@/types'

// ─── Card ────────────────────────────────────────────────────────────────────

interface KanbanCardProps {
  task: RoadmapTask
  overlay?: boolean
  error?: string | null
}

function KanbanCard({ task, overlay, error }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        'bg-white border rounded-[10px] p-2.5 text-xs shadow-sm cursor-grab active:cursor-grabbing transition select-none',
        isDragging && 'opacity-40 rotate-1',
        overlay && 'shadow-lg rotate-2 opacity-95',
        task.status === 'blocked' && 'border-red-200 bg-danger-soft',
        task.status === 'in_progress' && 'border-purple/30',
        task.status === 'done' && 'opacity-80',
        !['blocked', 'in_progress', 'done'].includes(task.status) && 'border-border'
      )}
    >
      <p
        className={cn(
          'font-600 text-text leading-snug mb-2',
          task.status === 'done' && 'line-through text-muted decoration-muted-2'
        )}
      >
        {task.status === 'done' && <span className="text-success-dark mr-1">✓</span>}
        {task.task}
      </p>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded-[5px] bg-navy text-white text-[8px] font-700 flex items-center justify-center flex-none">
            {task.owner?.[0]?.toUpperCase() ?? '?'}
          </div>
          <span className="text-muted-2 text-[10px] truncate max-w-[80px]">{task.owner}</span>
        </div>
        <span
          className={cn(
            'text-[10px] font-600',
            task.status === 'blocked' && 'text-danger',
            task.status !== 'blocked' && 'text-muted-2'
          )}
        >
          {task.eta}
        </span>
      </div>
      {error && (
        <p className="text-[10px] text-danger mt-1.5 border-t border-red-100 pt-1.5">{error}</p>
      )}
    </div>
  )
}

// ─── Column ───────────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  colId: string
  label: string
  dotColor: string
  tasks: RoadmapTask[]
  errors: Record<string, string>
}

function KanbanColumn({ colId, label, dotColor, tasks, errors }: KanbanColumnProps) {
  const isEmpty = tasks.length === 0
  const colStyle = {
    todo: '',
    in_progress: 'bg-purple-soft/30',
    blocked: 'bg-danger-soft/40',
    done: 'bg-success-soft/30',
  }[colId] ?? ''

  return (
    <div className={cn('rounded-[12px] border border-border-soft p-2.5 flex flex-col min-h-[160px]', colStyle || 'bg-bg')}>
      {/* Column header */}
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-1.5">
          <span className={cn('w-2 h-2 rounded-full', dotColor)} />
          <span className="text-[10.5px] font-700 text-muted uppercase tracking-wide">{label}</span>
        </div>
        <span
          className={cn(
            'text-[10px] font-600 px-1.5 py-0.5 rounded-full border',
            colId === 'done' && 'bg-success-soft border-green-200 text-success-dark',
            colId === 'blocked' && 'bg-danger-soft border-red-200 text-danger',
            colId === 'in_progress' && 'bg-purple-soft border-purple/20 text-purple',
            colId === 'todo' && 'bg-white border-border text-muted'
          )}
        >
          {tasks.length}
        </span>
      </div>

      {/* Cards */}
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <div className="flex flex-col gap-2 flex-1">
          {isEmpty ? (
            <p className="text-[11px] text-muted-2 text-center py-4">Nothing here yet</p>
          ) : (
            tasks.map((task) => (
              <KanbanCard key={task.id} task={task} error={errors[task.id] ?? null} />
            ))
          )}
        </div>
      </SortableContext>
    </div>
  )
}

// ─── Board ────────────────────────────────────────────────────────────────────

interface KanbanBoardProps {
  tasks: RoadmapTask[]
  onTaskMove: (taskId: string, newStatus: RoadmapTask['status']) => Promise<void>
}

export function KanbanBoard({ tasks, onTaskMove }: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const activeTask = tasks.find((t) => t.id === activeId)

  const getColumnTasks = (colId: string) => tasks.filter((t) => t.status === colId)

  const handleDragStart = (e: DragStartEvent) => {
    setActiveId(e.active.id as string)
  }

  const handleDragEnd = async (e: DragEndEvent) => {
    setActiveId(null)
    const { active, over } = e
    if (!over) return

    // Determine drop column by checking if overId is a column id or a task id
    const overId = over.id as string
    let newStatus: RoadmapTask['status'] | undefined
    const colMatch = KANBAN_COLUMNS.find((c) => c.id === overId)
    if (colMatch) {
      newStatus = colMatch.id as RoadmapTask['status']
    } else {
      const overTask = tasks.find((t) => t.id === overId)
      if (overTask) newStatus = overTask.status
    }

    if (!newStatus) return
    const task = tasks.find((t) => t.id === active.id)
    if (!task || task.status === newStatus) return

    // Optimistic update is handled by parent via onTaskMove
    try {
      setErrors((prev) => { const n = { ...prev }; delete n[task.id]; return n })
      await onTaskMove(task.id, newStatus)
    } catch {
      setErrors((prev) => ({ ...prev, [task.id]: 'Failed to move — try again' }))
    }
  }

  return (
    <div className="overflow-x-auto pb-2">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-4 gap-3 min-w-[700px]">
          {KANBAN_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.id}
              colId={col.id}
              label={col.label}
              dotColor={col.dotColor}
              tasks={getColumnTasks(col.id)}
              errors={errors}
            />
          ))}
        </div>

        <DragOverlay>
          {activeTask ? (
            <div className="rotate-2 opacity-90">
              <KanbanCard task={activeTask} overlay />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
