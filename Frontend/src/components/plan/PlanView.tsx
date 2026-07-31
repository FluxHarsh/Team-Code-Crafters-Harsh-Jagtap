import type { ScopeData, RoadmapTask } from '@/types'
import { taskStatusLabel } from '@/lib/utils'

export function PlanView({ scope, roadmap }: { scope: ScopeData; roadmap: RoadmapTask[] }) {
  // A project whose Planner hasn't run yet still has scope={} (backend JSONB
  // default) — default every array so the view renders empty instead of
  // crashing on undefined.map.
  const mvpFeatures = scope?.mvp_features ?? []
  const cutFeatures = scope?.cut_features ?? []
  const assumptions = scope?.assumptions ?? []
  const tasks = roadmap ?? []

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-medium text-text">MVP features</h3>
        <ul className="space-y-1">
          {mvpFeatures.map((f, i) => (
            <li key={i} className="text-sm text-text">• {f}</li>
          ))}
        </ul>
      </div>

      {cutFeatures.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text">Cut for scope</h3>
          <ul className="space-y-1">
            {cutFeatures.map((f, i) => (
              <li key={i} className="text-sm text-muted line-through">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {assumptions.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text">Assumptions</h3>
          <ul className="space-y-1">
            {assumptions.map((f, i) => (
              <li key={i} className="text-sm text-muted">• {f}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-text">Roadmap</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-bg text-xs text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Task</th>
                <th className="px-3 py-2 text-left">Owner</th>
                <th className="px-3 py-2 text-left">ETA</th>
                <th className="px-3 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id} className="border-t border-border">
                  <td className="px-3 py-2 text-text">{task.task}</td>
                  <td className="px-3 py-2 text-muted">{task.owner}</td>
                  <td className="px-3 py-2 text-muted">{task.eta}</td>
                  <td className="px-3 py-2 text-muted">{taskStatusLabel(task.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
