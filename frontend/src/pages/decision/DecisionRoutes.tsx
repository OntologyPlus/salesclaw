import { Routes, Route } from 'react-router-dom'
import DecisionOverviewPage from './DecisionOverviewPage'
import KpiDashboardPage from './KpiDashboardPage'
import { AttributionPage } from './AttributionPage'
import SimulationPage from './SimulationPage'
import AlertsPage from './AlertsPage'
import EffectTrackingPage from './EffectTrackingPage'
import WhatIfChatPage from './WhatIfChatPage'
import AlertManagerChatPage from './AlertManagerChatPage'
import { DiagnosisPage } from './DiagnosisPage'
import LoopPage from './LoopPage'
import RepDiagnosisPage from './RepDiagnosisPage'
import FollowupPage, { FollowupDetailPage } from './FollowupPage'
import { ParadigmPage } from './ParadigmPage'

// 决策支持模块路由
function DecisionRoutes() {
  return (
    <Routes>
      <Route index element={<DecisionOverviewPage />} />
      <Route path="kpi" element={<KpiDashboardPage />} />
      <Route path="attribution" element={<AttributionPage />} />
      <Route path="simulation" element={<SimulationPage />} />
      <Route path="alerts" element={<AlertsPage />} />
      <Route path="executions" element={<EffectTrackingPage />} />
      <Route path="what-if-simulate" element={<WhatIfChatPage />} />
      <Route path="alert-disposition" element={<AlertManagerChatPage />} />
      <Route path="diagnosis" element={<DiagnosisPage />} />
      <Route path="loop" element={<LoopPage />} />
      <Route path="loop/rep/:repId" element={<RepDiagnosisPage />} />
      <Route path="followup" element={<FollowupPage />} />
      <Route path="loop/followup/:executionId" element={<FollowupDetailPage />} />
      <Route path="paradigms" element={<ParadigmPage />} />
    </Routes>
  )
}

export default DecisionRoutes
