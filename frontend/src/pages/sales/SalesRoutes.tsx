import { Routes, Route } from 'react-router-dom'
import SalesOverviewPage from './SalesOverviewPage'
import VisitPlansPage from './VisitPlansPage'
import VisitRecordsPage from './VisitRecordsPage'
import VisitFeedbackPage from './VisitFeedbackPage'
import CoveragePage from './CoveragePage'
import ScoringPage from './ScoringPage'
import MatrixPage from './MatrixPage'
import RoiPage from './RoiPage'
import VisitPlanChatPage from './VisitPlanChatPage'
import KolAnalyzerChatPage from './KolAnalyzerChatPage'

// 销售执行模块路由
function SalesRoutes() {
  return (
    <Routes>
      <Route index element={<SalesOverviewPage />} />
      <Route path="plans" element={<VisitPlansPage />} />
      <Route path="records" element={<VisitRecordsPage />} />
      <Route path="feedback" element={<VisitFeedbackPage />} />
      <Route path="coverage" element={<CoveragePage />} />
      <Route path="scoring" element={<ScoringPage />} />
      <Route path="matrix" element={<MatrixPage />} />
      <Route path="roi" element={<RoiPage />} />
      <Route path="visit-plan-create" element={<VisitPlanChatPage />} />
      <Route path="kol-analyze" element={<KolAnalyzerChatPage />} />
    </Routes>
  )
}

export default SalesRoutes
