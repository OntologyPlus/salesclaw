import { Routes, Route } from 'react-router-dom'
import CollabOverviewPage from './CollabOverviewPage'
import TaskListPage from './TaskListPage'
import ApprovalListPage from './ApprovalListPage'
import AnnouncementListPage from './AnnouncementListPage'
import MeetingOrganizerChatPage from './MeetingOrganizerChatPage'
import ReportBuilderChatPage from './ReportBuilderChatPage'
import AcademicActivityChatPage from './AcademicActivityChatPage'
import AcademicBoardPage from './AcademicBoardPage'

// 协同办公模块路由
function CollabRoutes() {
  return (
    <Routes>
      <Route index element={<CollabOverviewPage />} />
      <Route path="tasks" element={<TaskListPage />} />
      <Route path="approvals" element={<ApprovalListPage />} />
      <Route path="announcements" element={<AnnouncementListPage />} />
      <Route path="meeting-organize" element={<MeetingOrganizerChatPage />} />
      <Route path="report-build" element={<ReportBuilderChatPage />} />
      <Route path="academic-chat" element={<AcademicActivityChatPage />} />
      <Route path="academic-board" element={<AcademicBoardPage />} />
    </Routes>
  )
}

export default CollabRoutes
