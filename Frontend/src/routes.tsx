import { createBrowserRouter, Navigate } from 'react-router-dom'
import { LandingPage } from '@/pages/LandingPage'
import { IngestPage } from '@/pages/IngestPage'
import { PlanPage } from '@/pages/PlanPage'
import { DashboardShell } from '@/components/dashboard/DashboardShell'
import { OverviewPage } from '@/pages/dashboard/OverviewPage'
import { AgentPage } from '@/pages/dashboard/AgentPage'
import { PitchPage } from '@/pages/dashboard/PitchPage'
import { PersonalChatPage } from '@/pages/dashboard/PersonalChatPage'
import { GroupChatPage } from '@/pages/dashboard/GroupChatPage'
import { TeamMembersPanel } from '@/components/team/TeamMembersPanel'
import { FileUploadPanel } from '@/components/files/FileUploadPanel'
import { PlannerSuggestionsInbox } from '@/components/suggestions/PlannerSuggestionsInbox'
import { GitHubInsightsPanel } from '@/components/github/GitHubInsightsPanel'
import { useParams } from 'react-router-dom'

// Small wrappers so route-level components (which don't take props) can
// still read :projectId and hand it to the panel components used both
// here and elsewhere.
function TeamRoute() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <TeamMembersPanel projectId={projectId} />
}

function FilesRoute() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <FileUploadPanel projectId={projectId} />
}

function SuggestionsRoute() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <PlannerSuggestionsInbox projectId={projectId} />
}

function GitHubRoute() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <GitHubInsightsPanel projectId={projectId} />
}

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
        path: 'team',
        element: <TeamRoute />,
      },
      {
        path: 'files',
        element: <FilesRoute />,
      },
      {
        path: 'chat/personal',
        element: <PersonalChatPage />,
      },
      {
        path: 'chat/group',
        element: <GroupChatPage />,
      },
      {
        path: 'suggestions',
        element: <SuggestionsRoute />,
      },
      {
        path: 'github',
        element: <GitHubRoute />,
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
