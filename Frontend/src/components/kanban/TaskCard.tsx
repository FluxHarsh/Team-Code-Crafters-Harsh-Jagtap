import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { RoadmapTask } from '@/types'
import { cn } from '@/lib/utils'

export function TaskCard({ task }: { task: RoadmapTask }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    data: { type: 'task', task },
  })

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
        'cursor-grab rounded-lg border border-border bg-card p-3 shadow-sm active:cursor-grabbing',
        isDragging && 'dragging-card'
      )}
    >
      <p className="text-sm font-medium text-text">{task.task}</p>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-navy-soft text-[10px] font-semibold text-navy">
          {task.owner.slice(0, 2).toUpperCase()}
        </span>
        <span>{task.eta}</span>
      </div>
    </div>
  )
}
