import { createBrowserRouter, Navigate } from 'react-router-dom'
import { LandingPage } from '@/pages/LandingPage'
import { IngestPage } from '@/pages/IngestPage'
import { PlanPage } from '@/pages/PlanPage'
import { DashboardShell } from '@/components/dashboard/DashboardShell'
import { OverviewPage } from '@/pages/dashboard/OverviewPage'
import { AgentPage } from '@/pages/dashboard/AgentPage'
import { PitchPage } from '@/pages/dashboard/PitchPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/projects/:projectId/ingest',
    element: <IngestPage />,
  },
  {
    path: '/projects/:projectId/plan',
    element: <PlanPage />,
  },
  {
    path: '/projects/:projectId/dashboard',
    element: <DashboardShell />,
    children: [
      {
        index: true,
        element: <OverviewPage />,
      },
      {
        path: 'agents/:agentKey',
        element: <AgentPage />,
      },
      {
        path: 'pitch',
        element: <PitchPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
