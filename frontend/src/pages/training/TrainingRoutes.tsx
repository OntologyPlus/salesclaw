import { Routes, Route } from 'react-router-dom'
import TrainingOverviewPage from './TrainingOverviewPage'
import CoursesPage from './CoursesPage'
import ExamsPage from './ExamsPage'
import PathsPage from './PathsPage'
import MyLearningPage from './MyLearningPage'
import PracticePage from './PracticePage'
import CertificatesPage from './CertificatesPage'
import ActivityListPage from './ActivityListPage'
import ActivityDataPage from './ActivityDataPage'
import PersonaLibraryPage from './PersonaLibraryPage'
import ScenarioParsePage from './ScenarioParsePage'
import PPTSpeechPage from './PPTSpeechPage'
import ExperiencePage from './ExperiencePage'
import SceneCreateChatPage from './SceneCreateChatPage'
import ExamCreateChatPage from './ExamCreateChatPage'
// B 路径：培训效果因果归因
import EffectOverviewPage from './EffectOverviewPage'
import ExecutionDetailPage from './ExecutionDetailPage'

// 智能培训模块路由
function TrainingRoutes() {
  return (
    <Routes>
      <Route index element={<TrainingOverviewPage />} />
      <Route path="courses" element={<CoursesPage />} />
      <Route path="exams" element={<ExamsPage />} />
      <Route path="paths" element={<PathsPage />} />
      <Route path="my-learning" element={<MyLearningPage />} />
      <Route path="practice" element={<PracticePage />} />
      <Route path="certificates" element={<CertificatesPage />} />
      <Route path="activities" element={<ActivityListPage />} />
      <Route path="activities/:id/data" element={<ActivityDataPage />} />
      <Route path="personas" element={<PersonaLibraryPage />} />
      <Route path="scenario-parse" element={<ScenarioParsePage />} />
      <Route path="ppt-speech" element={<PPTSpeechPage />} />
      <Route path="experience" element={<ExperiencePage />} />
      <Route path="scene-create" element={<SceneCreateChatPage />} />
      <Route path="exam-create" element={<ExamCreateChatPage />} />
      {/* B 路径：培训效果因果归因路由 */}
      <Route path="effect" element={<EffectOverviewPage />} />
      <Route path="effect/:executionId" element={<ExecutionDetailPage />} />
    </Routes>
  )
}

export default TrainingRoutes
