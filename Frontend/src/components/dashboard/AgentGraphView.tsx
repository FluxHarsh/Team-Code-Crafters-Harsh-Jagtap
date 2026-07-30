import { useStore } from '@/store'
import { AGENT_LIST } from '@/lib/agents'
import { cn } from '@/lib/utils'
import type { AgentNodeKey } from '@/types'

// Node positions in a logical graph layout
const NODE_POSITIONS: Record<AgentNodeKey, { x: number; y: number }> = {
  supervisor:     { x: 300, y: 30  },
  intake:         { x: 80,  y: 120 },
  scope_critic:   { x: 230, y: 120 },
  planner:        { x: 380, y: 120 },
  github_watcher: { x: 100, y: 230 },
  risk_watcher:   { x: 270, y: 230 },
  reprioritizer:  { x: 430, y: 230 },
  pitch_agent:    { x: 300, y: 320 },
}

// Edges: [from, to]
const EDGES: [AgentNodeKey, AgentNodeKey][] = [
  ['supervisor', 'intake'],
  ['supervisor', 'scope_critic'],
  ['supervisor', 'planner'],
  ['supervisor', 'github_watcher'],
  ['supervisor', 'risk_watcher'],
  ['supervisor', 'pitch_agent'],
  ['intake', 'scope_critic'],
  ['scope_critic', 'planner'],
  ['github_watcher', 'risk_watcher'],
  ['risk_watcher', 'reprioritizer'],
  ['reprioritizer', 'planner'],
  ['planner', 'supervisor'],
]

const NODE_RADIUS = 28

interface NodeProps {
  nodeKey: AgentNodeKey
  isActive: boolean
  x: number
  y: number
  label: string
  shortLabel: string
  bgColor: string
  iconColor: string
}

function GraphNode({ nodeKey, isActive, x, y, label, shortLabel }: NodeProps) {
  return (
    <g transform={`translate(${x},${y})`} className="cursor-default">
      {/* Glow ring when active */}
      {isActive && (
        <circle
          r={NODE_RADIUS + 8}
          fill="none"
          stroke="#FF6B4A"
          strokeWidth="2"
          opacity="0.4"
          className="animate-ping"
          style={{ transformOrigin: '0 0' }}
        />
      )}

      {/* Node circle */}
      <circle
        r={NODE_RADIUS}
        fill={isActive ? '#FF6B4A' : '#F6F7FB'}
        stroke={isActive ? '#F0522F' : '#ECEEF5'}
        strokeWidth={isActive ? 2 : 1.5}
      />

      {/* Label text */}
      <text
        textAnchor="middle"
        dy="-4"
        fontSize="9"
        fontWeight="800"
        fill={isActive ? '#fff' : '#1B2540'}
        fontFamily="Inter, sans-serif"
      >
        {shortLabel}
      </text>

      {/* Full label below */}
      <text
        textAnchor="middle"
        dy={NODE_RADIUS + 14}
        fontSize="8.5"
        fontWeight="600"
        fill={isActive ? '#F0522F' : '#7C88A6'}
        fontFamily="Inter, sans-serif"
      >
        {label}
      </text>

      {/* Live dot */}
      {isActive && (
        <circle cx={NODE_RADIUS - 4} cy={-(NODE_RADIUS - 4)} r={4} fill="#1FAE59" />
      )}
    </g>
  )
}

export function AgentGraphView() {
  const activeNode = useStore((s) => s.agentGraph.active_node)
  const recentRuns = useStore((s) => s.agentGraph.recent_runs)

  return (
    <div className="space-y-3">
      {/* SVG Graph */}
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 580 380"
          className="w-full max-w-[580px] mx-auto"
          style={{ minWidth: 360 }}
        >
          {/* Edges */}
          {EDGES.map(([from, to]) => {
            const f = NODE_POSITIONS[from]
            const t = NODE_POSITIONS[to]
            if (!f || !t) return null
            const isActive =
              activeNode === from || activeNode === to
            return (
              <line
                key={`${from}-${to}`}
                x1={f.x}
                y1={f.y}
                x2={t.x}
                y2={t.y}
                stroke={isActive ? '#FF6B4A' : '#ECEEF5'}
                strokeWidth={isActive ? 2 : 1.5}
                strokeDasharray={isActive ? undefined : '4 3'}
                opacity={isActive ? 0.8 : 1}
              />
            )
          })}

          {/* Nodes */}
          {AGENT_LIST.map((agent) => {
            const pos = NODE_POSITIONS[agent.key]
            if (!pos) return null
            return (
              <GraphNode
                key={agent.key}
                nodeKey={agent.key}
                isActive={activeNode === agent.key}
                x={pos.x}
                y={pos.y}
                label={agent.label.split('/')[0].trim()}
                shortLabel={agent.shortLabel}
                bgColor={agent.bgColor}
                iconColor={agent.iconColor}
              />
            )
          })}
        </svg>
      </div>

      {/* Recent activity feed */}
      {recentRuns.length > 0 && (
        <div className="border-t border-border-soft pt-3 space-y-1.5">
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2">Recent</p>
          {recentRuns.slice(0, 4).map((run, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-muted-2 flex-none" />
              <span className="font-600 text-navy">{run.node.replace(/_/g, ' ')}</span>
              <span className="text-muted-2 text-[10px] ml-auto font-mono">
                {new Date(run.finished_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
      )}

      {activeNode === null && recentRuns.length === 0 && (
        <p className="text-xs text-muted-2 text-center py-2">
          Agent graph will light up when monitoring starts
        </p>
      )}
    </div>
  )
}
