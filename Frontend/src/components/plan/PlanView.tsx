import type { ScopeData, RoadmapTask } from '@/types'
import { taskStatusLabel } from '@/lib/utils'

export function PlanView({ scope, roadmap }: { scope: ScopeData; roadmap: RoadmapTask[] }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-medium text-text">MVP features</h3>
        <ul className="space-y-1">
          {scope.mvp_features.map((f, i) => (
            <li key={i} className="text-sm text-text">• {f}</li>
          ))}
        </ul>
      </div>

      {scope.cut_features.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text">Cut for scope</h3>
          <ul className="space-y-1">
            {scope.cut_features.map((f, i) => (
              <li key={i} className="text-sm text-muted line-through">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {scope.assumptions.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text">Assumptions</h3>
          <ul className="space-y-1">
            {scope.assumptions.map((f, i) => (
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
              {roadmap.map((task) => (
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
