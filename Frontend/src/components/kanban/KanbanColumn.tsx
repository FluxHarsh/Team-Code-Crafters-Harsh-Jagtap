import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { RoadmapTask } from '@/types'
import { TaskCard } from './TaskCard'
import { cn } from '@/lib/utils'

interface KanbanColumnProps {
  id: string
  label: string
  dotColor: string
  tasks: RoadmapTask[]
}

export function KanbanColumn({ id, label, dotColor, tasks }: KanbanColumnProps) {
  // FIXED: previously only individual tasks were registered as drop
  // targets (via useSortable in TaskCard). An empty column had nothing
  // droppable in it at all, so dragging a task into an empty column
  // silently failed. useDroppable here makes the column container itself
  // a valid drop target regardless of how many tasks it holds.
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: { type: 'column', columnId: id },
  })

  return (
    <div className="flex w-72 flex-shrink-0 flex-col">
      <div className="mb-2 flex items-center gap-2 px-1">
        <span className={cn('h-2 w-2 rounded-full', dotColor)} />
        <span className="text-sm font-medium text-text">{label}</span>
        <span className="ml-auto rounded-full bg-bg px-2 py-0.5 text-xs text-muted">{tasks.length}</span>
      </div>

      <div
        ref={setNodeRef}
        className={cn(
          'flex min-h-[120px] flex-1 flex-col gap-2 rounded-card border border-dashed p-2 transition-colors',
          isOver ? 'border-primary bg-primary-soft' : 'border-border-soft bg-bg/50'
        )}
      >
        <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
          {tasks.length === 0 && (
            <div className="flex flex-1 items-center justify-center py-6 text-xs text-muted">
              Drop a task here
            </div>
          )}
        </SortableContext>
      </div>
    </div>
  )
}
