import { useState } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { useStore } from '@/store'
import { KANBAN_COLUMNS } from '@/lib/utils'
import { KanbanColumn } from './KanbanColumn'
import { TaskCard } from './TaskCard'
import type { RoadmapTask } from '@/types'

export function KanbanBoard() {
  const project = useStore((s) => s.project)
  const updateTask = useStore((s) => s.updateTask)
  const [activeTask, setActiveTask] = useState<RoadmapTask | null>(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const roadmap = project?.roadmap ?? []

  function handleDragStart(event: DragStartEvent) {
    const task = roadmap.find((t) => t.id === event.active.id)
    if (task) setActiveTask(task)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTask(null)
    const { active, over } = event
    if (!over) return

    const task = roadmap.find((t) => t.id === active.id)
    if (!task) return

    // `over.id` is either a column id (dropped on an empty column, or the
    // column container itself now that it's droppable) or a task id
    // (dropped on/near another card) — resolve to the target column
    // either way.
    const overData = over.data.current as { type?: string; columnId?: string; task?: RoadmapTask } | undefined
    const targetColumnId =
      overData?.type === 'column'
        ? overData.columnId
        : overData?.type === 'task'
          ? overData.task?.status
          : (over.id as string)

    if (targetColumnId && targetColumnId !== task.status) {
      updateTask({ ...task, status: targetColumnId as RoadmapTask['status'] })
      // TODO(phase 3.5 / backend integration): fire the PATCH to persist
      // the move once a tasksApi.move endpoint exists — optimistic local
      // update above keeps the board responsive in the meantime.
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4">
        {KANBAN_COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            id={col.id}
            label={col.label}
            dotColor={col.dotColor}
            tasks={roadmap.filter((t) => t.status === col.id)}
          />
        ))}
      </div>

      <DragOverlay>{activeTask ? <TaskCard task={activeTask} /> : null}</DragOverlay>
    </DndContext>
  )
}
